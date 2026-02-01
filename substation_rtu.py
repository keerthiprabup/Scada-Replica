"""
RTU-1 : Generating Side Substation
---------------------------------
• Generator + Generator Transformer + GCB
• Protection logic: GCB trips if exported MW > threshold
• Controller writes to close GCB
• Logs generator, export, forecast, GCB, GT temperature
"""

from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext, ModbusSequentialDataBlock
import threading, time, math, random, json
from datetime import datetime, timezone

# ===================== CONFIG =====================
UNIT_ID = 1
GEN_RATED_MW = 100.0
GEN_MIN_MW = 20.0
GEN_RAMP_RATE_MW_PER_SEC = 2.0
GT_MAX_TEMP_C = 90
GT_AMBIENT_TEMP_C = 35
SIM_MINUTES_PER_SEC = 10
LOG_INTERVAL_SEC = 3
GCB_TRIP_MW = 80.0  # Power threshold to trip
LOG_FILE = "log.json"

# ===================== MODBUS DATASTORE =====================
def create_datastore():
    return ModbusSlaveContext(
        co=ModbusSequentialDataBlock(0, [1] + [0]*9),
        hr=ModbusSequentialDataBlock(0, [0]*20)
    )

context = ModbusServerContext(slaves={UNIT_ID: create_datastore()}, single=False)

# ===================== THERMAL MODEL =====================
def calculate_gt_temperature(load_pct, current_temp):
    target = GT_AMBIENT_TEMP_C + (GT_MAX_TEMP_C - GT_AMBIENT_TEMP_C) * (load_pct / 100)**2
    return current_temp + (target - current_temp) * 0.05

# ===================== RTU LOGIC =====================
def rtu_logic():
    print(f"[RTU-{UNIT_ID}] Substation RTU started")
    gen_output_mw = 50.0
    gt_temp = GT_AMBIENT_TEMP_C + 5
    simulated_hour = 0.0
    simulated_hour = 0.0
    last_log_time = time.time()
    
    # Explicitly initialize coils (Fix for pymodbus init issue)
    # CO0=1 (GCB Closed)
    context[UNIT_ID].setValues(1, 0, [1])

    coil_values = context[UNIT_ID].getValues(1, 0, count=1)
    gcb_closed = bool(coil_values[0]) if coil_values else True
    last_gcb_state = gcb_closed
    print(f"[RTU-{UNIT_ID}] Initial GCB status = {'CLOSED' if gcb_closed else 'OPEN'}")

    while True:
        try:
            # ================= PLC LOGIC PIPELINE =================
            t_rx = time.time()  # Time of input reception (Read)
            
            # 1. INPUT PROCESSING
            # Read SCADA inputs (Coils)
            coil_values = context[UNIT_ID].getValues(1, 0, count=1)
            scada_cmd_close = bool(coil_values[0]) if coil_values else False
            
            # Read Physical inputs (Simulated sensors)
            # Simulated interactions
            simulated_hour = (simulated_hour + SIM_MINUTES_PER_SEC / 60) % 24
            
            # 2. PHYSICAL ABSTRACTION LAYER (Rule-Based Model)
            # Forecast & Ramp
            forecast_mw = 50 + 15*math.sin((simulated_hour-6)*math.pi/12) + random.uniform(-1.5,1.5)
            forecast_mw = max(GEN_MIN_MW, min(forecast_mw, GEN_RATED_MW))
            
            if forecast_mw > gen_output_mw:
                gen_output_mw += min(GEN_RAMP_RATE_MW_PER_SEC, forecast_mw - gen_output_mw)
            else:
                gen_output_mw -= min(GEN_RAMP_RATE_MW_PER_SEC, gen_output_mw - forecast_mw)

            # 3. PROTECTION LOGIC BLOCKS
            # Check constraints
            exported_mw_pre = gen_output_mw if last_gcb_state else 0.0 # Estimate based on current state
            protection_trip = exported_mw_pre > GCB_TRIP_MW
            
            if protection_trip:
                 print(f"[RTU-{UNIT_ID}] ⚠️ PROTECTION TRIP: Overload ({exported_mw_pre:.1f} > {GCB_TRIP_MW})")

            # 4. CONTROL COMMAND BLOCKS & OUTPUT CONDITIONING
            # Resolve State: Protection overrides SCADA
            if protection_trip:
                gcb_closed = False
            else:
                gcb_closed = scada_cmd_close

            t_update = time.time() # Time of state update
            
            # Actual Physical Outputs
            exported_mw = gen_output_mw if gcb_closed else 0.0
            gt_load_pct = (exported_mw/GEN_RATED_MW)*100
            gt_temp = calculate_gt_temperature(gt_load_pct, gt_temp)

            # Update Modbus Outputs (Feedback to SCADA)
            context[UNIT_ID].setValues(3,0,[
                int(exported_mw*10), int(gen_output_mw*10),
                int(forecast_mw*10), int(gt_temp)
            ])
            
            # Only sync the coil if our internal state differs from the register (due to protection trip)
            # The SCADA "sees" the trip when it polls and sees 0. 
            if gcb_closed != scada_cmd_close:
                 context[UNIT_ID].setValues(1, 0, [int(gcb_closed)])

            # Explicit State Logging
            if gcb_closed != last_gcb_state:
                print(f"[RTU-{UNIT_ID}] GCB changed → {'CLOSED' if gcb_closed else 'OPEN'}")
                last_gcb_state = gcb_closed

            # 30-min log (Enhanced)
            if time.time()-last_log_time >= LOG_INTERVAL_SEC:
                log_entry = {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "t_rx": t_rx,
                    "t_update": t_update,
                    "latency_delta": t_update - t_rx,
                    "simulated_hour": round(simulated_hour,2),
                    "generator_mw": round(gen_output_mw,2),
                    "exported_mw": round(exported_mw,2),
                    "protection_trip": protection_trip,
                    "gcb_status": "CLOSED" if gcb_closed else "OPEN"
                }
                with open(LOG_FILE,"a") as f:
                    json.dump(log_entry,f)
                    f.write(",\n")
                last_log_time = time.time()
                
            time.sleep(1)

        except Exception as e:
            print(f"[RTU-{UNIT_ID}] ERROR: {e}")
            time.sleep(1)

# Start RTU thread
threading.Thread(target=rtu_logic,daemon=True).start()
print(f"[RTU-{UNIT_ID}] Modbus TCP server listening on 0.0.0.0:5002")
StartTcpServer(context=context,address=("0.0.0.0",5002))
