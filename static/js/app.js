// SCADA Frontend Logic

let trendChart;
const API_BASE = "http://" + window.location.host + "/api";

// ---------------- INITIALIZATION ----------------
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    startPolling();
    initChart();
});

function initNavigation() {
    const navBtns = document.querySelectorAll('.nav-links button');
    const sections = document.querySelectorAll('.view-section');

    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Active State
            navBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // View Switching
            const targetId = btn.getAttribute('data-target');
            sections.forEach(sec => {
                sec.classList.remove('active');
                if (sec.id === targetId) sec.classList.add('active');
            });

            // Special Actions
            if (targetId === 'analysis-view') loadHistory();
        });
    });
}

// ---------------- CHART.JS ----------------
function initChart() {
    const ctx = document.getElementById('mainChart').getContext('2d');
    trendChart = new Chart(ctx, {
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

// ---------------- DATA POLLING ----------------
function startPolling() {
    setInterval(fetchStatus, 2000); // 2s polling
    setInterval(updateClock, 1000);
}

async function fetchStatus() {
    try {
        const res = await fetch(`${API_BASE}/status`);
        const data = await res.json();
        renderDashboard(data.rtus);
        updateLiveChart(data);
    } catch (e) {
        console.error("Poll Error:", e);
    }
}

function updateClock() {
    const now = new Date();
    document.getElementById('clock').innerText = now.toISOString().replace('T', ' ').substring(0, 19);
}

// ---------------- RENDERING ----------------
function renderDashboard(rtus) {
    const container = document.getElementById('rtu-grid');
    container.innerHTML = ''; // Clear (Improve logic later to diff instead of clear)

    // Sort: Substation, Feeder, then Homes
    const keys = Object.keys(rtus).sort((a, b) => {
        if (a === 'SUBSTATION') return -1;
        if (b === 'SUBSTATION') return 1;
        if (a === 'FEEDER') return -1;
        if (b === 'FEEDER') return 1;
        return a.localeCompare(b);
    });

    keys.forEach(key => {
        const data = rtus[key];
        const card = createRTUCard(key, data);
        container.appendChild(card);
    });
}

function createRTUCard(name, data) {
    const div = document.createElement('div');
    div.className = 'card';

    // Status Badge
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

    // Metrics HTML
    let metricsHtml = '';
    if (statusText !== 'OFFLINE') {
        for (let [k, v] of Object.entries(data)) {
            if (typeof v === 'number') v = Math.round(v * 100) / 100; // Round 2 dec
            if (['status'].includes(k)) continue;
            metricsHtml += `
                <div class="metric-item">
                    <span class="metric-label">${k.toUpperCase().replace('_', ' ')}</span>
                    <span class="metric-value">${v}</span>
                </div>
            `;
        }
    }

    // Controls
    let controlsHtml = '';
    if (name === 'FEEDER') {
        controlsHtml = `
            <button class="btn btn-success" onclick="sendCommand('FEEDER', 'CLOSE')">CLOSE</button>
            <button class="btn btn-danger" onclick="sendCommand('FEEDER', 'OPEN')">TRIP</button>
        `;
    } else if (name.startsWith('HOME')) {
        controlsHtml = `
            <button class="btn btn-success" onclick="sendCommand('${name}', 'ON')">ON</button>
            <button class="btn btn-danger" onclick="sendCommand('${name}', 'OFF')">OFF</button>
        `;
    }

    div.innerHTML = `
        <div class="card-header">
            <span>${name}</span>
            <span class="status-badge ${statusClass}">${statusText}</span>
        </div>
        <div class="metrics-list">
            ${metricsHtml}
        </div>
        <div class="control-panel">
            ${controlsHtml}
        </div>
    `;
    return div;
}

// ---------------- CHART UPDATE ----------------
function updateLiveChart(fullData) {
    if (!trendChart) return;

    const timestamp = new Date().toLocaleTimeString();
    const feeder = fullData.rtus['FEEDER'];

    if (feeder && feeder.current !== undefined) {
        if (trendChart.data.labels.length > 20) {
            trendChart.data.labels.shift();
            trendChart.data.datasets[0].data.shift();
            trendChart.data.datasets[1].data.shift();
        }

        trendChart.data.labels.push(timestamp);
        trendChart.data.datasets[0].data.push(feeder.current);
        trendChart.data.datasets[1].data.push(feeder.voltage);
        trendChart.update('none'); // 'none' for performance
    }
}

// ---------------- HISTORY ----------------
async function loadHistory() {
    const res = await fetch(`${API_BASE}/history?limit=50`);
    const logs = await res.json();
    const tbody = document.getElementById('log-table-body');
    tbody.innerHTML = '';

    logs.reverse().forEach(log => {
        const row = document.createElement('tr');
        // Simple summary: show first alert or just status
        let summary = "Normal";
        if (log.data.FEEDER && log.data.FEEDER.overload_alarm) summary = "FEEDER OVERLOAD";
        if (log.data.SUBSTATION && log.data.SUBSTATION.overload) summary = "SUBSTATION OVERLOAD";

        row.innerHTML = `
            <td>${log.timestamp}</td>
            <td>${summary}</td>
            <td><pre style="font-size:0.7rem">${JSON.stringify(log.data.FEEDER || {}, null, 0).substring(0, 50)}...</pre></td>
        `;
        tbody.appendChild(row);
    });
}

// ---------------- CONTROLS ----------------
async function sendCommand(target, action) {
    await fetch(`${API_BASE}/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, action })
    });
    // Instant feedback or wait for poll
}

async function addRTU() {
    const name = document.getElementById('rtu-name').value;
    const ip = document.getElementById('rtu-ip').value;
    const port = document.getElementById('rtu-port').value;
    const unit = document.getElementById('rtu-unit').value;

    const res = await fetch(`${API_BASE}/rtu`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, ip, port, unit })
    });

    const json = await res.json();
    alert(json.message || "Done");
    document.getElementById('add-rtu-form').reset();
}
