'use strict';

/**
 * Returns req.body if something already parsed it (Vercel's Node runtime
 * does this automatically; Express does too when json middleware runs).
 * Otherwise reads and JSON-parses the raw request stream, resolving to {}
 * on any read/parse failure so callers never have to special-case a
 * malformed or empty body.
 */
function readJsonBody(req) {
  if (req.body && typeof req.body === 'object') {
    return Promise.resolve(req.body);
  }
  if (typeof req.on !== 'function') {
    return Promise.resolve({});
  }
  return new Promise(resolve => {
    let raw = '';
    req.on('data', chunk => { raw += chunk; });
    req.on('end', () => {
      if (!raw) return resolve({});
      try {
        resolve(JSON.parse(raw));
      } catch {
        resolve({});
      }
    });
    req.on('error', () => resolve({}));
  });
}

module.exports = { readJsonBody };
