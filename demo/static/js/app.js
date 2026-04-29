// State Machine & Global Variables
let currentTab = 'scada-view';
let userManualIdsState = false; // True = User wants IDS ON. False = User manually killed it.
let isIsolated = false;

let trendChart;
const API_BASE = "/api";
let pendingAuthAction = null; // 'ISOLATE' or 'UNISOLATE'

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initChart();
    startPolling();
    fetchInterfaces();
});

async function fetchInterfaces() {
    try {
        const res = await fetch(`${API_BASE}/interfaces`);
        const interfaces = await res.json();
        const select = document.getElementById('interface-select');
        select.innerHTML = '';
        interfaces.forEach(iface => {
            const opt = document.createElement('option');
            opt.value = iface.name;
            opt.textContent = iface.name + (iface.ip ? ` (${iface.ip})` : '');
            select.appendChild(opt);
        });
    } catch (e) {
        console.error("Failed to fetch interfaces", e);
    }
}

// ---------------- NAVIGATION & SPA LOGIC ----------------
function initNavigation() {
    const navTabs = document.querySelectorAll('.nav-tab');
    const sections = document.querySelectorAll('.view-section');

    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.getAttribute('data-target');
            if (targetId === currentTab) return;

            // Update UI
            navTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            sections.forEach(s => {
                s.classList.add('hidden');
                s.classList.remove('active');
                if (s.id === targetId) {
                    s.classList.remove('hidden');
                    s.classList.add('active');
                }
            });

            currentTab = targetId;
            handleTabSwitch();
        });
    });
}

function handleTabSwitch() {
    if (currentTab === 'scada-view') {
        // PAUSE IDS! Never analyze while SCADA HMI is active.
        setIdsState('OFF');
    } else if (currentTab === 'ids-view') {
        // RESUME IDS (Only if the user didn't manually turn it off)
        if (userManualIdsState) {
            setIdsState('ON');
        } else {
            setIdsState('OFF');
        }
    }
}

async function toggleManualIds() {
    userManualIdsState = !userManualIdsState;
    if (userManualIdsState) {
        await setIdsState('ON');
    } else {
        await setIdsState('OFF');
    }
}

async function setIdsState(mode) {
    try {
        const iface = document.getElementById('interface-select').value;
        await fetch(`${API_BASE}/ids/mode`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ mode: mode, interface: iface })
        });
        
        const badge = document.getElementById('ids-status-badge');
        const btn = document.getElementById('manual-ids-toggle');
        
        if (mode === 'ON') {
            badge.className = 'badge badge-green';
            badge.innerText = 'IDS: ACTIVE';
            if (btn) {
                btn.className = 'btn btn-danger';
                btn.innerHTML = '<i class="fa-solid fa-stop"></i> STOP IDS';
            }
        } else {
            badge.className = 'badge badge-red';
            badge.innerText = 'IDS: PAUSED';
            if (btn) {
                btn.className = 'btn btn-success';
                btn.innerHTML = '<i class="fa-solid fa-play"></i> START IDS';
            }
        }
    } catch (e) {
        console.error("Failed to change IDS state", e);
    }
}

// ---------------- SCADA RENDERING ----------------
function renderScadaGrid(rtus) {
    const grid = document.getElementById('scada-grid');
    grid.innerHTML = ''; // Re-render for simplicity

    const keys = Object.keys(rtus).sort((a,b) => {
        if (a === 'SUBSTATION') return -1;
        if (a === 'FEEDER') return (b==='SUBSTATION') ? 1 : -1;
        return a.localeCompare(b);
    });

    keys.forEach(key => {
        const data = rtus[key];
        const card = document.createElement('div');
        card.className = 'rtu-node';
        
        // Determine Status Color
        let glowColor = 'rgba(255,255,255,0.05)';
        let statusBadge = `<span class="badge badge-green">NORMAL</span>`;
        if (data.status === 'ERROR' || data.status === 'OFFLINE') {
            glowColor = 'var(--accent-red-glow)';
            statusBadge = `<span class="badge badge-red">OFFLINE</span>`;
        } else if (data.overload || data.overload_alarm || data.trip || data.breaker_closed === false || data.supply_on === false) {
            glowColor = 'var(--accent-red-glow)';
            statusBadge = `<span class="badge badge-red">ALERT/TRIP</span>`;
        } else {
            glowColor = 'var(--accent-green-glow, rgba(16,185,129,0.2))';
        }

        // Image Selection
        let imgSrc = '';
        if (key === 'SUBSTATION') imgSrc = 'substation_rtu.png';
        else if (key === 'FEEDER') imgSrc = 'feeder_rtu.png';
        else imgSrc = 'home_rtu.png';

        // Modbus Register Overlay Content
        let registerHtml = '';
        let controlsHtml = '';
        
        if (key === 'SUBSTATION') {
            registerHtml = `
                <div class="reg-item"><span class="reg-lbl">HR0: Exported Power</span><span class="reg-val">${data.exported_mw} MW</span></div>
                <div class="reg-item"><span class="reg-lbl">HR1: Generation</span><span class="reg-val">${data.gen_output} MW</span></div>
                <div class="reg-item"><span class="reg-lbl">HR3: Core Temp</span><span class="reg-val">${data.gen_temp} °C</span></div>
                <div class="reg-item"><span class="reg-lbl">CO0: Breaker Status</span><span class="reg-val">${data.gcb_closed ? 'CLOSED' : 'OPEN'}</span></div>
            `;
            controlsHtml = `
                <button class="btn btn-success" onclick="sendCmd('${key}', 'COIL', 0, 1)"><i class="fa-solid fa-power-off"></i> CLOSE GCB</button>
                <button class="btn btn-danger" onclick="sendCmd('${key}', 'COIL', 1, 1)"><i class="fa-solid fa-bolt"></i> TRIP GCB</button>
            `;
        } else if (key === 'FEEDER') {
            registerHtml = `
                <div class="reg-item"><span class="reg-lbl">HR0: Load %</span><span class="reg-val">${data.load_pct} %</span></div>
                <div class="reg-item"><span class="reg-lbl">HR1: Voltage</span><span class="reg-val">${data.voltage} V</span></div>
                <div class="reg-item"><span class="reg-lbl">HR4: Power</span><span class="reg-val">${data.power_kw} kW</span></div>
                <div class="reg-item"><span class="reg-lbl">CO0: Breaker</span><span class="reg-val">${data.breaker_closed ? 'CLOSED' : 'OPEN'}</span></div>
            `;
            controlsHtml = `
                <button class="btn btn-success" onclick="sendCmd('${key}', 'COIL', 0, 1)"><i class="fa-solid fa-power-off"></i> CLOSE</button>
                <button class="btn btn-danger" onclick="sendCmd('${key}', 'COIL', 0, 0)"><i class="fa-solid fa-bolt"></i> TRIP</button>
            `;
        } else {
            registerHtml = `
                <div class="reg-item"><span class="reg-lbl">HR0: Home Load</span><span class="reg-val">${data.load_w} W</span></div>
                <div class="reg-item"><span class="reg-lbl">HR1: Voltage</span><span class="reg-val">${data.voltage} V</span></div>
                <div class="reg-item"><span class="reg-lbl">CO0: Supply Cmd</span><span class="reg-val">${data.supply_on ? 'ON' : 'OFF'}</span></div>
                <div class="reg-item"><span class="reg-lbl">CO1: Overload Trip</span><span class="reg-val">${data.trip ? 'TRIPPED' : 'NORMAL'}</span></div>
            `;
            controlsHtml = `
                <button class="btn btn-success" onclick="sendCmd('${key}', 'COIL', 0, 1)"><i class="fa-solid fa-plug"></i> SUPPLY ON</button>
                <button class="btn btn-danger" onclick="sendCmd('${key}', 'COIL', 0, 0)"><i class="fa-solid fa-ban"></i> SHUT OFF</button>
            `;
        }

        // Card Assembly
        card.style.boxShadow = `0 0 20px ${glowColor} inset`;
        card.innerHTML = `
            <div class="rtu-title-bar">
                <strong><i class="fa-solid fa-server"></i> ${key}</strong>
                ${statusBadge}
            </div>
            <div class="rtu-image-container">
                <img src="/static/images/${imgSrc}" alt="${key}">
            </div>
            
            <div class="register-overlay">
                <h4><i class="fa-solid fa-microchip"></i> PLC Modbus Map</h4>
                <div class="register-grid">
                    ${registerHtml}
                </div>
                <div class="rtu-controls mt-4">
                    ${controlsHtml}
                </div>
            </div>
        `;
        
        grid.appendChild(card);
    });
}

async function sendCmd(target, type, addr, val) {
    if (isIsolated) {
        // Just warning but allowing it according to "trip logic from rtu stating manual mode"
        console.warn("System is Isolated. Sending manual control directly to RTU.");
    }
    await fetch(`${API_BASE}/control`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ target, type, address: addr, value: val })
    });
}

// ---------------- CYBER COMMAND RENDERING ----------------
async function updateDockerTable() {
    try {
        const ifaceSelect = document.getElementById('interface-select');
        const network = ifaceSelect ? ifaceSelect.value : "br-xyb";
        const res = await fetch(`${API_BASE}/containers?network=${network}`);
        const containers = await res.json();
        const tbody = document.querySelector('#docker-table tbody');
        tbody.innerHTML = '';
        containers.forEach(c => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><i class="fa-brands fa-docker text-blue"></i> ${c.name}</td>
                <td><span class="badge badge-green">${c.ip}</span></td>
            `;
            tbody.appendChild(tr);
        });
    } catch(e) {}
}

function updateBreaches(breaches) {
    const tbody = document.querySelector('#breach-table tbody');
    tbody.innerHTML = '';
    
    // Reverse to show latest first
    const recent = [...breaches].reverse().slice(0, 50);
    recent.forEach(b => {
        const tr = document.createElement('tr');
        // Check if it's a generic anomaly
        let badgeClass = 'badge-red';
        if (b.classification && b.classification.includes('Generic Traffic Anomaly')) {
            badgeClass = 'badge-green'; // Less severe
        }
        
        tr.innerHTML = `
            <td style="font-family: monospace; font-size: 0.85rem">${b.timestamp.substring(11, 23)}</td>
            <td>${b.src_ip}:${b.src_port} &rarr; ${b.dst_ip}:${b.dst_port}</td>
            <td><span class="badge ${badgeClass}">${b.classification}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// ---------------- POLLING ----------------
function startPolling() {
    setInterval(pollData, 2000);
    setInterval(() => {
        const d = new Date();
        document.getElementById('clock').innerText = d.toLocaleTimeString();
    }, 1000);
}

async function pollData() {
    try {
        // 1. SCADA Status & Isolation
        const res = await fetch(`${API_BASE}/status`);
        const data = await res.json();
        
        // Handle Global Isolation State
        isIsolated = data.isolation.isolated;
        const alertBox = document.getElementById('global-isolation-alert');
        if (isIsolated) {
            alertBox.classList.remove('hidden');
        } else {
            alertBox.classList.add('hidden');
        }

        // Render SCADA Grid if in SCADA tab
        if (currentTab === 'scada-view') {
            renderScadaGrid(data.scada.rtus);
            updateLiveChart(data.scada.rtus);
        }

        // 2. Cyber Command Data (Only poll if in IDS tab to save bandwidth)
        if (currentTab === 'ids-view') {
            updateDockerTable();
            const logRes = await fetch(`${API_BASE}/ids/logs`);
            const logData = await logRes.json();
            updateBreaches(logData.breaches);
        }

    } catch (e) {
        console.error("Polling error", e);
    }
}

// ---------------- AUTH MODAL ----------------
function triggerIsolate() {
    pendingAuthAction = 'ISOLATE';
    document.getElementById('password-modal').classList.remove('hidden');
}

function triggerUnisolate() {
    pendingAuthAction = 'UNISOLATE';
    document.getElementById('password-modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('password-modal').classList.add('hidden');
    document.getElementById('auth-password').value = '';
    pendingAuthAction = null;
}

async function submitAuth() {
    const pw = document.getElementById('auth-password').value;
    const endpoint = pendingAuthAction === 'ISOLATE' ? '/isolate' : '/unisolate';
    
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ password: pw })
        });
        
        if (res.ok) {
            closeModal();
            // Force immediate poll
            pollData();
        } else {
            alert("Invalid Authorization Code.");
        }
    } catch (e) {
        alert("System error during authorization.");
    }
}

// ---------------- CHART ----------------
function initChart() {
    const ctx = document.getElementById('mainChart').getContext('2d');
    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Feeder Load (%)', data: [], borderColor: 'rgba(59, 130, 246, 1)', tension: 0.4, fill: true, backgroundColor: 'rgba(59, 130, 246, 0.1)' }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, min: 0, max: 120 }
            },
            plugins: { legend: { labels: { color: 'white' } } }
        }
    });
}

function updateLiveChart(rtus) {
    if (!trendChart) return;
    const feeder = rtus['FEEDER'];
    if (feeder && feeder.load_pct !== undefined) {
        const ts = new Date().toLocaleTimeString();
        if (trendChart.data.labels.length > 20) {
            trendChart.data.labels.shift();
            trendChart.data.datasets[0].data.shift();
        }
        trendChart.data.labels.push(ts);
        trendChart.data.datasets[0].data.push(feeder.load_pct);
        trendChart.update('none');
    }
}
