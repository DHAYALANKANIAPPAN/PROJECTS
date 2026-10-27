const { getDb } = require('../lib/db');

module.exports = async (req, res) => {
  try {
    const db = await getDb();
    const minRisk = parseInt(req.query.minRisk) || 0;
    const days = parseInt(req.query.days) || 30;
    const platform = req.query.platform;
    const limit = parseInt(req.query.limit) || 100;

    const since = new Date();
    since.setDate(since.getDate() - days);

    const query = { ts: { $gte: since }, risk: { $gte: minRisk } };
    if (platform) {
      query.platform = platform;
    }

    const detections = await db.collection('detections')
      .find(query)
      .sort({ ts: -1 })
      .limit(limit)
      .toArray();

    res.status(200).json(detections);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};
