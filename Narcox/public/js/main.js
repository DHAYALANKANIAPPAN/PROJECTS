// public/js/main.js

async function updateDashboard() {
    // 1. Fetch our data! (This will read from mock.json for now)
    const stats = await API.get('/api/stats');
    
    if (stats) {
        // 2. Update the 4 top cards using the IDs we added earlier
        document.getElementById('stat-total-alerts').innerText = stats.totalAlerts;
        document.getElementById('stat-evidence').innerText = stats.evidencePackages;
        document.getElementById('stat-entities').innerText = stats.highRiskEntities;
        document.getElementById('stat-detections').innerText = stats.detections30d;
        
        // 3. Update the Recent Alerts Table
        const tbody = document.getElementById('recent-alerts-tbody');
        tbody.innerHTML = ''; // clear the old dummy rows
        
        // Loop over the new recent alerts and create HTML for them
        stats.recent.forEach(alert => {
            const tr = document.createElement('tr');
            tr.className = 'border-b border-gray-200 hover:bg-gray-50';
            
            tr.innerHTML = `
                <td class="py-3 px-4 font-mono text-sm">#${esc(alert._id.substring(0,6))}</td>
                <td class="py-3 px-4 capitalize">${esc(alert.platform)}</td>
                <td class="py-3 px-4">${esc(alert.username)}</td>
                <td class="py-3 px-4">${riskBadge(alert.risk)}</td>
                <td class="py-3 px-4 text-gray-500 truncate max-w-[200px]">${esc(alert.text)}</td>
            `;
            tbody.appendChild(tr);
        });
    }
}

let lastAlertsId = null;

async function updateAlerts() {
    const alerts = await API.get('/api/alerts');
    if (alerts && alerts.length > 0) {
        // Detect if there is a new alert we haven't seen yet!
        const newestId = alerts[0]._id;
        if (lastAlertsId !== null && newestId !== lastAlertsId) {
            // PLAY A BEEP SOUND
            const beep = new Audio('data:audio/mp3;base64,//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq');
            beep.play().catch(e => {}); // Ignore error if browser blocks autoplay
        }
        lastAlertsId = newestId;

        const tbody = document.getElementById('alerts-page-tbody');
        if(!tbody) return;
        tbody.innerHTML = '';
        
        alerts.forEach(alert => {
            const tr = document.createElement('tr');
            tr.className = 'border-b border-gray-200 hover:bg-gray-50';
            
            const timeStr = new Date(alert.ts).toLocaleTimeString();
            
            tr.innerHTML = `
                <td class="py-3 px-4 text-sm text-gray-500">${timeStr}</td>
                <td class="py-3 px-4 capitalize">${esc(alert.platform)}</td>
                <td class="py-3 px-4">${esc(alert.username)}</td>
                <td class="py-3 px-4">${riskBadge(alert.risk)}</td>
                <td class="py-3 px-4 text-gray-500">${esc(alert.text)}</td>
                <td class="py-3 px-4">
                    <button onclick="createEvidence('${alert._id}')" class="px-3 py-1 bg-blue-100 text-blue-600 rounded hover:bg-blue-200 text-xs font-medium transition-colors">
                        Create Evidence
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }
}

window.createEvidence = async (id) => {
    alert("Packaging evidence for Case #" + id.substring(0,6) + "...");
    await API.post('/api/evidence', { detectionId: id, officer: 'Durai Singam' });
    alert("Evidence securely packaged and cryptographically signed!");
};

async function updateTelegram() {
    // 1. Update webhook status
    const status = await API.get('/api/telegram/status');
    if (status) {
        document.getElementById('telegram-webhook-status').innerText = status.connected ? 'Active: ' + status.webhook : 'Disconnected';
    }

    // 2. Fetch detections table
    const minRisk = document.getElementById('tg-min-risk').value;
    const days = document.getElementById('tg-days').value;
    const detections = await API.get(`/api/detections?platform=telegram&minRisk=${minRisk}&days=${days}`);
    
    if (detections) {
        const tbody = document.getElementById('telegram-page-tbody');
        if(!tbody) return;
        tbody.innerHTML = '';
        
        if (detections.length === 0) {
            tbody.innerHTML = `<tr id="empty-state"><td colspan="5" class="py-6 text-center text-gray-500 font-medium">No active alerts</td></tr>`;
            return;
        }

        detections.forEach(det => {
            const tr = document.createElement('tr');
            tr.className = 'border-b border-gray-200 hover:bg-gray-50';
            const timeStr = new Date(det.ts).toLocaleTimeString();
            
            // Format explanations nicely
            const reasonsHtml = (det.reasons || []).map(r => `<li>- ${esc(r)}</li>`).join('');
            const imageHtml = (det.imageLabels && det.imageLabels.length > 0) ? `<li>?? AI found: ${esc(det.imageLabels.join(', '))}</li>` : '';
            const idents = det.identifiers || {};
            const phonesHtml = (idents.phones || []).map(p => `<li>📞 ${esc(p)}</li>`).join('');
            
            tr.innerHTML = `
                <td class="py-3 px-4 text-sm text-gray-500">${timeStr}</td>
                <td class="py-3 px-4">${esc(det.chatTitle)}</td>
                <td class="py-3 px-4">${esc(det.username)}</td>
                <td class="py-3 px-4">${riskBadge(det.risk)}</td>
                <td class="py-3 px-4">
                    <div>${esc(det.text)}</div>
                    <details class="mt-2 text-xs text-gray-500 bg-gray-100 p-2 rounded">
                        <summary class="cursor-pointer text-blue-600 font-medium">Why flagged?</summary>
                        <ul class="mt-1 space-y-1">
                            ${reasonsHtml}
                            ${imageHtml}
                            ${phonesHtml}
                        </ul>
                    </details>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }
}
window.downloadEvidence = (detectionId) => {
    const ev = (window._evidenceCache || []).find(e => e.detectionId === detectionId);
    if (!ev) { alert('Evidence package not found.'); return; }

    const pkg = {
        exportedAt: new Date().toISOString(),
        exportedBy: 'Durai Singam',
        note: 'Verify by re-hashing "content" with SHA-256 and comparing to contentHash/packageHash.',
        package: ev
    };

    const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `narcox-evidence-${detectionId}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
};

async function updateInstagram() {
    // We can hardcode the query params for now like we did for Telegram
    const minRisk = 4;
    const days = 30;
    const detections = await API.get(`/api/detections?platform=instagram&minRisk=${minRisk}&days=${days}`);
    
    if (detections) {
        const tbody = document.getElementById('instagram-page-tbody');
        if(!tbody) return;
        tbody.innerHTML = '';
        
        if (detections.length === 0) {
            tbody.innerHTML = `<tr id="empty-state"><td colspan="5" class="py-6 text-center text-gray-500 font-medium">No active alerts</td></tr>`;
            return;
        }

        detections.forEach(det => {
            const tr = document.createElement('tr');
            tr.className = 'border-b border-gray-200 hover:bg-gray-50';
            const timeStr = new Date(det.ts).toLocaleTimeString();
            
            const simulatedTag = det.simulated ? `<span class="ml-2 px-2 py-0.5 bg-yellow-500/20 text-yellow-500 text-[10px] rounded uppercase">Simulated</span>` : '';
            const reasonsHtml = (det.reasons || []).map(r => `<li>- ${esc(r)}</li>`).join('');
            const imageHtml = (det.imageLabels && det.imageLabels.length > 0) ? `<li>?? AI found: ${esc(det.imageLabels.join(', '))}</li>` : '';
            
            tr.innerHTML = `
                <td class="py-3 px-4 text-sm text-gray-500">${timeStr}</td>
                <td class="py-3 px-4">${esc(det.chatTitle)}</td>
                <td class="py-3 px-4">${esc(det.username)}</td>
                <td class="py-3 px-4">${riskBadge(det.risk)}</td>
                <td class="py-3 px-4">
                    <div>${esc(det.text)} ${simulatedTag}</div>
                    <details class="mt-2 text-xs text-gray-500 bg-gray-100 p-2 rounded">
                        <summary class="cursor-pointer text-blue-600 font-medium">Why flagged?</summary>
                        <ul class="mt-1 space-y-1">
                            ${reasonsHtml}
                            ${imageHtml}
                        </ul>
                    </details>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }
}

async function updateEvidence() {
    const evidence = await API.get('/api/evidence');
    const container = document.getElementById('evidence-container');
    if (!evidence || !container) return;
    window._evidenceCache = evidence;
    
    container.innerHTML = '';
    
    if (evidence.length === 0) {
        container.innerHTML = `<div id="empty-state" class="py-6 text-center text-gray-500 font-medium">No forensic packages available</div>`;
        return;
    }

    evidence.forEach(ev => {
        const verifiedBadge = ev.verified 
            ? `<span class="hash-verified text-sm px-3 py-1 bg-green-500/10 border border-green-500/30 rounded">✓ HASH VERIFIED</span>`
            : `<span class="text-sm px-3 py-1 bg-red-500/10 border border-red-500/30 text-red-500 rounded">✗ TAMPERED</span>`;
            
        const custodyHtml = ev.custody.map(c => 
            `<div class="flex justify-between text-xs text-gray-500"><span class="font-mono">${c.action} by ${c.by}</span> <span>${new Date(c.at).toLocaleString()}</span></div>`
        ).join('');
        
        container.innerHTML += `
            <div class="stat-card p-6 rounded-lg border-l-4 ${ev.verified ? 'border-green-500' : 'border-red-500'}">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h3 class="font-mono text-lg text-primary">CASE #${ev.detectionId}</h3>
                        <p class="text-xs text-gray-500 mt-1">Package Hash: <span class="font-mono text-[10px] bg-muted/30 p-1 rounded break-all">${ev.packageHash}</span></p>
                    </div>
                    ${verifiedBadge}
                </div>
                <div class="bg-black/50 p-3 rounded mb-4 font-mono text-xs border border-gray-200">
                    <div class="text-blue-600 mb-2">RAW CONTENT:</div>
                    ${JSON.stringify(ev.content, null, 2)}
                </div>
                <div class="space-y-2 mb-4">
                    <div class="text-xs font-bold text-gray-500 uppercase tracking-wider">Custody Chain</div>
                    ${custodyHtml}
                </div>
                <button onclick="downloadEvidence('${ev.detectionId}')" class="text-xs bg-primary hover:bg-red-700 text-white px-4 py-2 rounded transition-colors flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                    Download Forensic JSON
                </button>
            </div>
        `;
    });
}

let networkInitialized = false;
let netInstance = null;

async function updateNetwork() {
    if (networkInitialized) return;
    if (location.hash !== '#network') return;
    const data = await API.get('/api/network');
    const container = document.getElementById('network-map-container');
    if (!data || !container || !window.vis) return;
    networkInitialized = true;

    // 1. Merge duplicate edges into one weighted edge
    const merged = {};
    data.edges.forEach(e => {
        const k = e.from + '|' + e.to + '|' + e.kind;
        merged[k] = merged[k] || { ...e, weight: 0 };
        merged[k].weight++;
    });
    const edgeList = Object.values(merged);

    // 2. Node styling by type/risk
    const palette = { account: '#38bdf8', group: '#a78bfa', phones: '#34d399',
                      upi: '#fbbf24', wallets: '#f472b6', emails: '#22d3ee' };
    const info = {};
    const nodes = new vis.DataSet(data.nodes.map(n => {
        info[n.id] = n;
        const base = palette[n.type] || '#94a3b8';
        const hot = n.risk >= 8;
        const ring = n.type === 'group';
        return {
            id: n.id,
            label: n.label,
            shape: 'dot',
            value: Math.max(6, n.risk * 2 + (n.degree || 0) * 3),
            color: {
                background: hot ? '#ff3b3b' : base,
                border: ring ? '#e5e7eb' : (hot ? '#ffb3b3' : 'rgba(255,255,255,0.25)'),
                highlight: { background: '#fef2f2', border: '#ef4444' }
            },
            borderWidth: ring ? 3 : (hot ? 3 : 1.5),
            shadow: { enabled: true, color: 'rgba(0,0,0,0.1)', size: 10, x: 2, y: 2 },
            font: { color: '#0f172a', size: 13, face: 'Inter, ui-sans-serif, system-ui', strokeWidth: 3, strokeColor: '#ffffff' },
            title: `${n.label}\nType: ${n.type}\nRisk: ${n.risk}/10\nConnections: ${n.degree || 0}` +
                   (n.role ? `\nRole: ${n.role}` : '')
        };
    }));

    const edges = new vis.DataSet(edgeList.map((e, i) => ({
        id: i, from: e.from, to: e.to,
        width: Math.min(1 + Math.log2(e.weight + 1) * 1.5, 8),
        title: `${e.kind} x${e.weight}`,
        color: { color: '#94a3b8', highlight: '#ef4444', opacity: 0.8 },
        smooth: { type: 'continuous' },
        arrows: { to: { enabled: true, scaleFactor: 0.5 } }
    })));

    netInstance = new vis.Network(container, { nodes, edges }, {
        nodes: { scaling: { min: 14, max: 45 } },
        interaction: { hover: true, tooltipDelay: 100, navigationButtons: true, keyboard: true },
        physics: {
            solver: 'forceAtlas2Based',
            forceAtlas2Based: { gravitationalConstant: -80, centralGravity: 0.02, springLength: 140, avoidOverlap: 0.6 },
            stabilization: { iterations: 200 }
        }
    });

    // 3. Details panel
    let panel = document.getElementById('network-panel');
    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'network-panel';
        panel.style.cssText = 'position:absolute;top:12px;right:12px;width:230px;background:rgba(255,255,255,0.95);box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);' +
            'border:1px solid #cbd5e1;border-radius:10px;padding:14px;font-size:12px;color:#0f172a;display:none;z-index:5;backdrop-filter:blur(4px)';
        container.style.position = 'relative';
        container.appendChild(panel);
    }

    // 4. Click a node to spotlight its neighbors and dim the rest
    netInstance.on('click', p => {
        const all = nodes.getIds();
        if (!p.nodes.length) {
            nodes.update(all.map(id => ({ id, opacity: 1 })));
            panel.style.display = 'none';
            return;
        }
        const id = p.nodes[0];
        const near = new Set([id, ...netInstance.getConnectedNodes(id)]);
        nodes.update(all.map(x => ({ id: x, opacity: near.has(x) ? 1 : 0.12 })));
        const n = info[id];
        panel.innerHTML = `<div style="font-weight:700;color:#ef4444;margin-bottom:6px">${esc(n.label)}</div>` +
            `<div>Type: ${esc(n.type)}</div><div>Risk: ${n.risk}/10</div>` +
            `<div>Connections: ${n.degree || 0}</div><div>Messages: ${n.count}</div>` +
            (n.role ? `<div>Role: ${esc(n.role)}</div>` : '');
        panel.style.display = 'block';
    });

    // 5. Search and fit controls
    const bar = document.getElementById('network-controls');
    if (bar && !bar.dataset.ready) {
        bar.dataset.ready = '1';
        bar.innerHTML = `<input id="net-search" placeholder="Search account..." style="background:#0b1220;border:1px solid #1e293b;color:#f1f5f9;padding:6px 12px;border-radius:8px;font-size:12px;width:200px"> ` +
            `<button id="net-fit" style="background:#38bdf8;color:#05070a;font-weight:600;padding:6px 14px;border-radius:8px;font-size:12px;margin-left:8px">Fit View</button>`;
        document.getElementById('net-fit').onclick = () => netInstance.fit({ animation: true });
        document.getElementById('net-search').oninput = ev => {
            const q = ev.target.value.toLowerCase();
            const hit = nodes.get().find(n => q && n.label.toLowerCase().includes(q));
            if (hit) { netInstance.selectNodes([hit.id]); netInstance.focus(hit.id, { scale: 1.3, animation: true }); }
        };
    }
    netInstance.once('stabilizationIterationsDone', () => netInstance.fit({ animation: true }));
    window.addEventListener('hashchange', () => {
        if (location.hash === '#network' && netInstance) {
            setTimeout(() => { netInstance.redraw(); netInstance.fit({ animation: true }); }, 100);
        }
    });
}

function runAllUpdates() {
    updateDashboard();
    updateAlerts();
    updateTelegram();
    updateInstagram();
    updateEvidence();
    updateNetwork();
}

// Tell our poll() tool to run everything every 5 seconds!
poll(runAllUpdates, 5000);


async function updateCharts() {
    const stats = await API.get('/api/stats');
    if (!stats) return;

    const trendContainer = document.getElementById('chart-trends');
    if (trendContainer && Array.isArray(stats.trend)) {
        const maxCount = Math.max(1, ...stats.trend.map(d => d.count));
        trendContainer.innerHTML = stats.trend.length === 0
            ? '<div class="text-center text-gray-500 text-sm w-full">No data in the last 7 days</div>'
                        : stats.trend.map(d => {
                const barPx = Math.max(6, Math.round((d.count / maxCount) * 180));
                const day = new Date(d._id).toLocaleDateString(undefined, { weekday: 'short' });
                return `
                    <div class="flex flex-col items-center justify-end flex-1 h-full">
                        <div class="text-[10px] text-gray-500 mb-1">${d.count}</div>
                        <div class="w-full rounded-t" style="height:${barPx}px; background:#dc2626"></div>
                        <div class="text-[10px] text-gray-500 mt-2">${day}</div>
                    </div>
                `;
            }).join('');
    }

    const mediaContainer = document.getElementById('chart-media');
    if (mediaContainer && stats.byType) {
        const entries = Object.entries(stats.byType);
        const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;
        mediaContainer.innerHTML = entries.length === 0
            ? '<div class="text-center text-gray-500 text-sm">No data available</div>'
            : entries.map(([type, count]) => {
                const pct = Math.round((count / total) * 100);
                return `
                    <div>
                        <div class="flex justify-between text-xs mb-1">
                            <span class="text-gray-500 capitalize">${type}</span>
                            <span class="text-primary font-medium">${count}</span>
                        </div>
                        <div class="w-full bg-muted/30 rounded-full h-2">
                            <div class="bg-primary h-2 rounded-full" style="width:${pct}%"></div>
                        </div>
                    </div>
                `;
            }).join('');
    }
}

if (typeof updateDashboard === 'function') {
    const _origUpdateDashboard = updateDashboard;
    updateDashboard = async function() {
        await _origUpdateDashboard();
        await updateCharts();
    };
} else {
    setInterval(updateCharts, 5000);
    updateCharts();
}

function reportQueryString(extra = {}) {
    const params = new URLSearchParams({ report: 1, ...extra });
    const from = document.getElementById('report-from')?.value;
    const to = document.getElementById('report-to')?.value;
    const platform = document.getElementById('report-platform')?.value;
    const minRisk = document.getElementById('report-minrisk')?.value;
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    if (platform) params.set('platform', platform);
    if (minRisk) params.set('minRisk', minRisk);
    return params.toString();
}

async function updateReports() {
    const data = await API.get(`/api/stats?${reportQueryString()}`);
    if (!data) return;

    document.getElementById('report-total').innerText = data.summary.totalDetections;
    document.getElementById('report-high').innerText = data.summary.highRisk;
    document.getElementById('report-medium').innerText = data.summary.mediumRisk;
    document.getElementById('report-low').innerText = data.summary.lowRisk;

    const kwBody = document.getElementById('report-keywords-tbody');
    kwBody.innerHTML = data.topKeywords.length
        ? data.topKeywords.map(k => `
            <tr class="border-b border-gray-200">
                <td class="py-2">${esc(k.term)}</td>
                <td class="py-2 text-right text-gray-500">${k.count}</td>
            </tr>`).join('')
        : `<tr><td class="py-2 text-gray-500">No data</td></tr>`;

    const acctBody = document.getElementById('report-accounts-tbody');
    acctBody.innerHTML = data.topAccounts.length
        ? data.topAccounts.map(a => `
            <tr class="border-b border-gray-200">
                <td class="py-2">${esc(a.account)}</td>
                <td class="py-2 text-right text-gray-500">${a.count}</td>
            </tr>`).join('')
        : `<tr><td class="py-2 text-gray-500">No data</td></tr>`;
}

function downloadReportCsv() {
    window.open(`/api/stats?${reportQueryString({ format: 'csv' })}`, '_blank');
}






