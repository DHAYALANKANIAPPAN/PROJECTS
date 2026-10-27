'use strict';

const { analyze } = require('./detector');

const MAX_TEXT_LENGTH = 4000;

/**
 * Run the existing, unmodified detector (`analyze` from lib/detector.js) on
 * a normalized message and, when enough identity info is present, persist
 * it via `store.saveDetection` using the exact same "detections" data
 * contract api/detect.js writes (platform, chatId, chatTitle, userId,
 * username, text, mediaType, ts, risk, level, categories, matches,
 * identifiers, reasons, imageLabels) - so records coming from the Telegram
 * and Instagram webhooks are indistinguishable, to the network graph and
 * dashboard, from ones posted straight to /api/detect.
 *
 * Designed to never throw: callers are webhook handlers that must still
 * ack the platform even if a field is missing or persistence fails.
 *
 * @param {object|null} store - anything shaped like memoryStore/db.js's
 *   store (saveDetection(record) -> Promise<void>), or null/undefined to
 *   skip persistence entirely (analysis is still returned).
 * @param {object} normalized
 * @returns {Promise<{ skipped: true, reason: string } | { skipped: false, persisted: boolean, result: object }>}
 */
async function ingestDetection(store, normalized = {}) {
  const {
    text, userId, username, chatId, chatTitle,
    platform, mediaType, ts, imageLabels
  } = normalized;

  if (typeof text !== 'string' || !text.trim()) {
    return { skipped: true, reason: 'no message text' };
  }
  const trimmedText = text.length > MAX_TEXT_LENGTH ? text.slice(0, MAX_TEXT_LENGTH) : text;

  const result = analyze(trimmedText);

  let persisted = false;
  if (store && userId != null && chatId != null && platform) {
    try {
      await store.saveDetection({
        platform,
        chatId,
        chatTitle: chatTitle || 'unknown',
        userId,
        username: username || 'unknown',
        text: trimmedText,
        mediaType: mediaType || 'text',
        ts: ts ? new Date(ts).toISOString() : new Date().toISOString(),
        risk: result.risk,
        level: result.level,
        categories: result.categories,
        matches: result.matches,
        identifiers: result.identifiers,
        reasons: result.reasons,
        imageLabels: imageLabels || [],
        createdAt: new Date().toISOString()
      });
      persisted = true;
    } catch (err) {
      console.error('failed to persist webhook detection:', err);
      // don't fail the webhook just because persistence failed
    }
  }

  return { skipped: false, persisted, result };
}

module.exports = { ingestDetection };
