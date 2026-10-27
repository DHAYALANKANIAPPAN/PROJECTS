const { getDb } = require('../lib/db');

module.exports = async (req, res) => {
  try {
    const db = await getDb();

    // ---- REPORT MODE ----
    // GET /api/stats?report=1&from=2026-09-01&to=2026-09-23&platform=telegram&minRisk=0
    if (req.query.report) {
      const from = req.query.from ? new Date(req.query.from) : new Date(Date.now() - 30 * 86400000);
      const to = req.query.to ? new Date(req.query.to) : new Date();
      const minRisk = Number(req.query.minRisk) || 0;
      const platform = req.query.platform;

      const query = { ts: { $gte: from, $lte: to }, risk: { $gte: minRisk } };
      if (platform) query.platform = platform;

      const rows = await db.collection('detections')
        .find(query)
        .sort({ ts: -1 })
        .toArray();

      const totalDetections = rows.length;
      const highRisk = rows.filter(r => r.risk >= 7).length;
      const mediumRisk = rows.filter(r => r.risk >= 4 && r.risk < 7).length;
      const lowRisk = rows.filter(r => r.risk < 4).length;

      const byPlatform = {};
      const byCategory = {};
      const keywordCounts = {};
      const accountCounts = {};

      rows.forEach(r => {
        byPlatform[r.platform] = (byPlatform[r.platform] || 0) + 1;
        (r.categories || []).forEach(c => { byCategory[c] = (byCategory[c] || 0) + 1; });
        (r.matches || []).forEach(m => { keywordCounts[m.term] = (keywordCounts[m.term] || 0) + 1; });
        const acct = r.username || r.userId;
        if (acct) accountCounts[acct] = (accountCounts[acct] || 0) + 1;
      });

      const topKeywords = Object.entries(keywordCounts)
        .sort((a, b) => b[1] - a[1]).slice(0, 10)
        .map(([term, count]) => ({ term, count }));

      const topAccounts = Object.entries(accountCounts)
        .sort((a, b) => b[1] - a[1]).slice(0, 10)
        .map(([account, count]) => ({ account, count }));

      // CSV export
      if (req.query.format === 'csv') {
        const header = 'Timestamp,Platform,Chat,User,Risk,Level,Categories,Text\n';
        const csvRows = rows.map(r => {
          const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
          return [
            esc(new Date(r.ts).toISOString()),
            esc(r.platform),
            esc(r.chatTitle),
            esc(r.username || r.userId),
            esc(r.risk),
            esc(r.level),
            esc((r.categories || []).join('; ')),
            esc(r.text)
          ].join(',');
        }).join('\n');

        res.setHeader('Content-Type', 'text/csv');
        res.setHeader('Content-Disposition', `attachment; filename="narcox-report-${Date.now()}.csv"`);
        return res.status(200).send(header + csvRows);
      }

      return res.status(200).json({
        range: { from, to },
        summary: { totalDetections, highRisk, mediumRisk, lowRisk },
        byPlatform,
        byCategory,
        topKeywords,
        topAccounts,
        detections: rows.map(({ _id, ...rest }) => rest)
      });
    }

    // ---- NORMAL DASHBOARD STATS MODE (unchanged) ----
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const totalAlerts = await db.collection('detections').countDocuments({ risk: { $gte: 7 }, ts: { $gte: thirtyDaysAgo } });
    const evidencePackages = await db.collection('evidence').countDocuments();

    const highRiskEntitiesArray = await db.collection('detections').distinct('userId', { risk: { $gte: 7 } });
    const highRiskEntities = highRiskEntitiesArray.length;

    const detections30d = await db.collection('detections').countDocuments({ ts: { $gte: thirtyDaysAgo } });
    const highRisk = totalAlerts;

    const byTypePipeline = [
      { $match: { ts: { $gte: thirtyDaysAgo } } },
      { $group: { _id: "$mediaType", count: { $sum: 1 } } }
    ];
    const byTypeResults = await db.collection('detections').aggregate(byTypePipeline).toArray();
    const byType = {};
    byTypeResults.forEach(r => { byType[r._id || 'unknown'] = r.count; });

    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    const trendPipeline = [
      { $match: { ts: { $gte: sevenDaysAgo } } },
      {
        $group: {
          _id: { $dateToString: { format: "%Y-%m-%d", date: "$ts" } },
          count: { $sum: 1 }
        }
      },
      { $sort: { _id: 1 } }
    ];
    const trend = await db.collection('detections').aggregate(trendPipeline).toArray();

    const recent = await db.collection('detections').find().sort({ ts: -1 }).limit(10).toArray();

    res.status(200).json({
      totalAlerts,
      evidencePackages,
      highRiskEntities,
      detections30d,
      highRisk,
      byType,
      trend,
      recent
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};
