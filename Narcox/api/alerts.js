const { getDb } = require('../lib/db');

module.exports = async (req, res) => {
  try {
    const db = await getDb();
    const alerts = await db.collection('detections')
      .find({ risk: { $gte: 7 } })
      .sort({ ts: -1 })
      .limit(50)
      .toArray();

    res.status(200).json(alerts);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};
