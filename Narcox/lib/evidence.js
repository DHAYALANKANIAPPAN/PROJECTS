'use strict';

const crypto = require('crypto');

function buildPackage(detection, officer) {
  const content = {
    platform: detection.platform,
    userId: detection.userId,
    chatId: detection.chatId,
    text: detection.text
  };

  const canonical = JSON.stringify(content, Object.keys(content).sort());
  const packageHash = crypto.createHash('sha256').update(canonical).digest('hex');

  return {
    detectionId: String(detection._id),
    packageHash,
    verified: true,
    content,
    custody: [
      { action: 'CAPTURED', by: 'system', at: detection.ts || detection.createdAt },
      { action: 'PACKAGED', by: officer || 'system', at: new Date().toISOString() }
    ]
  };
}

function verifyPackage(evidenceDoc) {
  const canonical = JSON.stringify(evidenceDoc.content, Object.keys(evidenceDoc.content).sort());
  const recomputed = crypto.createHash('sha256').update(canonical).digest('hex');
  return recomputed === evidenceDoc.packageHash;
}

module.exports = { buildPackage, verifyPackage };
