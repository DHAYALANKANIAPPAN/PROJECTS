'use strict';

function scoreUserBehavior(activity = {}) {
  const { messageCount = 0, chatCount = 0, cueWordTotal = 0, maxMsgRisk = 0, reusedIdentifierAcrossChats = false } = activity;
  let risk = 0;
  const reasons = [];
  if (messageCount >= 10) { risk += 2; reasons.push(`${messageCount} flagged messages in window`); }
  else if (messageCount >= 5) { risk += 1; reasons.push(`${messageCount} flagged messages in window`); }
  if (chatCount >= 4) { risk += 4; reasons.push(`Active in ${chatCount} different groups`); }
  else if (chatCount >= 2) { risk += 2; reasons.push(`Active in ${chatCount} different groups`); }
  if (cueWordTotal >= 8) { risk += 4; reasons.push(`Cue words repeated ${cueWordTotal} times across messages`); }
  else if (cueWordTotal >= 3) { risk += 2; reasons.push(`Cue words repeated ${cueWordTotal} times across messages`); }
  if (reusedIdentifierAcrossChats) { risk += 3; reasons.push('Same phone/UPI/wallet reused across more than one group'); }
  risk = Math.max(0, Math.min(10, risk));
  risk = Math.max(risk, Math.min(10, maxMsgRisk));
  return { risk, level: risk >= 7 ? 'high' : risk >= 4 ? 'medium' : 'low', reasons };
}

module.exports = { scoreUserBehavior };