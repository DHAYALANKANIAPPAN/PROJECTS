'use strict';

const lex = require('./lexicon.json');

const LEET = { '0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a', '$': 's' };

/**
 * Normalize raw text into two forms:
 *  - plain: lowercased, zero-width chars stripped, spaced-out letters collapsed
 *  - leet:  plain with common leetspeak substitutions reversed (0->o, 3->e, etc.)
 */
function normalize(t) {
  let s = String(t).toLowerCase().replace(/[\u200B-\u200D\uFEFF]/g, '');
  // collapse spaced/dotted/dashed letter sequences like "h e r o i n" or "h.e.r.o.i.n"
  s = s.replace(/\b(?:[a-z][\s.\-_]){3,}[a-z]\b/g, m => m.replace(/[\s.\-_]/g, ''));
  const leet = s.replace(/[013457@$]/g, c => LEET[c] || c);
  return { plain: s, leet };
}

/**
 * Word-boundary substring match, so a short/common term like "ice", "pot",
 * or "meth" doesn't fire on "nice", "spot", "method". This does NOT use JS's
 * built-in \b - that only treats [A-Za-z0-9_] as "word characters", so it
 * finds no boundary at all around non-Latin scripts (Devanagari, Tamil,
 * Telugu, Kannada, Malayalam, Bengali, Gujarati, Gurmukhi, Urdu, Odia, ...),
 * which would make every regional-language lexicon term unmatchable.
 * Instead we use lookaround against \p{L}/\p{N} (any Unicode letter or
 * number), so a term surrounded by whitespace/punctuation/string-edges
 * matches in any script, while one embedded inside a longer word in that
 * same script does not.
 */
function wordBoundaryMatch(text, term) {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?<![\\p{L}\\p{N}])${escaped}(?![\\p{L}\\p{N}])`, 'u').test(text);
}

/** Standard Levenshtein edit distance. */
function lev(a, b) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      d[i][j] = Math.min(
        d[i - 1][j] + 1,
        d[i][j - 1] + 1,
        d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)
      );
    }
  }
  return d[a.length][b.length];
}

/** Pull out contact / payment identifiers that are common in sales messages. */
function extractIdentifiers(t) {
  const text = String(t);
  const digits = text.replace(/(\d)[\s\-.]+(?=\d)/g, '$1'); // "98765 43210" -> "9876543210"
  return {
    phones: [...new Set(digits.match(/(?:\+?91[\s-]?)?[6-9]\d{9}\b/g) || [])],
    emails: text.match(/[\w.+-]+@[\w-]+\.[\w.]+/g) || [],
    upi: text.match(/\b[\w.\-]{2,}@(?:oksbi|okhdfc|okicici|okaxis|ybl|paytm|upi|ibl|axl)\b/gi) || [],
    wallets: [
      // Base58 excludes 0 (zero), O, I, and lowercase l - the old class let all of
      // those through, so it could "match" strings that aren't valid addresses.
      ...(text.match(/\b(?:bc1|[13])[a-km-zA-HJ-NP-Z1-9]{25,39}\b/g) || []),
      ...(text.match(/\b0x[a-fA-F0-9]{40}\b/g) || [])
    ],
    urls: text.match(/https?:\/\/\S+|t\.me\/\S+|wa\.me\/\S+/gi) || []
  };
}

/**
 * Analyze a message and return an explainable risk score.
 * risk: 0-10 integer. level: low/medium/high. reasons: human-readable explanation trail.
 */
function analyze(text = '') {
  const { plain, leet } = normalize(text);
  // Split on anything that isn't a Unicode letter/number (not just a-z), so
  // words in regional-language scripts tokenize correctly too - a plain
  // [^a-z]+ split would silently throw away every non-Latin character
  // before fuzzy matching or intent-word detection ever ran.
  const words = leet.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  const matches = [];
  const reasons = [];
  const cats = new Set();
  let base = 0;

  for (const { t, cat, w } of lex.terms) {
    const directHit = wordBoundaryMatch(plain, t) || wordBoundaryMatch(leet, t);
    // Terms >=5 chars: standard 1-edit-distance fuzzy match.
    // Terms of exactly 4 chars (e.g. "weed", "coke"): still worth catching typos,
    // but a plain 1-edit tolerance on a 4-letter word matches too many unrelated
    // words, so require the candidate word to be the *same length* (transposition/
    // substitution typos like "woed"/"coje", not insertions/deletions like "wed"/"wee").
    // Terms under 4 chars ("lsd") are too short for fuzzy matching to be reliable at all.
    const fuzzyHit =
      !directHit &&
      t.length >= 4 &&
      !t.includes(' ') &&
      words.some(x =>
        t.length >= 5
          ? Math.abs(x.length - t.length) <= 1 && lev(x, t) <= 1
          : x.length === t.length && lev(x, t) === 1
      );
    if (directHit || fuzzyHit) {
      matches.push({ term: t, type: cat, fuzzy: fuzzyHit });
      cats.add(cat);
      base = Math.max(base, w);
      reasons.push(
        fuzzyHit
          ? `Fuzzy-matched '${t}' (${cat}, weight ${w})`
          : `Matched '${t}' (${cat}, weight ${w})`
      );
    }
  }

  let emojiScore = 0;
  for (const { e, cat, w } of lex.emoji) {
    if (text.includes(e)) {
      emojiScore += w;
      cats.add(cat);
      matches.push({ term: e, type: 'emoji:' + cat });
      reasons.push(`Drug-coded emoji ${e} (${cat})`);
    }
  }

  const identifiers = extractIdentifiers(text);
  const hasId = !!(identifiers.phones.length || identifiers.upi.length || identifiers.wallets.length);
  const intentHits = lex.intent.filter(k => words.includes(k));
  const intent = intentHits.length;

  // Repetition rule: cue words like "packet"/"pillow" are harmless once, but a
  // message that keeps repeating them (e.g. "packet packet packets ready") is a
  // classic coded-sale pattern. Count every occurrence of the configured cue
  // words; at/over the threshold, treat it like a lexicon hit (base 5, +1 more
  // once it reaches threshold+2). Configured in lexicon.json under "repeat".
  const repCfg = lex.repeat || { threshold: 3, words: [] };
  const repSet = new Set(repCfg.words);
  const repHits = words.filter(x => repSet.has(x));
  if (repHits.length >= repCfg.threshold) {
    const repBase = repHits.length >= repCfg.threshold + 2 ? 6 : 5;
    base = Math.max(base, repBase);
    cats.add('slang');
    reasons.push(`Cue word(s) repeated ${repHits.length}x: ${[...new Set(repHits)].join(', ')}`);
  }
  const cueWordCount = repHits.length;
  let risk = base + Math.min(emojiScore, 3);
  if (risk > 0) {
    risk += Math.min(intent, 2);
    if (matches.length >= 3) risk += 1;
    if (hasId) risk += 1;
  }
  // Per spec: with no lexicon term/emoji match, identifiers and/or intent
  // words alone do not contribute to risk. risk stays 0 in that case.
  if (intent) reasons.push(`Sales/intent words: ${intentHits.join(', ')}`);
  if (hasId) reasons.push('Contact/payment identifier present');
  risk = Math.max(0, Math.min(10, risk));

  return {
    risk,
    level: risk >= 7 ? 'high' : risk >= 4 ? 'medium' : 'low',
    categories: [...cats],
    matches,
    identifiers,
    reasons
  };
}

module.exports = { analyze, normalize, extractIdentifiers, lev };
