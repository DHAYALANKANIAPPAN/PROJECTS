module.exports = async (req, res) => {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) return res.json({ connected: false });

  try {
    const resp = await fetch(`https://api.telegram.org/bot${token}/getWebhookInfo`);
    const data = await resp.json();
    return res.json({
      connected: true,
      webhook: data.result.url,
      pending: data.result.pending_update_count
    });
  } catch (e) {
    return res.json({ connected: false });
  }
};