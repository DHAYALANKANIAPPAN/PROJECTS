'use strict';

/**
 * Minimal in-memory implementation of the store interface used by
 * api/detect.js and api/network.js. Good for local dev / demo; swap for a
 * real DB-backed store in production (same methods).
 */
function createMemoryStore() {
  const detections = [];

  return {
    async saveDetection(record) {
      detections.push(record);
    },

    async getDetections({
      minRisk = 0,
      sinceDays = 30
    } = {}) {
      const cutoff =
        Date.now() - sinceDays * 24 * 60 * 60 * 1000;

      return detections.filter(
        d =>
          d.risk >= minRisk &&
          new Date(d.createdAt).getTime() >= cutoff
      );
    },

    async getUserActivity(
      userId,
      { sinceDays = 7 } = {}
    ) {
      const cutoff =
        Date.now() - sinceDays * 24 * 60 * 60 * 1000;

      const docs = detections.filter(
        d =>
          d.userId === userId &&
          new Date(
            d.ts || d.createdAt
          ).getTime() >= cutoff
      );

      const chats = new Set();

      let maxMsgRisk = 0;
      let cueWordTotal = 0;

      const idChats = new Map();

      for (const d of docs) {
        chats.add(d.chatId);

        maxMsgRisk = Math.max(
          maxMsgRisk,
          d.risk || 0
        );

        cueWordTotal += d.cueWordCount || 0;

        for (const [kind, values] of Object.entries(
          d.identifiers || {}
        )) {
          if (kind === 'urls') continue;

          for (const v of values || []) {
            const key = `${kind}:${v}`;

            if (!idChats.has(key)) {
              idChats.set(key, new Set());
            }

            idChats.get(key).add(d.chatId);
          }
        }
      }

      return {
        messageCount: docs.length,
        chatCount: chats.size,
        cueWordTotal,
        maxMsgRisk,
        reusedIdentifierAcrossChats: [
          ...idChats.values()
        ].some(s => s.size > 1)
      };
    },

    // Exposed for tests/demo seeding
    _all: detections
  };
}

module.exports = { createMemoryStore };