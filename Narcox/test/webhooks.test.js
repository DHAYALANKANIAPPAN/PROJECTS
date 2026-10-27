'use strict';

const assert = require('assert');
const http = require('http');
const express = require('express');

process.env.INSTAGRAM_VERIFY_TOKEN = 'test-verify-token';
delete process.env.MONGODB_URI; // force the in-memory store for this test run

const telegramWebhook = require('../api/telegram/webhook');
const instagramWebhook = require('../api/instagram/webhook');
const { getStore } = require('../lib/getStore');

// --- tiny helpers to drive the handlers over real HTTP, same approach the
// existing detect.js regression test uses -------------------------------

function buildApp() {
  const app = express();
  app.use(express.json({ limit: '1mb' }));
  app.all('/api/telegram/webhook', (req, res) => telegramWebhook(req, res));
  app.all('/api/instagram/webhook', (req, res) => instagramWebhook(req, res));
  return app;
}

function request(server, { method, path, body, headers = {} } = {}) {
  return new Promise((resolve, reject) => {
    const port = server.address().port;
    const payload = body !== undefined ? Buffer.from(body) : undefined;
    const req = http.request(
      {
        host: 'localhost',
        port,
        path,
        method,
        headers: payload
          ? { 'Content-Type': 'application/json', 'Content-Length': payload.length, ...headers }
          : headers
      },
      res => {
        let raw = '';
        res.on('data', chunk => { raw += chunk; });
        res.on('end', () => {
          let parsed;
          try { parsed = raw ? JSON.parse(raw) : undefined; } catch { parsed = raw; }
          resolve({ status: res.statusCode, body: parsed, raw });
        });
      }
    );
    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });
}

async function run() {
  const app = buildApp();
  const server = app.listen(0);
  await new Promise(resolve => server.once('listening', resolve));

  try {
    // --- 1. Telegram POST: normal group message with a high-risk term ---
    {
      const update = {
        update_id: 1,
        message: {
          message_id: 10,
          from: { id: 111, username: 'seller1', first_name: 'Sel' },
          chat: { id: -100222, title: 'Deals Group', type: 'supergroup' },
          date: 1700000000,
          text: 'heroin available, dm now'
        }
      };
      const { status, body } = await request(server, {
        method: 'POST', path: '/api/telegram/webhook', body: JSON.stringify(update)
      });
      assert.strictEqual(status, 200, 'telegram POST should ack with 200');
      assert.strictEqual(body.ok, true);
      assert.strictEqual(body.skipped, false);
      assert.strictEqual(body.result.level, 'high', 'heroin message should score high');
      assert.strictEqual(body.persisted, true, 'message had userId/chatId/platform so should persist');

      const store = await getStore();
      const saved = store._all.find(d => d.text === 'heroin available, dm now');
      assert.ok(saved, 'record should be persisted to the store');
      assert.strictEqual(saved.platform, 'telegram');
      assert.strictEqual(saved.userId, '111');
      assert.strictEqual(saved.username, 'seller1');
      assert.strictEqual(saved.chatId, '-100222');
      assert.strictEqual(saved.chatTitle, 'Deals Group');
      console.log('PASS telegram POST normalizes fields, runs detector, and persists');
    }

    // --- 2. Instagram GET verification (valid token) ---
    {
      const { status, raw } = await request(server, {
        method: 'GET',
        path: '/api/instagram/webhook?hub.mode=subscribe&hub.verify_token=test-verify-token&hub.challenge=abc123'
      });
      assert.strictEqual(status, 200);
      assert.strictEqual(raw, 'abc123', 'should echo back hub.challenge verbatim');
      console.log('PASS instagram GET verification succeeds and echoes challenge');
    }

    // --- 3. Instagram GET verification (invalid token) ---
    {
      const { status, body } = await request(server, {
        method: 'GET',
        path: '/api/instagram/webhook?hub.mode=subscribe&hub.verify_token=wrong-token&hub.challenge=abc123'
      });
      assert.strictEqual(status, 403, 'wrong verify token should be rejected');
      assert.ok(body.error);
      console.log('PASS instagram GET verification rejects invalid token');
    }

    // --- 4. Instagram POST: DM messaging event ---
    {
      const payload = {
        object: 'instagram',
        entry: [
          {
            id: 'ig-business-1',
            time: 1700000000,
            messaging: [
              {
                sender: { id: '9988' },
                recipient: { id: 'ig-business-1' },
                timestamp: 1700000000123,
                message: { mid: 'm_1', text: 'ice available, hit my dm' }
              }
            ]
          }
        ]
      };
      const { status, body } = await request(server, {
        method: 'POST', path: '/api/instagram/webhook', body: JSON.stringify(payload)
      });
      assert.strictEqual(status, 200);
      assert.strictEqual(body.ok, true);
      assert.strictEqual(body.eventCount, 1);
      assert.strictEqual(body.outcomes[0].result.level !== undefined, true);

      const store = await getStore();
      const saved = store._all.find(d => d.text === 'ice available, hit my dm');
      assert.ok(saved, 'instagram DM should be persisted');
      assert.strictEqual(saved.platform, 'instagram');
      assert.strictEqual(saved.userId, '9988');
      console.log('PASS instagram POST normalizes DM event, runs detector, and persists');
    }

    // --- 5. Malformed requests: should never crash, always 200 ---
    {
      // Telegram: valid JSON but no `message` at all.
      const r1 = await request(server, {
        method: 'POST', path: '/api/telegram/webhook', body: JSON.stringify({ update_id: 2 })
      });
      assert.strictEqual(r1.status, 200);
      assert.strictEqual(r1.body.skipped, true, 'update with no text should be skipped, not crash');

      // Telegram: empty body.
      const r2 = await request(server, {
        method: 'POST', path: '/api/telegram/webhook', body: ''
      });
      assert.strictEqual(r2.status, 200);

      // Instagram: entry with neither messaging nor changes.
      const r3 = await request(server, {
        method: 'POST', path: '/api/instagram/webhook', body: JSON.stringify({ object: 'instagram', entry: [{}] })
      });
      assert.strictEqual(r3.status, 200);
      assert.strictEqual(r3.body.eventCount, 0);

      // Instagram: totally empty body.
      const r4 = await request(server, {
        method: 'POST', path: '/api/instagram/webhook', body: '{}'
      });
      assert.strictEqual(r4.status, 200);
      assert.strictEqual(r4.body.eventCount, 0);

      // Wrong HTTP method on each.
      const r5 = await request(server, { method: 'GET', path: '/api/telegram/webhook' });
      assert.strictEqual(r5.status, 405);
      const r6 = await request(server, { method: 'PUT', path: '/api/instagram/webhook' });
      assert.strictEqual(r6.status, 405);

      console.log('PASS malformed/edge-case requests are handled without crashing');
    }

    console.log('\nAll webhook tests passed.');
  } finally {
    server.close();
  }
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
