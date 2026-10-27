'use strict';

const { ObjectId } = require('mongodb');
const { getDb } = require('../lib/db');
const { buildPackage, verifyPackage } = require('../lib/evidence');

module.exports = async (req, res) => {
  try {
    const db = await getDb();

    if (req.method === 'POST') {
      const { detectionId, officer } = req.body || {};
      if (!detectionId) {
        return res.status(400).json({ error: 'detectionId is required' });
      }

      const detection = await db.collection('detections')
        .findOne({ _id: new ObjectId(detectionId) });

      if (!detection) {
        return res.status(404).json({ error: 'detection not found' });
      }

      const evidenceDoc = buildPackage(detection, officer);
      await db.collection('evidence').insertOne(evidenceDoc);

      return res.status(201).json(evidenceDoc);
    }

    // GET - list all evidence, re-verifying each hash on read
    const rows = await db.collection('evidence')
      .find({})
      .sort({ 'custody.1.at': -1 })
      .toArray();

    const withVerification = rows.map(({ _id, ...rest }) => ({
      ...rest,
      verified: verifyPackage(rest)
    }));

    res.status(200).json(withVerification);
  } catch (err) {
    console.error('/api/evidence failed:', err);
    res.status(500).json({ error: 'evidence operation failed' });
  }
};
