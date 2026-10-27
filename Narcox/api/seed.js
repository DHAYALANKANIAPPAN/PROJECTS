const { getDb } = require('../lib/db');

module.exports = async (req, res) => {
  try {
    if (req.query.key !== process.env.TELEGRAM_WEBHOOK_SECRET) {
      return res.status(401).json({ error: "Unauthorized" });
    }

    const db = await getDb();
    
    const fakeDetections = [
      {
        platform: "telegram",
        chatId: "-100123456",
        chatTitle: "Shadow Market",
        userId: "445566",
        username: "vendor_x",
        text: "Got new pure mdma, dm for prices. W.app +447712345678",
        mediaType: "text",
        ts: new Date(),
        risk: 9,
        level: "high",
        categories: ["drugs", "sales"],
        matches: [{term: "mdma", type: "drug"}],
        identifiers: { phones: ["+447712345678"], emails: [], upi: [], wallets: [], urls: [] },
        reasons: ["Mentioned 'mdma'", "Provided phone number"],
        imageLabels: []
      },
      {
        platform: "instagram",
        chatId: "ig_post_8899",
        chatTitle: "Public Post",
        userId: "998877",
        username: "green_leaf_420",
        text: "Best strains in town, link in bio",
        mediaType: "photo",
        ts: new Date(Date.now() - 3600000),
        risk: 8,
        level: "high",
        categories: ["drugs"],
        matches: [{term: "strains", type: "drug_slang"}],
        identifiers: { phones: [], emails: [], upi: [], wallets: [], urls: [] },
        reasons: ["Mentioned 'strains'"],
        imageLabels: ["marijuana", "green"]
      },
      {
        platform: "telegram",
        chatId: "-100123456",
        chatTitle: "Shadow Market",
        userId: "112233",
        username: "curious_user",
        text: "Anyone know a good club?",
        mediaType: "text",
        ts: new Date(Date.now() - 86400000),
        risk: 2,
        level: "low",
        categories: [],
        matches: [],
        identifiers: { phones: [], emails: [], upi: [], wallets: [], urls: [] },
        reasons: ["No obvious threats"],
        imageLabels: []
      },
      {
        platform: "telegram",
        chatId: "-100789456",
        chatTitle: "Rave Central",
        userId: "445566",
        username: "vendor_x",
        text: "Discount on bulk pills today",
        mediaType: "text",
        ts: new Date(Date.now() - 7200000),
        risk: 7,
        level: "high",
        categories: ["drugs", "sales"],
        matches: [{term: "pills", type: "drug_slang"}],
        identifiers: { phones: [], emails: [], upi: [], wallets: [], urls: [] },
        reasons: ["Mentioned 'pills' in bulk context"],
        imageLabels: []
      }
    ];

    await db.collection('detections').insertMany(fakeDetections);

    res.status(200).json({ success: true, inserted: fakeDetections.length, message: "Fake data seeded!" });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};
