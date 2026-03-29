const API_BASE = "http://" + window.location.host + "/api";

let feederChart;
let substationChart;
let anomalyChart;

document.addEventListener('DOMContentLoaded', () => {
    initNav();
    initCharts();
    initIDS();
    startEngine();
});

function initNav() {
    const btns = document.querySelectorAll('.nav-btn');
    const sections = document.querySelectorAll('.view-section');

    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            btns.forEach(b => b.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(btn.dataset.target).classList.add('active');
        });
    });
}

function initCharts() {
    // Feeder Chart
    const ctxF = document.getElementById('feederChart').getContext('2d');
    feederChart = new Chart(ctxF, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Load (%)', data: [], borderColor: '#3b82f6', tension: 0.4 },
                { label: 'Current (A)', data: [], borderColor: '#eab308', tension: 0.4 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: { x: { display: false }, y: { min: 0 } },
            plugins: { legend: { labels: { color: '#cbd5e1' } } }
        }
    });

    // Substation Chart
    const ctxS = document.getElementById('substationChart').getContext('2d');
    substationChart = new Chart(ctxS, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{ label: 'Exported MW', data: [], borderColor: '#22c55e', fill: true, backgroundColor: 'rgba(34, 197, 94, 0.1)' }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: { x: { display: false }, y: { min: 0 } },
            plugins: { legend: { labels: { color: '#cbd5e1' } } }
        }
    });

    // Anomaly Chart
    const ctxA = document.getElementById('anomalyChart').getContext('2d');
    anomalyChart = new Chart(ctxA, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{ label: 'Anomaly Score', data: [], borderColor: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', fill: true, tension: 0.1 }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: { x: { display: false } },
            plugins: { legend: { labels: { color: '#cbd5e1' } } }
        }
    });
}

function startEngine() {
    setInterval(updateClock, 1000);
    setInterval(pollData, 2000); // 2 seconds
    setInterval(pollIDS, 2000); // 2 seconds
}

function updateClock() {
    document.getElementById('clock').innerText = new Date().toLocaleTimeString();
}

async function pollData() {
    try {
        // Check isolation status
        const isoRes = await fetch(`${API_BASE}/isolation_status`);
        const isoData = await isoRes.json();
        
        handleIsolation(isoData.isolated);

        // Fetch real-time SCADA
        const scadaRes = await fetch(`${API_BASE}/scada_status`);
        if (!scadaRes.ok && isoData.isolated) {
            // SCADA stopped intentionally = All offline
            updateDiagramOffline();
            return;
        }

        const scadaData = await scadaRes.json();
        if (scadaData.rtus) {
            updateCharts(scadaData.rtus);
            updateDiagram(scadaData.rtus);
        }

    } catch (e) {
        console.error("Polling error:", e);
        updateDiagramOffline();
    }
}

function handleIsolation(isIsolated) {
    const banner = document.getElementById('isolation-banner');
    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');

    if (isIsolated) {
        banner.classList.remove('hidden');
        indicator.className = 'indicator isolated';
        text.innerText = 'Electrical System - Manual Mode';
        text.style.color = '#ef4444';
    } else {
        banner.classList.add('hidden');
        indicator.className = 'indicator ok';
        text.innerText = 'System Normal';
        text.style.color = '#94a3b8';
    }
}

function updateCharts(rtus) {
    const time = new Date().toLocaleTimeString();

    // Feeder
    if (rtus['FEEDER'] && !rtus['FEEDER'].status) {
        const f = rtus['FEEDER'];
        if (feederChart.data.labels.length > 20) {
            feederChart.data.labels.shift();
            feederChart.data.datasets.forEach(d => d.data.shift());
        }
        feederChart.data.labels.push(time);
        feederChart.data.datasets[0].data.push(f.load_pct || 0);
        feederChart.data.datasets[1].data.push(f.current || 0);
        feederChart.update('none');
    }

    // Substation
    if (rtus['SUBSTATION'] && !rtus['SUBSTATION'].status) {
        const s = rtus['SUBSTATION'];
        if (substationChart.data.labels.length > 20) {
            substationChart.data.labels.shift();
            substationChart.data.datasets[0].data.shift();
        }
        substationChart.data.labels.push(time);
        substationChart.data.datasets[0].data.push(s.exported_mw || 0);
        substationChart.update('none');
    }
}

// Diagram Logic
function updateDiagram(rtus) {
    // Map RTU names to DOM node IDs
    const map = {
        'SUBSTATION': 'node-substation',
        'FEEDER': 'node-feeder',
        'HOME_1': 'node-home1',
        'HOME_2': 'node-home2',
        'HOME_3': 'node-home3'
    };

    // SCADA Master Node (always online if this runs)
    setNodeState('node-scada', 'active', 'Online');

    for (const [rtu, id] of Object.entries(map)) {
        const data = rtus[rtu];
        if (!data || data.status === 'OFFLINE' || data.status === 'ERROR') {
            setNodeState(id, 'offline', 'Offline');
        } else if (data.overload || data.overload_alarm || data.trip) {
            setNodeState(id, 'alarm', 'Alarm');
        } else if (data.breaker_closed === false || data.supply_on === false) {
             setNodeState(id, 'alarm', 'Tripped');
        } else {
            setNodeState(id, 'active', 'Online');
        }
    }
}

function updateDiagramOffline() {
    const nodes = ['node-scada','node-substation', 'node-feeder', 'node-home1', 'node-home2', 'node-home3'];
    nodes.forEach(id => setNodeState(id, 'offline', 'Offline'));
}

function setNodeState(elemId, cls, text) {
    const el = document.getElementById(elemId);
    if (!el) return;
    el.className = `flow-node ${cls}`;
    const stateEl = el.querySelector('.state');
    if (stateEl) stateEl.innerText = text;
}

// IDS Logics
async function initIDS() {
    // Buttons
    document.getElementById('btn-unisolate').addEventListener('click', async () => {
        try {
            await fetch(`${API_BASE}/unisolate`, { method: 'POST' });
            pollData(); // Force immediate update
        } catch(e) { console.error(e); }
    });

    document.getElementById('btn-start-ids').addEventListener('click', async () => {
        const intf = document.getElementById('interface-select').value;
        try {
            await fetch(`${API_BASE}/ids/start`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({interface: intf})
            });
            pollIDS(); // immediate feedback
        } catch(e) { console.error(e); }
    });

    document.getElementById('btn-stop-ids').addEventListener('click', async () => {
        try {
            await fetch(`${API_BASE}/ids/stop`, { method: 'POST' });
            pollIDS();
        } catch(e) { console.error(e); }
    });

    // Load interfaces
    try {
        const res = await fetch(`${API_BASE}/interfaces`);
        const interfaces = await res.json();
        const select = document.getElementById('interface-select');
        select.innerHTML = '';
        interfaces.forEach(i => {
            const opt = document.createElement('option');
            opt.value = i;
            opt.innerText = i;
            select.appendChild(opt);
        });
    } catch(e) { console.error(e); }
}

async function pollIDS() {
    try {
        // Status
        const stRes = await fetch(`${API_BASE}/ids/status`);
        const stData = await stRes.json();
        const startBtn = document.getElementById('btn-start-ids');
        const stopBtn = document.getElementById('btn-stop-ids');
        const stText = document.getElementById('ids-status-text');

        if (stData.running) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
            stText.innerText = 'Running';
            stText.className = 'status-online';
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
            stText.innerText = 'Stopped';
            stText.className = 'status-offline';
        }

        // Logs
        const lgRes = await fetch(`${API_BASE}/ids/logs`);
        const lgData = await lgRes.json();
        
        const term = document.getElementById('ids-log-terminal');
        const isAtBottom = term.scrollHeight - term.scrollTop <= term.clientHeight + 10;
        
        if (lgData.logs) {
            term.innerText = lgData.logs;
            if (isAtBottom) term.scrollTop = term.scrollHeight;
        }

        // Scores updating graph
        if (lgData.scores && lgData.scores.length > 0) {
            anomalyChart.data.labels = lgData.scores.map(s => s.time);
            anomalyChart.data.datasets[0].data = lgData.scores.map(s => s.score);
            anomalyChart.update('none');
        }

    } catch(e) {}
}
