const { getDb } = require('../../lib/db');
const { analyze } = require('../../lib/detector');

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).send('Method Not Allowed');
  }

  const { username, text, mediaType } = req.body;
  if (!username || !text) {
    return res.status(400).json({ error: 'username and text are required' });
  }

  const a = analyze(text);
  const db = await getDb();

  const doc = {
    platform: 'instagram',
    chatId: 'IG DM (simulated)',
    chatTitle: 'IG DM (simulated)',
    userId: username,
    username: username,
    text: text,
    mediaType: mediaType || 'text',
    ts: new Date(),
    risk: a.risk,
    level: a.level,
    categories: a.categories,
    matches: a.matches,
    identifiers: a.identifiers,
    reasons: a.reasons,
    imageLabels: [],
    simulated: true
  };

  if (a.risk > 0) {
    await db.collection('detections').insertOne(doc);
  }

  res.json({ ok: true, inserted: a.risk > 0, risk: a.risk });
};