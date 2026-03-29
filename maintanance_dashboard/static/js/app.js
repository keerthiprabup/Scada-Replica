const API_BASE = "http://" + window.location.host + "/api";
const SCADA_API_BASE = "http://localhost:5000/api";

let anomalyChart;
let mainChart;
let isIdsRunning = false;

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

    // SCADA Main Chart
    const ctxM = document.getElementById('mainChart').getContext('2d');
    mainChart = new Chart(ctxM, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Feeder Load (A)', data: [], borderColor: '#3b82f6', tension: 0.4 },
                { label: 'Voltage (V)', data: [], borderColor: '#22c55e', tension: 0.4, yAxisID: 'y1' }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
                y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
                y1: { position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#22c55e' } }
            },
            plugins: { legend: { labels: { color: '#e2e8f0' } } }
        }
    });
}

function startEngine() {
    setInterval(updateClock, 1000);
    setInterval(pollData, 2000); // 2 seconds
    setInterval(pollIDS, 2000); // 2 seconds
    setInterval(pollScadaMaster, 2000); // 2 seconds
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

    } catch (e) {
        console.error("Polling error:", e);
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
        const pwd = document.getElementById('ids-password').value;
        try {
            const res = await fetch(`${API_BASE}/ids/start`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({interface: intf, password: pwd})
            });
            const d = await res.json();
            if (!d.success) alert(d.message);
            pollIDS(); // immediate feedback
        } catch(e) { console.error(e); }
    });

    document.getElementById('btn-stop-ids').addEventListener('click', async () => {
        const pwd = document.getElementById('ids-password').value;
        try {
            const res = await fetch(`${API_BASE}/ids/stop`, { 
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({password: pwd}) 
            });
            const d = await res.json();
            if (!d.success) alert(d.message);
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
            isIdsRunning = true;
            
            // Hide scada tabs
            document.querySelectorAll('.scada-feature').forEach(el => el.style.display = 'none');
            // Force active tab to ids-view
            document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));
            document.getElementById('ids-view').classList.add('active');
            document.querySelectorAll('.nav-btn').forEach(b => {
                if(b.getAttribute('data-target') === 'ids-view') b.classList.add('active');
                else b.classList.remove('active');
            });
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
            stText.innerText = 'Stopped';
            stText.className = 'status-offline';
            isIdsRunning = false;
            
            // Show scada tabs
            document.querySelectorAll('.scada-feature').forEach(el => el.style.display = '');
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

// SCADA Master Polling
async function pollScadaMaster() {
    if (isIdsRunning) return; 
    
    try {
        const res = await fetch(`${SCADA_API_BASE}/status`);
        const data = await res.json();
        renderDashboard(data.rtus);
        updateLiveChart(data);
    } catch(e) {}
    
    // History if analysis view is active
    if (document.getElementById('analysis-view').classList.contains('active')) {
        try {
            const res = await fetch(`${SCADA_API_BASE}/history?limit=100`);
            const logs = await res.json();
            const tbody = document.getElementById('log-table-body');
            tbody.innerHTML = '';
            logs.reverse().forEach(log => {
                const row = document.createElement('tr');
                let summary = "Normal";
                if (log.data.FEEDER && log.data.FEEDER.overload_alarm) summary = "FEEDER OVERLOAD";
                if (log.data.SUBSTATION && log.data.SUBSTATION.overload) summary = "SUBSTATION OVERLOAD";

                row.innerHTML = `
                    <td style="padding: 10px; border-bottom: 1px solid #334155;">${log.timestamp}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #334155;">${summary}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #334155;"><pre style="font-size:0.75rem; color:#94a3b8; margin:0; white-space:pre-wrap;">${JSON.stringify(log.data.FEEDER || {}, null, 0).substring(0, 100)}</pre></td>
                `;
                tbody.appendChild(row);
            });
        } catch(e) {}
    }
}

function renderDashboard(rtus) {
    const container = document.getElementById('rtu-grid');
    if (!container) return;
    container.innerHTML = '';

    const keys = Object.keys(rtus).sort((a, b) => {
        if (a === 'SUBSTATION') return -1;
        if (b === 'SUBSTATION') return 1;
        if (a === 'FEEDER') return -1;
        if (b === 'FEEDER') return 1;
        return a.localeCompare(b);
    });

    keys.forEach(key => {
        const data = rtus[key];
        const div = document.createElement('div');
        div.style.backgroundColor = "#1e293b";
        div.style.padding = "15px";
        div.style.border = "1px solid #334155";
        div.style.borderRadius = "8px";
        div.style.marginBottom = "10px";

        let statusClass = 'status-ok';
        let statusText = 'ONLINE';
        if (data.status === 'ERROR' || data.status === 'OFFLINE') {
            statusClass = 'status-err';
            statusText = 'OFFLINE';
        } else if (data.overload || data.overload_alarm || data.trip) {
            statusClass = 'status-warn';
            statusText = 'ALARM';
        } else if (data.breaker_closed === false || data.supply_on === false) {
            statusClass = 'status-warn';
            statusText = 'TRIPPED/OFF';
        }

        let metricsHtml = '';
        if (statusText !== 'OFFLINE') {
            for (let [k, v] of Object.entries(data)) {
                if (typeof v === 'number') v = Math.round(v * 100) / 100;
                if (['status'].includes(k)) continue;
                metricsHtml += `<div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span style="color:#94a3b8; font-size:0.9rem">${k.toUpperCase()}</span> <span>${v}</span></div>`;
            }
        }

        div.innerHTML = `
            <div style="display:flex; justify-content:space-between; margin-bottom:10px; border-bottom:1px solid #334155; padding-bottom:5px;">
                <strong style="color:#e2e8f0">${key}</strong>
                <span class="${statusClass}" style="font-size:0.8rem; padding:2px 6px; border-radius:4px; 
                      background-color:${statusText === 'ONLINE' ? '#166534' : '#7f1d1d'};
                      color:${statusText === 'ONLINE' ? '#bbf7d0' : '#fecaca'};">${statusText}</span>
            </div>
            <div>${metricsHtml}</div>
        `;
        container.appendChild(div);
    });
}

function updateLiveChart(fullData) {
    if (!mainChart) return;
    const timestamp = new Date().toLocaleTimeString();
    const feeder = fullData.rtus['FEEDER'];

    if (feeder && feeder.current !== undefined) {
        if (mainChart.data.labels.length > 50) {
            mainChart.data.labels.shift();
            mainChart.data.datasets[0].data.shift();
            mainChart.data.datasets[1].data.shift();
        }
        mainChart.data.labels.push(timestamp);
        mainChart.data.datasets[0].data.push(feeder.current);
        mainChart.data.datasets[1].data.push(feeder.voltage);
        mainChart.update('none');
    }
}

async function addRTU() {
    const name = document.getElementById('rtu-name').value;
    const ip = document.getElementById('rtu-ip').value;
    const port = document.getElementById('rtu-port').value;
    const unit = document.getElementById('rtu-unit').value;

    const res = await fetch(`${SCADA_API_BASE}/rtu`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, ip, port, unit })
    });

    const json = await res.json();
    alert(json.message || "Done");
    document.getElementById('add-rtu-form').reset();
}
