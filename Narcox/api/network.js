'use strict';

const { createMongoStore } = require('../lib/db');
const { buildGraph } = require('../lib/network');

let storePromise;
function getStore() {
  if (!storePromise) storePromise = createMongoStore();
  return storePromise;
}

module.exports = async (req, res) => {
  try {
    const minRisk = Number(req.query.minRisk) || 4;
    const sinceDays = Number(req.query.sinceDays) || 30;

    const store = await getStore();
    const rows = await store.getDetections({ minRisk, sinceDays });

    res.status(200).json(buildGraph(rows));
  } catch (err) {
    console.error('GET /api/network failed:', err);
    res.status(500).json({ error: 'failed to build network graph' });
  }
};
