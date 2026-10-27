'use strict';

/**
 * Build a graph of accounts <-> groups <-> shared identifiers from a list of
 * detection records. Each detection is expected to have:
 *   { userId, username, chatId, chatTitle, risk, identifiers }
 * where identifiers matches the shape returned by detector.extractIdentifiers.
 */
function buildGraph(dets) {
  const nodes = new Map();
  const edges = [];
  // Tracks *distinct* neighbors per node, separate from the raw edges array.
  // Repeated messages from the same user in the same chat push multiple
  // 'posts_in' edges (useful for edge weight / frequency), but that must not
  // inflate the degree used for the supplier heuristic below - otherwise an
  // account that just posts often in one group looks identical to one that
  // actually fans out across many groups/identifiers.
  const neighbors = new Map();

  const add = (id, type, label, risk = 0) => {
    const n = nodes.get(id) || { id, type, label, risk: 0, count: 0 };
    n.risk = Math.max(n.risk, risk);
    n.count++;
    nodes.set(id, n);
  };

  const link = (from, to, kind) => {
    edges.push({ from, to, kind });
    if (!neighbors.has(from)) neighbors.set(from, new Set());
    if (!neighbors.has(to)) neighbors.set(to, new Set());
    neighbors.get(from).add(to);
    neighbors.get(to).add(from);
  };

  for (const d of dets) {
    const u = `user:${d.userId}`;
    const c = `chat:${d.chatId}`;
    add(u, 'account', '@' + d.username, d.risk);
    add(c, 'group', d.chatTitle, d.risk);
    link(u, c, 'posts_in');

    const idf = d.identifiers || {};
    for (const [k, arr] of Object.entries(idf)) {
      if (k === 'urls') continue; // urls are too noisy/ambiguous to graph as identity nodes
      for (const v of arr || []) {
        const i = `${k}:${v}`;
        add(i, k, v, d.risk);
        link(u, i, 'uses');
      }
    }
  }

  // role hint: accounts touching many distinct groups/identifiers are likely suppliers
  nodes.forEach(n => {
    n.degree = neighbors.get(n.id) ? neighbors.get(n.id).size : 0;
    n.role = n.type === 'account' ? (n.degree >= 4 ? 'supplier?' : 'buyer/promoter?') : undefined;
  });

  return { nodes: [...nodes.values()], edges };
}

module.exports = { buildGraph };
