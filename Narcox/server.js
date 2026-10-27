'use strict';

const express = require('express');
const { createMemoryStore } = require('./lib/memoryStore');
const { createMongoStore } = require('./lib/db');
const { createDetectRouter } = require('./api/detect');
const { createNetworkRouter } = require('./api/network');

/**
 * Uses the Mongo-backed store when MONGODB_URI is set, otherwise falls back
 * to the in-memory store (local dev / demo / tests). Both implement the
 * same { saveDetection, getDetections } interface, so the routes below
 * don't need to know which one they got.
 */
async function buildApp() {
  const app = express();
  const store = process.env.MONGODB_URI
    ? await createMongoStore()
    : createMemoryStore();

  app.use('/api', createDetectRouter(store));
  app.use('/api', createNetworkRouter(store));

  app.get('/health', (req, res) => res.json({ ok: true }));

  return { app, store };
}

if (require.main === module) {
  buildApp()
    .then(({ app, store }) => {
      const port = process.env.PORT || 3000;
      const server = app.listen(port, () => console.log(`narcox listening on :${port}`));

      // Graceful shutdown: stop accepting new connections, then close the
      // Mongo client cleanly (memoryStore has no close(), so guard for it).
      // Without this, SIGTERM (e.g. on redeploy) kills in-flight requests
      // and leaves the Mongo connection pool dangling.
      const shutdown = signal => {
        console.log(`${signal} received, shutting down`);
        server.close(async () => {
          if (typeof store.close === 'function') {
            await store.close().catch(err => console.error('error closing store:', err));
          }
          process.exit(0);
        });
      };
      process.on('SIGTERM', () => shutdown('SIGTERM'));
      process.on('SIGINT', () => shutdown('SIGINT'));
    })
    .catch(err => {
      console.error('failed to start narcox:', err);
      process.exit(1);
    });
}

module.exports = { buildApp };
