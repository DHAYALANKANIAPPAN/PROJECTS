'use strict';

const express = require('express');
const { analyze } = require('../lib/detector');
const { scoreUserBehavior } = require('../lib/behavior');

const VALID_PLATFORMS = new Set(['telegram', 'instagram']);
const VALID_MEDIA_TYPES = new Set([
  'text',
  'image',
  'caption',
  'unknown'
]);

/**
 * POST /api/detect
 * body: {
 *   text, userId, username, chatId, chatTitle,
 *   platform,        // "telegram" | "instagram" - required to persist
 *   mediaType,       // "text" | "image" | "caption" | "unknown"
 *   ts,              // origin timestamp
 *   imageLabels      // string[] - image-analysis output
 * }
 *
 * Runs the detector on `text`, optionally persists the detection via
 * `store.saveDetection(record)`, and always returns the analysis.
 */
function createDetectRouter(store) {
  const router = express.Router();

  router.post(
    '/detect',
    express.json({ limit: '20kb' }),
    async (req, res) => {
      const {
        text,
        userId,
        username,
        chatId,
        chatTitle,
        platform,
        mediaType,
        ts,
        imageLabels
      } = req.body || {};

      if (typeof text !== 'string' || !text.trim()) {
        return res.status(400).json({
          error: 'text is required'
        });
      }

      if (text.length > 4000) {
        return res.status(413).json({
          error: 'text exceeds 4000 character limit'
        });
      }

      if (
        platform !== undefined &&
        !VALID_PLATFORMS.has(platform)
      ) {
        return res.status(400).json({
          error: `platform must be one of: ${[
            ...VALID_PLATFORMS
          ].join(', ')}`
        });
      }

      if (
        mediaType !== undefined &&
        !VALID_MEDIA_TYPES.has(mediaType)
      ) {
        return res.status(400).json({
          error: `mediaType must be one of: ${[
            ...VALID_MEDIA_TYPES
          ].join(', ')}`
        });
      }

      if (
        imageLabels !== undefined &&
        !Array.isArray(imageLabels)
      ) {
        return res.status(400).json({
          error: 'imageLabels must be an array of strings'
        });
      }

      const result = analyze(text);

      let behavior = null;

      // Persisting needs enough identity to be useful later
      // (network graph, per-account history).
      if (
        store &&
        userId != null &&
        chatId != null &&
        platform
      ) {
        try {
          await store.saveDetection({
            platform,
            chatId,
            chatTitle: chatTitle || 'unknown',
            userId,
            username: username || 'unknown',
            text,
            mediaType: mediaType || 'text',
            ts: ts
              ? new Date(ts).toISOString()
              : new Date().toISOString(),

            risk: result.risk,
            level: result.level,
            categories: result.categories,
            matches: result.matches,
            identifiers: result.identifiers,
            reasons: result.reasons,
            cueWordCount: result.cueWordCount,
            imageLabels: imageLabels || [],

            createdAt: new Date().toISOString()
          });

          // Calculate user behavior after the detection
          // has been successfully saved.
          if (
            typeof store.getUserActivity === 'function'
          ) {
            const activity =
              await store.getUserActivity(
                userId,
                { sinceDays: 7 }
              );

            behavior = scoreUserBehavior(activity);
          }
        } catch (err) {
          console.error(
            'failed to persist detection:',
            err
          );

          // Don't fail the request just because
          // persistence or behavior calculation failed.
        }
      }

      res.json(
        behavior
          ? { ...result, behavior }
          : result
      );
    }
  );

  return router;
}

module.exports = { createDetectRouter };