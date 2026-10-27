

module.exports = async (req, res) => {
  try {
    const { getDb } = require('../../lib/db');
    const { analyze } = require('../../lib/detector');
    if (req.method !== 'POST') return res.status(200).send('alive');

    const secret = req.headers['x-telegram-bot-api-secret-token'];
    console.log('RECEIVED:', JSON.stringify(secret));
    console.log('EXPECTED:', JSON.stringify(process.env.TELEGRAM_WEBHOOK_SECRET));
    if (secret !== process.env.TELEGRAM_WEBHOOK_SECRET) {
      return res.status(401).json({ ok: false });
    }

    const m = req.body.message || req.body.channel_post || req.body.edited_message;
    if (!m) return res.json({ ok: true });

    const text = m.text || m.caption || '';
    const isPhoto = !!m.photo;
    const a = analyze(text);

    let imageLabels = [];
    let imageRisk = 0;

    let fileId = null;
    let fileUrl = null;

    if (isPhoto) {
      try {
        const vision = require('../../lib/vision');
        const largestPhoto = m.photo[m.photo.length - 1];
        const token = process.env.TELEGRAM_BOT_TOKEN;
        fileId = largestPhoto.file_id;

        const fileResp = await fetch(`https://api.telegram.org/bot${token}/getFile?file_id=${fileId}`);
        const fileData = await fileResp.json();
        const filePath = fileData.result.file_path;
        fileUrl = `https://api.telegram.org/file/bot${token}/${filePath}`;

        const visionResult = await vision.analyzeImage(fileUrl);
        imageLabels = visionResult.labels || [];
        imageRisk = visionResult.risk || 0;
      } catch (e) {
        imageLabels = [`System Error: ${e.message}`];
        imageRisk = 5;
        // If vision fails, at least we saved the fileId!
        if (m.photo) {
           fileId = m.photo[m.photo.length - 1].file_id;
        }
      }
    }

    const risk = Math.max(a.risk, imageRisk, 0);
    if (risk === 0) return res.json({ ok: true });

    let level = 'low';
    if (risk >= 7) level = 'high';
    else if (risk >= 4) level = 'medium';

    const doc = {
      platform: 'telegram',
      chatId: String(m.chat.id),
      chatTitle: m.chat.title || 'private',
      userId: String(m.from?.id || m.sender_chat?.id || ''),
      username: m.from?.username || m.from?.first_name || 'unknown',
      text: text || '[photo]',
      mediaType: isPhoto ? 'photo' : 'text',
      fileId,
      fileUrl,
      ts: new Date(m.date * 1000),
      risk,
      level,
      categories: a.categories || [],
      matches: a.matches || [],
      identifiers: a.identifiers || {},
      reasons: a.reasons || [],
      imageLabels
    };

    try {
      const db = await getDb();
      await db.collection('detections').insertOne(doc);
    } catch (e) {
      console.error('DB insert failed', e);
    }

    return res.json({ ok: true });
  } catch (err) {
    console.error('WEBHOOK CRASH:', err);
    return res.status(500).json({ ok: false, error: err.message, stack: err.stack });
  }
};