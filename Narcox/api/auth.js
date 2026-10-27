'use strict';

const { isEmailAllowed, createSessionCookie, clearSessionCookie, readSession } = require('../lib/auth');

module.exports = async (req, res) => {
  const action = req.query.action;

  if (action === 'login' && req.method === 'POST') {
    const { email } = req.body || {};
    if (!email || typeof email !== 'string') {
      return res.status(400).json({ error: 'email is required' });
    }
    if (!isEmailAllowed(email)) {
      return res.status(403).json({ error: 'this email is not authorized' });
    }
    res.setHeader('Set-Cookie', createSessionCookie(email.trim().toLowerCase()));
    return res.status(200).json({ ok: true, email: email.trim().toLowerCase() });
  }

  if (action === 'logout') {
    res.setHeader('Set-Cookie', clearSessionCookie());
    return res.status(200).json({ ok: true });
  }

  // default: 'me' - check session
  const session = readSession(req);
  if (!session) {
    return res.status(401).json({ authenticated: false });
  }
  return res.status(200).json({ authenticated: true, email: session.email });
};
