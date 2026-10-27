'use strict';

const { MongoClient } = require('mongodb');

async function createMongoStore({
  uri = process.env.MONGODB_URI,
  dbName = process.env.MONGODB_DB || 'narcox',
  collectionName = 'detections'
} = {}) {
  if (!uri) {
    throw new Error('createMongoStore: MONGODB_URI is not set');
  }

  const client = new MongoClient(uri, {
    serverSelectionTimeoutMS: 8000
  });

  await client.connect();

  const db = client.db(dbName);
  const detections = db.collection(collectionName);

  await Promise.all([
    detections.createIndex({ risk: 1, ts: -1 }),
    detections.createIndex({ userId: 1 }),
    detections.createIndex({ chatId: 1 })
  ]);

  return {
    async saveDetection(record) {
      await detections.insertOne({
        ...record,
        createdAt: record.createdAt
          ? new Date(record.createdAt)
          : new Date()
      });
    },

    async getDetections({
      minRisk = 0,
      sinceDays = 30
    } = {}) {
      const cutoff = new Date(
        Date.now() - sinceDays * 24 * 60 * 60 * 1000
      );

      const rows = await detections
        .find({
          risk: { $gte: minRisk },
          ts: { $gte: cutoff }
        })
        .sort({ ts: -1 })
        .toArray();

      return rows.map(({ _id, ...rest }) => rest);
    },

    async getUserActivity(
      userId,
      { sinceDays = 7 } = {}
    ) {
      const cutoff = new Date(
        Date.now() - sinceDays * 24 * 60 * 60 * 1000
      );

      const docs = await detections
        .aggregate([
          { $match: { userId } },
          {
            $addFields: {
              _tsDate: { $toDate: '$ts' }
            }
          },
          {
            $match: {
              _tsDate: { $gte: cutoff }
            }
          },
          {
            $project: {
              _id: 0,
              chatId: 1,
              risk: 1,
              cueWordCount: 1,
              identifiers: 1
            }
          }
        ])
        .toArray();

      const chats = new Set();

      let maxMsgRisk = 0;
      let cueWordTotal = 0;

      const idChats = new Map();

      for (const d of docs) {
        chats.add(d.chatId);

        maxMsgRisk = Math.max(
          maxMsgRisk,
          d.risk || 0
        );

        cueWordTotal += d.cueWordCount || 0;

        for (const [kind, values] of Object.entries(
          d.identifiers || {}
        )) {
          if (kind === 'urls') continue;

          for (const v of values || []) {
            const key = `${kind}:${v}`;

            if (!idChats.has(key)) {
              idChats.set(key, new Set());
            }

            idChats.get(key).add(d.chatId);
          }
        }
      }

      return {
        messageCount: docs.length,
        chatCount: chats.size,
        cueWordTotal,
        maxMsgRisk,
        reusedIdentifierAcrossChats: [
          ...idChats.values()
        ].some((s) => s.size > 1)
      };
    },

    async close() {
      await client.close();
    },

    _client: client,
    _collection: detections
  };
}

let _cachedClient = null;
let _cachedDb = null;

async function getDb({
  uri = process.env.MONGODB_URI,
  dbName = process.env.MONGODB_DB || 'narcox'
} = {}) {
  if (_cachedDb) {
    return _cachedDb;
  }

  if (!uri) {
    throw new Error('getDb: MONGODB_URI is not set');
  }

  _cachedClient = new MongoClient(uri, {
    serverSelectionTimeoutMS: 8000
  });

  await _cachedClient.connect();

  _cachedDb = _cachedClient.db(dbName);

  return _cachedDb;
}

module.exports = {
  createMongoStore,
  getDb
};