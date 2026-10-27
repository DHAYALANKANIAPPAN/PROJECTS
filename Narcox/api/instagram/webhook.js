const { getDb } = require('../../lib/db');
const { analyze } = require('../../lib/detector');
const vision = require('../../lib/vision');

module.exports = async function handler(req, res) {
  if (req.method === 'GET') {
    const mode = req.query['hub.mode'];
    const token = req.query['hub.verify_token'];
    const challenge = req.query['hub.challenge'];

    if (mode === 'subscribe' && token === process.env.IG_VERIFY_TOKEN) {
      return res.status(200).send(challenge);
    }
    return res.status(403).send('Forbidden');
  }

  if (req.method === 'POST') {
    const entries = req.body.entry || [];
    const items = [];

    for (const e of entries) {
      if (e.messaging) {
        for (const m of e.messaging) {
          if (m.message) {
            let text = m.message.text || '';
            let mediaType = 'text';
            let fileUrl = null;
            let isPhoto = false;

            if (m.message.attachments && m.message.attachments.length > 0) {
                const att = m.message.attachments[0];
                if (att.type === 'image') {
                    isPhoto = true;
                    mediaType = 'photo';
                    fileUrl = att.payload.url;
                    text = text || '[photo]';
                }
            }
            
            if (text || isPhoto) {
                items.push({
                  userId: String(m.sender.id),
                  username: String(m.sender.id),
                  text: text,
                  ts: new Date(m.timestamp),
                  mediaType: mediaType,
                  fileUrl: fileUrl,
                  isPhoto: isPhoto,
                  chat: 'IG DM'
                });
            }
          }
        }
      }

      if (e.changes) {
        for (const c of e.changes) {
          if (c.field === 'comments' && c.value && c.value.text) {
            items.push({
              userId: String(c.value.from.id),
              username: c.value.from.username,
              text: c.value.text,
              ts: new Date(),
              mediaType: 'comment',
              isPhoto: false,
              chat: 'IG post ' + c.value.media.id
            });
          }
        }
      }
    }

    const db = await getDb();

    for (const item of items) {
      const a = analyze(item.text);
      let imageLabels = [];
      let imageRisk = 0;

      if (item.isPhoto && item.fileUrl) {
          try {
             const visionResult = await vision.analyzeImage(item.fileUrl);
             imageLabels = visionResult.labels || [];
             imageRisk = visionResult.risk || 0;
          } catch (e) {
             console.error('IG Vision failed', e);
             imageLabels = [`System Error: ${e.message}`];
             imageRisk = 5;
          }
      }

      const risk = Math.max(a.risk, imageRisk, 0);
      if (risk === 0) continue;

      let level = 'low';
      if (risk >= 7) level = 'high';
      else if (risk >= 4) level = 'medium';

      await db.collection('detections').insertOne({
        platform: 'instagram',
        chatId: item.chat,
        chatTitle: item.chat,
        userId: item.userId,
        username: item.username,
        text: item.text,
        mediaType: item.mediaType,
        fileUrl: item.fileUrl || null,
        ts: item.ts,
        risk: risk,
        level: level,
        categories: a.categories || [],
        matches: a.matches || [],
        identifiers: a.identifiers || {},
        reasons: a.reasons || [],
        imageLabels: imageLabels
      });
    }

    return res.json({ ok: true });
  }

  res.status(405).send('Method Not Allowed');
};
