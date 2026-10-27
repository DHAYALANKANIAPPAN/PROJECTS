'use strict';

const assert = require('assert');
const { analyze, extractIdentifiers } = require('../lib/detector');
const { buildGraph } = require('../lib/network');

// --- Section 1: the 10 sample messages from the original spec, verbatim ---
// Each is checked against the concrete behavior the spec asked for, not just
// a high/low tier, so a silent regression in risk math trips a real failure.
const specCases = [
  {
    text: 'heroin, mdma cocaine and kanja', note: 'spec #1: multi-term stack, expect >=8',
    check: r => r.risk >= 8
  },
  {
    text: 'h e r o i n available call 98765 43210', note: 'spec #2: spaced letters -> high, plus phone extracted',
    check: r => r.level === 'high' && r.identifiers.phones.length === 1 && r.identifiers.phones[0] === '9876543210'
  },
  {
    text: 'c0caine 1 gram', note: 'spec #3: leetspeak decode',
    check: r => r.matches.some(m => m.term === 'cocaine')
  },
  {
    text: 'k@nja stock', note: 'spec #4: leetspeak cannabis slang',
    check: r => r.matches.some(m => m.term === 'kanja')
  },
  {
    text: '❄️ available dm me', note: 'spec #5: emoji + intent, no lexicon term',
    check: r => r.matches.some(m => m.term === '❄️') && r.risk > 0
  },
  {
    text: 'pay me on seller@ybl for maal', note: 'spec #6: UPI handle + slang term',
    check: r => r.identifiers.upi.length === 1 && r.matches.some(m => m.term === 'maal')
  },
  {
    text: "let's meet for lunch", note: 'spec #7: harmless, expect 0',
    check: r => r.risk === 0
  },
  {
    text: 'I love my dog', note: 'spec #8: harmless, expect 0',
    check: r => r.risk === 0
  },
  {
    // KNOWN LIMITATION, flagged in the spec itself for discussion rather than
    // silent "fix": "coke" is a direct lexicon hit (weight 6, cat stimulant),
    // so "coke zero is cold" currently scores medium, not low. Narrowing the
    // match (e.g. requiring an intent/identifier co-occurrence before "coke"
    // alone counts) would suppress this false positive but would also make
    // the term-alone signal weaker everywhere else - that's a product
    // trade-off, not a bug, so this is asserted at its *actual* behavior with
    // the caveat left visible, instead of quietly asserting the spec's wish.
    text: 'coke zero is cold', note: 'spec #9: known false-positive on "coke" - NEEDS TEAM DISCUSSION, see comment above',
    check: r => r.matches.some(m => m.term === 'coke') && r.level !== 'high'
  },
  {
    text: 'bhai maal available hai, dm kar de rate ke liye', note: 'spec #10: Hinglish example',
    check: r => r.matches.some(m => m.term === 'maal') && r.risk > 0
  }
];

let specPassed = 0;
for (const c of specCases) {
  const r = analyze(c.text);
  const ok = c.check(r);
  console.log(
    `${ok ? 'PASS' : 'FAIL'} [${c.note}] "${c.text}" -> risk=${r.risk} level=${r.level}` +
      (r.reasons.length ? `\n       reasons: ${r.reasons.join(' | ')}` : '')
  );
  if (ok) specPassed++;
  else assert.fail(`spec case failed: ${c.note}`);
}
console.log(`\n${specPassed}/${specCases.length} spec-sample cases matched expected behavior\n`);

// --- Section 2: broader risk-tier coverage across categories/evasion styles ---
const cases = [
  { text: 'h e r o i n available tonight', expectHigh: true, note: 'spaced-out letters' },
  { text: 'got fresh c0caine, dm for rate', expectHigh: true, note: 'leetspeak' },
  { text: 'k@nja stock ready, price 500/gram', expectHigh: true, note: 'leetspeak cannabis' },
  { text: '❄️ available, cod ok, call 9876543210', expectHigh: false, note: 'emoji + phone + intent (medium: emoji base is capped low)' },
  { text: 'mdma molly stock available delivery cod', expectHigh: true, note: 'multi-term stack' },
  { text: 'weed maal ready, dm 9988776655', expectHigh: false, note: 'medium: slang + weak term' },
  { text: 'charas available, pickup only', expectHigh: true, note: 'weight-5 term + 2 intent words crosses threshold' },
  { text: 'I love my sister a lot, she gave me some stuff to eat', expectHigh: false, note: 'false-positive control (weak term, no intent)' },
  { text: 'the weather today is really nice for a walk', expectHigh: false, note: 'harmless, unrelated' },
  { text: 'lsd trip report from last weekend, no sales talk here', expectHigh: true, note: 'high-weight term alone (8) already crosses high threshold, even without intent/id' },
  { text: 'fentanyl batch ready, dm for price', expectHigh: true, note: 'max-weight (10) opioid term' },
  { text: 'k2 spray on paper, available now', expectHigh: true, note: 'synthetic cannabinoid' }
];

let passed = 0;
for (const c of cases) {
  const r = analyze(c.text);
  const isHigh = r.level === 'high';
  const ok = isHigh === c.expectHigh;
  console.log(
    `${ok ? 'PASS' : 'FAIL'} [${c.note}] "${c.text}" -> risk=${r.risk} level=${r.level}` +
      (r.reasons.length ? `\n       reasons: ${r.reasons.join(' | ')}` : '')
  );
  if (ok) passed++;
}

console.log(`\n${passed}/${cases.length} cases matched expected risk tier`);

// hard assertions on a couple of unambiguous cases so `node test/detector.test.js`
// exits non-zero on real regressions
assert.strictEqual(analyze('heroin available, dm now').level, 'high');
assert.strictEqual(analyze('the weather today is really nice for a walk').level, 'low');
assert.ok(analyze('❄️ available, cod ok, call 9876543210').identifiers.phones.length === 1);

// --- Regression tests for bugs fixed in this pass ---

// Per spec: identifiers and/or intent words alone (no lexicon term/emoji
// hit) score exactly 0 - only a lexicon/emoji match establishes a base risk.
{
  const r = analyze('price 500, cod, dm 9876543210');
  assert.strictEqual(r.risk, 0, 'identifier+intent-only message should score 0 per spec');
  assert.strictEqual(r.level, 'low');
}
assert.strictEqual(analyze('stock available, pickup only').level, 'low');
// A bare phone number with no other signal stays low too.
assert.strictEqual(analyze('9876543210').level, 'low');

// Bug: fuzzy matching only kicked in for terms >=5 chars, so short-but-serious
// terms like "weed"/"coke" got no typo tolerance at all.
{
  const r = analyze('woed available dm'); // substitution typo of "weed"
  assert.ok(r.matches.some(m => m.term === 'weed' && m.fuzzy));
}
// Guard against the obvious false-positive risk of lowering that threshold:
// an unrelated short word must not fuzzy-match.
assert.strictEqual(analyze('wee available dm').matches.length, 0);

// Bug: the wallet regex's base58 character class wrongly allowed '0' and
// lowercase 'l', which real base58 addresses never contain.
{
  const ids = extractIdentifiers('fake 10OI1eP5QGefi2DMPTfTL5SLmv7DivfNa');
  assert.strictEqual(ids.wallets.length, 0, 'string containing base58-excluded chars should not match');
}
{
  const ids = extractIdentifiers('wallet 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa');
  assert.strictEqual(ids.wallets.length, 1, 'a valid-looking base58 address should still match');
}

// Bug: network.js graphed raw edge count as "degree", so an account posting
// 4+ times in a single group (no fan-out at all) got mislabeled 'supplier?'.
{
  const repeatedSameChat = Array.from({ length: 5 }, () => ({
    userId: 'u1', username: 'sameuser', chatId: 'c1', chatTitle: 'onegroup',
    risk: 5, identifiers: { phones: [], emails: [], upi: [], wallets: [] }
  }));
  const g1 = buildGraph(repeatedSameChat);
  const acct1 = g1.nodes.find(n => n.id === 'user:u1');
  assert.strictEqual(acct1.role, 'buyer/promoter?', 'repeated posts in one group should not look like fan-out');

  const fannedOut = ['c1', 'c2', 'c3', 'c4'].map(chatId => ({
    userId: 'u2', username: 'realfanout', chatId, chatTitle: chatId,
    risk: 5, identifiers: { phones: [], emails: [], upi: [], wallets: [] }
  }));
  const g2 = buildGraph(fannedOut);
  const acct2 = g2.nodes.find(n => n.id === 'user:u2');
  assert.strictEqual(acct2.role, 'supplier?', 'genuine fan-out across distinct groups should still flag');
}

// --- Regression test: api/detect.js must persist the full shared data
// contract (platform, chatId, chatTitle, userId, username, text, mediaType,
// ts, risk, level, categories, matches, identifiers, reasons, imageLabels),
// or Akshiya's Telegram writes and Lingesh's Instagram/image writes land in
// the same collection with mismatched shapes and break the network graph.
{
  const { createDetectRouter } = require('../api/detect');
  const express = require('express');
  const http = require('http');

  const saved = [];
  const fakeStore = { saveDetection: async rec => { saved.push(rec); } };
  const app = express();
  app.use('/api', createDetectRouter(fakeStore));
  const server = app.listen(0);
  const port = server.address().port;

  const body = JSON.stringify({
    text: 'heroin available, dm now',
    userId: 'u1', username: 'seller1', chatId: 'c1', chatTitle: 'test group',
    platform: 'telegram', mediaType: 'text', ts: '2026-01-01T00:00:00.000Z'
  });

  const req = http.request(
    { host: 'localhost', port, path: '/api/detect', method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } },
    res => {
      res.on('data', () => {});
      res.on('end', () => {
        const REQUIRED_FIELDS = [
          'platform', 'chatId', 'chatTitle', 'userId', 'username', 'text',
          'mediaType', 'ts', 'risk', 'level', 'categories', 'matches',
          'identifiers', 'reasons', 'imageLabels'
        ];
        assert.strictEqual(saved.length, 1, 'detection should have been persisted');
        for (const field of REQUIRED_FIELDS) {
          assert.ok(field in saved[0], `saved record missing contract field: ${field}`);
        }
        assert.strictEqual(saved[0].platform, 'telegram');
        console.log('PASS data-contract fields all present on saved record');
        server.close();
        console.log('\nAll hard assertions passed (including regression tests for fixed bugs).');
      });
    }
  );
  req.write(body);
  req.end();
}
