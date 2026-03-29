const API_BASE = "http://" + window.location.host + "/api";

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
