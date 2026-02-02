async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        if (!data.rtus) return;

        updateUI(data.rtus);
        document.getElementById('clock').innerText = new Date(data.timestamp).toLocaleTimeString();
    } catch (e) {
        console.error("Fetch error:", e);
    }
}

function updateUI(rtus) {
    // Substation
    if (rtus.SUBSTATION) {
        document.getElementById('gen-mw').innerText = rtus.SUBSTATION.exported_mw.toFixed(1) + " MW";
        document.getElementById('gen-temp').innerText = rtus.SUBSTATION.gen_temp + " °C";
        document.getElementById('gen-status').style.background = rtus.SUBSTATION.gcb_closed ? "var(--accent)" : "#555";
        document.getElementById('gen-status').innerText = rtus.SUBSTATION.gcb_closed ? "GCB CLOSED" : "GCB OPEN";
    }

    // Feeder
    if (rtus.FEEDER) {
        const f = rtus.FEEDER;
        document.getElementById('feeder-kw').innerText = f.power_kw.toFixed(1) + " kW";
        document.getElementById('feeder-v').innerText = f.voltage + " V";
        document.getElementById('feeder-a').innerText = f.current + " A";

        const cbStatus = document.getElementById('feeder-cb-status');
        cbStatus.innerText = f.breaker_closed ? "BREAKER CLOSED" : "BREAKER OPEN / TRIPPED";
        cbStatus.style.color = f.breaker_closed ? "var(--accent)" : "var(--danger)";

        const alarm = document.getElementById('feeder-alarm');
        if (f.overload_alarm) {
            alarm.classList.remove('hidden');
        } else {
            alarm.classList.add('hidden');
        }
    }

    // Homes
    const container = document.getElementById('home-container');
    container.innerHTML = '';

    Object.keys(rtus).forEach(key => {
        if (key.startsWith('HOME')) {
            const h = rtus[key];
            const div = document.createElement('div');
            const isOn = h.supply_on;
            div.className = `home-card ${isOn ? 'on' : 'off'}`;

            div.innerHTML = `
                <div class="home-header">
                    <strong>${key}</strong>
                    <span>${h.voltage} V</span>
                </div>
                <div class="metrics" style="margin-bottom: 5px;">
                    <span>Wait: ${h.load_w} W</span>
                    <span>Total: ${h.energy_kwh.toFixed(1)} kWh</span>
                </div>
                <div style="text-align:right; font-size:0.8em;">
                    ${h.trip ? '<span style="color:var(--danger)">TRIPPED</span>' : (isOn ? 'ONLINE' : 'OFFLINE')}
                </div>
            `;
            container.appendChild(div);
        }
    });
}

async function control(target, action) {
    await fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, action })
    });
    fetchStatus(); // Refresh immediately
}

setInterval(fetchStatus, 1000);
fetchStatus();
