# SCADA Attack Demo

This document outlines the sample commands and expected behaviors for the four primary attack vectors: **Command Injection**, **Denial of Service (DoS)**, **Replay Attack**, and **False Data Injection (FDI)**. It also serves as a reference for the Modbus network layout.

## 🧭 Network & Protocol Reference

Before executing attacks, you must understand how to target specific devices and data points within the simulated SCADA network.

### 1. Selecting the Target & Unit ID
In Modbus TCP, a single IP address can host multiple logical devices, differentiated by a **Unit ID** (also called Slave ID). In our dockerized environment:

| RTU Name | Container IP / Target | Modbus Port | Unit ID | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Substation** | `substation` / `172.20.0.x` | 5002 | **1** | Controls the main power generation and Grid Circuit Breaker. |
| **Feeder** | `feeder` / `172.20.0.x` | 5003 | **2** | Distributes power from substation to homes. |
| **Home 1** | `home` / `172.20.0.x` | 5004 | **3** | End consumer load. |
| **Home 2** | `home2` / `172.20.0.x` | 5004 | **4** | End consumer load. |
| **Home 3** | `home3` / `172.20.0.x` | 5004 | **5** | End consumer load. |

### 2. Modbus Register Map
Modbus uses two primary memory spaces that we target in these attacks:
*   **Coils (Function 05/01)**: 1-bit boolean values (True/False or ON/OFF). Used for Actuators (Breakers, Switches).
*   **Holding Registers (Function 06/03)**: 16-bit integer values (0-65535). Used for Sensors (Voltage, Power, Load).

Below is the unified mapping for your RTUs:

| RTU | Type | Address | Signal Name | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Generator (Substation)** | Coil | 0 | `Gen_Close_Cmd` | Generator breaker close command |
| | Coil | 1 | `Gen_Open_Cmd` | Generator breaker open command |
| | Coil | 2 | `Gen_Reset` | Trip reset after fault clearance |
| | Coil | 3 | `Gen_Trip` | Latched generator trip indication |
| | Coil | 4 | `GCB_Status` | Generator circuit breaker state |
| | Holding Reg | 0 (40001) | `Gen_Power` | Generated power output |
| | Holding Reg | 1 (40002) | `Gen_Temp` | Generator temperature |
| | Holding Reg | 2 (40003) | `Gen_Overload` | Generator overload flag |
| **Feeder** | Coil | 0 | `Feeder_Close_Cmd` | Feeder breaker close command |
| | Coil | 1 | `Feeder_Open_Cmd` | Feeder breaker open command |
| | Coil | 2 | `Feeder_Reset` | Trip reset after overload |
| | Coil | 3 | `Feeder_Trip` | Latched feeder trip status |
| | Coil | 4 | `Feeder_Status` | Feeder breaker state |
| | Holding Reg | 0 (40001) | `Feeder_Load` | Feeder load demand |
| | Holding Reg | 1 (40002) | `Feeder_Current`| Feeder current magnitude |
| | Holding Reg | 2 (40003) | `Feeder_Overload`| Feeder overload flag |
| **Home** | Coil | 0 | `Supply_Enable` | Consumer supply enable |
| | Coil | 1 | `Manual_Disconnect` | Manual disconnection command |
| | Coil | 2 | `Home_Reset` | Trip reset after fault |
| | Coil | 3 | `Home_Trip` | Latched overload trip |
| | Coil | 4 | `Supply_Status` | Consumer supply state |
| | Holding Reg | 0 (40001) | `Home_Load` | Consumer load demand |
| | Holding Reg | 1 (40002) | `Home_Current` | Consumer current |
| | Holding Reg | 2 (40003) | `Home_Overload` | Overload condition flag |

*(Note: While documentation often lists registers starting at `40001`, the protocol address transmitted over the network is `0`. The scripts use the zero-indexed network address).*

---

## 🎯 Scenario Context
You are demonstrating the project with the following state:
- **System State**: Unisolated (Normal Operation).
- **Intrusion Detection System (IDS)**: **ON** and monitoring the `br-xyb` network.

The attacker has gained access to the SCADA network (`br-xyb`) and is executing these scripts.

---

## 1. Command Injection (Direct Actuator Control)
**Objective**: Bypass the HMI and send direct Modbus commands to open or close physical breakers.

**How it works**: The attacker sends a "Write Single Coil" (Function 05) command to an actuator address.

### 🛠️ Sample Command: Trip the Feeder Breaker
To force the Feeder breaker to open, we target the Feeder (Unit 2) and send `1` (True) to Coil address `1` (`Feeder_Open_Cmd`):
```bash
python attack_scripts/command_injection.py --target feeder --port 5003 --unit 2 write-coil 1 1
```

### 👁️ Expected Outcome
1. **SCADA Impact**: The Feeder breaker will immediately open, cutting power to downstream Home RTUs.
2. **IDS Response**: If the IDS is trained to recognize that breaker commands should only originate from the `scada_master` IP, it will detect this unexpected packet from the attacker's IP and immediately **Isolate the System**.

---

## 2. False Data Injection (FDI) / Sensor Spoofing
**Objective**: Overwrite Holding Registers to feed false sensor data (e.g., voltage or load spikes) to the HMI and automated logic.

**How it works**: The attacker sends a "Write Single Register" (Function 06) command to alter a sensor value before the SCADA Master polls it.

### 🛠️ Sample Command: Spoof Feeder Load
To change the Feeder Load to an extreme value, we target the Feeder (Unit 2) and write `9999` to Holding Register address `0` (`Feeder_Load`):
```bash
python attack_scripts/command_injection.py --target feeder --port 5003 --unit 2 write-reg 0 9999
```

### 👁️ Expected Outcome
1. **SCADA Impact**: The HMI will briefly show a massive, physically impossible load spike on the Feeder.
2. **IDS Response**: The Isolation Forest model will immediately flag this as an anomaly (because 9999 is far outside normal operational parameters) and **Isolate the System**, protecting the grid from making automated decisions based on fake data.

---

## 3. Denial of Service (DoS / Query Flood)
**Objective**: Exhaust the RTU's connection pool and CPU resources, causing it to drop legitimate SCADA traffic.

**How it works**: The script spawns numerous concurrent threads that aggressively open Modbus TCP connections and send junk "Read Holding Registers" requests in an infinite loop.

### 🛠️ Sample Command: Flood the Master RTU
To launch a flood against the MasterRTU:
```bash
python attack_scripts/dos_flood.py --target ScadaMaster --port 5000 --size 2000 --rate 10000
```
*(Press `Ctrl+C` to halt the attack)*

### 👁️ Expected Outcome
1. **SCADA Impact**: The SCADA Master will fail to poll the Substation. The Maintenance Dashboard will show a `TIMEOUT` or `OFFLINE` status for the Substation.
2. **IDS Response**: The massive influx of network traffic and connection attempts will trigger a network anomaly. The IDS will detect the DoS signature and **Isolate the System**.

---

## 4. Replay Attack (State Lockout) (Needs packet analysation[time consuming])
**Objective**: Prevent legitimate SCADA operators from changing the state of a device by aggressively replaying (overwriting) its shared packets.


### 👁️ Expected Outcome
1. **SCADA Impact**: While the script is running, if the operator uses the Dashboard to click "Turn OFF" for the Home RTU, the HMI might temporarily show it as off, but the replay script will immediately overwrite it back to ON within milliseconds. The operator loses control of the actuator.
2. **IDS Response**: The IDS will detect an unnaturally high frequency of Write commands targeting the same register and flag it as an anomaly, subsequently **Isolating the System**.

---

> [!TIP]
> **Demo Flow Recommendation:**
> 1. Start with the Dashboard running normally and the IDS turned ON.
> 2. Explain the vulnerability of Modbus TCP (no authentication, plaintext) and briefly show the Modbus Map.
> 3. Execute **False Data Injection**. Watch the HMI spike, and then observe the IDS immediately catch the anomaly and trigger Isolation.
> 4. Use the Maintenance Dashboard to **Unisolate** the system (requires the admin password).
> 5. Proceed to demonstrate the next attack (e.g., Command Injection).
