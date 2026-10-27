'use strict';

const { createMemoryStore } = require('./memoryStore');
const { createMongoStore } = require('./db');

/**
 * Lazily builds (and caches) the same store implementation server.js uses:
 * Mongo-backed when MONGODB_URI is set, otherwise the in-memory store.
 *
 * Serverless functions (Vercel) can reuse a warm module scope between
 * invocations on the same instance, so caching the store/connection here
 * avoids reconnecting to Mongo on every request while still working fine
 * cold (each cold start just rebuilds it once).
 */
let storePromise = null;

function getStore() {
  if (!storePromise) {
    storePromise = process.env.MONGODB_URI
      ? createMongoStore()
      : Promise.resolve(createMemoryStore());
  }
  return storePromise;
}

/** Test-only: drop the cached store so the next getStore() rebuilds it. */
function _resetStoreCache() {
  storePromise = null;
}

module.exports = { getStore, _resetStoreCache };
