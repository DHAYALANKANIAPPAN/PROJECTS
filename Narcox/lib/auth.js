'use strict';

const crypto = require('crypto');

const SECRET = process.env.SESSION_SECRET || 'change-me-in-production';
const COOKIE_NAME = 'narcox_session';
const MAX_AGE_SECONDS = 60 * 60 * 12; // 12 hours

function getAllowedEmails() {
  return (process.env.ALLOWED_EMAILS || '')
    .split(',')
    .map(e => e.trim().toLowerCase())
    .filter(Boolean);
}

function isEmailAllowed(email) {
  if (!email) return false;
  return getAllowedEmails().includes(String(email).trim().toLowerCase());
}

function sign(value) {
  const hmac = crypto.createHmac('sha256', SECRET).update(value).digest('hex');
  return `${value}.${hmac}`;
}

function verify(signed) {
  if (!signed || !signed.includes('.')) return null;
  const idx = signed.lastIndexOf('.');
  const value = signed.slice(0, idx);
  const sig = signed.slice(idx + 1);
  const expected = crypto.createHmac('sha256', SECRET).update(value).digest('hex');
  if (sig.length !== expected.length) return null;
  const ok = crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected));
  return ok ? value : null;
}

function createSessionCookie(email) {
  const payload = JSON.stringify({ email, exp: Date.now() + MAX_AGE_SECONDS * 1000 });
  const token = sign(Buffer.from(payload).toString('base64url'));
  return `${COOKIE_NAME}=${token}; HttpOnly; Secure; SameSite=Lax; Max-Age=${MAX_AGE_SECONDS}; Path=/`;
}

function clearSessionCookie() {
  return `${COOKIE_NAME}=; HttpOnly; Secure; SameSite=Lax; Max-Age=0; Path=/`;
}

function readSession(req) {
  const cookieHeader = req.headers.cookie || '';
  const match = cookieHeader.split(';').map(c => c.trim()).find(c => c.startsWith(`${COOKIE_NAME}=`));
  if (!match) return null;

  const token = match.slice(COOKIE_NAME.length + 1);
  const value = verify(token);
  if (!value) return null;

  try {
    const payload = JSON.parse(Buffer.from(value, 'base64url').toString('utf8'));
    if (!payload.exp || Date.now() > payload.exp) return null;
    return payload;
  } catch {
    return null;
  }
}

module.exports = {
  isEmailAllowed,
  createSessionCookie,
  clearSessionCookie,
  readSession,
  COOKIE_NAME
};
