# Detection method

`lib/detector.js` scores a single chat message for likely drug-sale activity
and returns an explainable result. This doc describes how, so scores can be
audited and the lexicon can be extended safely.

## Pipeline

```
raw text
  -> normalize()          plain + leet-decoded forms
  -> lexicon match        direct substring + fuzzy (typo-tolerant)
  -> emoji match           drug-coded emoji
  -> extractIdentifiers()  phone / email / UPI / wallet / URL
  -> intent word count     ("price", "cod", "dm", "available", ...)
  -> risk formula          -> { risk: 0-10, level, reasons, matches }
```

### 1. Normalization (`normalize`)

- Lowercases the text and strips zero-width characters (`\u200B-\u200D`,
  `\uFEFF`) sometimes used to break up flagged words.
- Collapses spaced-out or dotted/dashed letter sequences of 4+ characters
  (`h e r o i n`, `h.e.r.o.i.n` -> `heroin`) so simple spacing evasion
  doesn't defeat matching.
- Produces a second, "leet-decoded" form by reversing common leetspeak
  substitutions (`0->o, 1->i, 3->e, 4->a, 5->s, 7->t, @->a, $->s`), e.g.
  `c0ca1ne` -> `cocaine`.

Both the plain and leet forms are checked against the lexicon, so a hit in
either counts.

### 2. Lexicon matching

`lib/lexicon.json` holds `{ t: term, cat: category, w: weight }` entries.
A term matches a message if:

- **Direct**: the term is a substring of the normalized (plain or leet) text.
- **Fuzzy** (typo tolerance), only when the term isn't already a direct hit:
  - Terms **>= 5 characters**: any word in the message within 1 character of
    length and 1 Levenshtein edit of the term.
  - Terms of **exactly 4 characters**: any word of the *same length* that is
    1 substitution/transposition away (catches `woed`/`coje`-style typos
    without opening up insertion/deletion matches, which get noisy at this
    length).
  - Terms **under 4 characters** (e.g. `lsd`) are never fuzzy-matched - too
    short for edit-distance tolerance to be reliable.
  - Multi-word terms (containing a space) are never fuzzy-matched.

Each match contributes to a `base` risk equal to the **highest weight** among
matched terms (not summed - one very high-weight term is enough to establish
risk regardless of how many low-weight terms also matched).

### 3. Emoji matching

Each drug-coded emoji present in the raw text (`❄️`, `💊`, `🍁`, `🌿`, `🍄` by
default) adds its weight to `emojiScore`, which is capped at **+3** total
before being added to `base`. Emojis alone are a weak signal by design - the
cap keeps an emoji-only message from reaching "high" on its own.

### 4. Identifiers (`extractIdentifiers`)

Regex-based extraction of contact/payment identifiers commonly seen in sale
messages:

- **Phones**: Indian mobile numbers (`+91` optional, leading digit 6-9, 10
  digits), tolerant of internal spaces/dashes/dots.
- **Emails**: standard email shape.
- **UPI handles**: `name@bank-suffix` (oksbi, okhdfc, okicici, okaxis, ybl,
  paytm, upi, ibl, axl).
- **Wallets**: Bitcoin-style Base58 (`1...`/`3...`/`bc1...`, excluding the
  Base58-invalid characters `0`, `O`, `I`, lowercase `l`) and Ethereum-style
  `0x` + 40 hex chars.
- **URLs**: `http(s)://`, `t.me/...`, `wa.me/...` links.

`hasId` is true if any phone, UPI, or wallet identifier was found. (URLs and
emails are extracted and returned but don't themselves flip `hasId` - they're
too common in ordinary chat to be a strong signal on their own.)

### 5. Intent words

A fixed word list (`available, deal, price, stock, delivery, cod, dm,
pickup, gram, grams, kg, rate, supply, need, asked`) is checked against the
tokenized leet-decoded text. `intent` is the count of distinct hits.

### 6. Risk formula

```
risk = base + min(emojiScore, 3)

if risk > 0:
    risk += min(intent, 2)          # up to +2 for sale-intent language
    if 3+ distinct matches: risk += 1
    if hasId: risk += 1

risk = clamp(risk, 0, 10)
```

**Identifiers and intent words never establish risk on their own.** If no
lexicon term or emoji matched (`base == 0` and `emojiScore == 0`), risk stays
`0` regardless of how many identifiers or intent words are present - a bare
phone number, or generic commerce chatter like "price? cod, dm", is not
itself evidence of drug activity without a substance reference. This is a
deliberate design choice to bound false positives, not an oversight; see the
regression test in `test/detector.test.js` that pins this behavior.

### 7. Level thresholds

```
risk >= 7  -> "high"
risk >= 4  -> "medium"
else       -> "low"
```

### `reasons`

Every contributing signal (each matched term, each emoji, intent words,
identifier presence) is appended to a human-readable `reasons` array so a
reviewer can see *why* a message scored the way it did without re-deriving
it from the raw weights.

## Network graph (`lib/network.js`)

`buildGraph(detections)` turns a list of saved detection records into a
graph of `account <-> group` and `account <-> identifier` nodes/edges, for
spotting accounts that operate across many groups (possible suppliers) vs.
accounts that just post repeatedly in one group (buyers/promoters).

- Nodes: `user:<userId>`, `chat:<chatId>`, and one node per distinct
  identifier value (`phones:...`, `upi:...`, `wallets:...`; URLs are
  excluded - too noisy to treat as identity nodes).
- Edges: `posts_in` (user -> chat) and `uses` (user -> identifier), one per
  occurrence (so repeated posts in the same chat produce repeated edges,
  useful as a frequency signal).
- **Degree**, used for the role heuristic, is the count of *distinct*
  neighbors (a `Set`), not the raw edge count - so an account that posts 10
  times in one group has degree 1 there, not 10. `role` is `'supplier?'`
  when an account's distinct-neighbor degree is >= 4 (touches many
  groups/identifiers), otherwise `'buyer/promoter?'`.

## Storage (`lib/memoryStore.js` / `lib/db.js`)

Both implement the same two-method interface consumed by the API routes:

```
saveDetection(record) -> Promise<void>
getDetections({ minRisk, sinceDays }) -> Promise<Array<record>>
```

`memoryStore.js` is an in-process array, for local dev/tests. `db.js` is the
MongoDB-backed implementation (`MONGODB_URI` env var) used in production;
`server.js` picks whichever is configured and closes it cleanly on
`SIGTERM`/`SIGINT` (waits for `server.close()`, then `store.close()`, so a
redeploy doesn't drop in-flight requests or leave the Mongo pool open).
See `lib/db.js` for index and query details.

## Data contract compliance (`api/detect.js`)

The team's shared `detections` shape (see PROJECT CONTEXT) is:

```
{ platform, chatId, chatTitle, userId, username, text, mediaType, ts,
  risk, level, categories, matches, identifiers, reasons, imageLabels }
```

`POST /api/detect` now accepts and validates `platform` (`telegram` |
`instagram`), `mediaType`, `ts`, and `imageLabels` from the caller, and
writes every one of these fields on the saved record - defaulting the ones
a caller omits rather than dropping them. This matters because Akshiya's
Telegram webhook and Lingesh's Instagram/image pipeline both write into the
same collection that `lib/network.js` reads from; if either write path
produced a differently-shaped record, `buildGraph()` and any dashboard
filter keyed on `platform` or `mediaType` would silently miss data. A
record is only persisted once `platform` is supplied, since an
unattributed record (can't tell Telegram from Instagram) is worse than no
record for the network graph. This is pinned by a regression test in
`test/detector.test.js` that posts to the real Express route and asserts
every contract field is present on what gets saved.
