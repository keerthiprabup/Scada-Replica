"""
RTU 2: Feeder (415V Distribution)
Simulates a distribution feeder with load management capabilities
"""
from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusServerContext,
    ModbusSlaveContext,
    ModbusSequentialDataBlock
)
import threading
import random
import time

# Electrical Parameters
FEEDER_RATED_VOLTAGE_V = 415
FEEDER_RATED_CURRENT_A = 400
FEEDER_RATED_LOAD_PCT = 85
FEEDER_LENGTH_KM = 2.5

# Unit ID
UNIT_ID = 2

# Modbus Register Map:
# Holding Registers (HR):
#   HR0: Feeder Load (%)
#   HR1: Line Voltage (V)
#   HR2: Line Current (A)
#   HR3: Power Factor (x100, e.g., 85 = 0.85)
#   HR4: Total Power (kW) - scaled by 10
# Coils (CO):
#   CO0: Feeder Breaker Status (1=closed, 0=open)
#   CO1: Load Shedding Active (1=active, 0=inactive)
#   CO2: Overload Alarm (1=alarm)
#   CO3: Upstream Available (1=power available from substation)


def create_datastore():
    """Create modbus datastore for feeder RTU"""
    return ModbusSlaveContext(
        co=ModbusSequentialDataBlock(0, [1, 0, 0, 1] + [0]*6),
        di=ModbusSequentialDataBlock(0, [0]*10),
        hr=ModbusSequentialDataBlock(0, [0]*20),
        ir=ModbusSequentialDataBlock(0, [0]*10)
    )


context = ModbusServerContext(slaves={UNIT_ID: create_datastore()}, single=False)


def feeder_logic():
    """Main RTU logic for feeder"""
    print(f"[RTU-{UNIT_ID}] Feeder RTU started")
    print(f"[RTU-{UNIT_ID}] Feeder: {FEEDER_RATED_VOLTAGE_V}V, {FEEDER_RATED_CURRENT_A}A, {FEEDER_LENGTH_KM}km")
    
    # Initialize
    feeder_load = 50.0
    load_shed_timer = 0
    
    while True:
        try:
            # ================= PLC LOGIC PIPELINE =================
            t_rx = time.time()
            
            # 1. INPUT PROCESSING
            # Read SCADA/Simulated Input Registers
            # For Feeder, Upstream Coils are inputs from Substation (simulated here via simple logic or direct writes)
            # In this sim, we check our own coil to see if upstream is valid (conceptually pushed by SCADA or sensed)
            coil_values = context[UNIT_ID].getValues(1, 0, count=4)
            breaker_cmd_close = bool(coil_values[0])
            load_shed_cmd = bool(coil_values[1])
            upstream_available = bool(coil_values[3]) # CO3 - Usually sensed voltage
            
            # 2. PHYSICAL ABSTRACTION
            # Load dynamics
            if upstream_available and breaker_cmd_close: # Only if biologically closed (before trip logic)
                 # Natural load variation
                 feeder_load += random.uniform(-2, 3)
                 feeder_load = max(25, min(feeder_load, 95))
            else:
                 feeder_load = 0
            
            # 3. PROTECTION LOGIC
            overload_trip = feeder_load > FEEDER_RATED_LOAD_PCT
            
            # Load Shed Logic (PLC Logic)
            if overload_trip:
                load_shed_timer += 1
            else:
                load_shed_timer = 0
                
            auto_load_shed = False
            if load_shed_timer > 5:
                auto_load_shed = True
                
            # 4. CONTROL COMMAND & OUTPUT CONDITIONING
            # Breaker Status
            if overload_trip:
                breaker_closed = False # Trip
            else:
                breaker_closed = breaker_cmd_close # Follow SCADA
            
            # Load Shed Status (Union of SCADA cmd and Auto Logic)
            final_load_shed = load_shed_cmd or auto_load_shed
            
            if final_load_shed and feeder_load > 0:
                 feeder_load *= 0.7 # Physical effect of load shedding
                 
            # Calculate Electrical Params
            if feeder_load > 0:
                voltage = FEEDER_RATED_VOLTAGE_V * (1.0 - (feeder_load / 100.0) * 0.08)
                current = (feeder_load / 100.0) * FEEDER_RATED_CURRENT_A
                power_factor = 0.87 + random.uniform(-0.03, 0.03)
                total_power_kw = (voltage * current * math.sqrt(3) * power_factor) / 1000
            else:
                voltage, current, power_factor, total_power_kw = 0, 0, 0, 0

            t_update = time.time()
            
            # Modbus Outputs
            context[UNIT_ID].setValues(3, 0, [
                int(feeder_load), int(voltage), int(current),
                int(power_factor * 100), int(total_power_kw * 10)
            ])
            
            # Update Feedback Coils (Only what we control/tripped)
            # CO0: Breaker
            if breaker_closed != breaker_cmd_close:
                 context[UNIT_ID].setValues(1, 0, [int(breaker_closed)])

            # CO2: Overload Alarm
            context[UNIT_ID].setValues(1, 2, [int(overload_trip)])

            # CO1: Load Shed Status (Feedback)
            if final_load_shed != load_shed_cmd:
                 context[UNIT_ID].setValues(1, 1, [int(final_load_shed)])
                 
            time.sleep(1)

            
        except Exception as e:
            print(f"[RTU-{UNIT_ID}] Error: {e}")
            time.sleep(1)


# Import math for calculations
import math

# Start logic thread
threading.Thread(target=feeder_logic, daemon=True).start()

# Start Modbus server
print(f"[RTU-{UNIT_ID}] Starting Modbus TCP server on 0.0.0.0:5003")
StartTcpServer(context=context, address=("0.0.0.0", 5003))
