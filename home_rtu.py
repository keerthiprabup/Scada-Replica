"""
RTU 3: Home (230V Consumer)
Simulates residential consumer with realistic load patterns
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
import math
import os
from pymodbus.client import ModbusTcpClient

# Electrical Parameters
HOME_VOLTAGE_V = 230
HOME_CONTRACT_LOAD_KW = float(os.getenv("CONTRACT_LOAD_KW", 5.0))
HOME_MIN_LOAD_KW = 0.3  # Base load (refrigerator, etc.)

# Unit ID
UNIT_ID = int(os.getenv("UNIT_ID", 3))

# Modbus Register Map:
# Holding Registers (HR):
#   HR0: Home Load (W) - actual load in watts
#   HR1: Voltage (V)
#   HR2: Current (A) - scaled by 10
#   HR3: Energy Consumed Today (kWh) - scaled by 10
#   HR4: Power Factor (x100)
# Coils (CO):
#   CO0: Supply Available (1=on, 0=off)
#   CO1: Overload Trip (1=tripped)
#   CO2: Load Shed Command (1=load reduced, 0=normal)


def create_datastore():
    """Create modbus datastore for home RTU"""
    return ModbusSlaveContext(
        co=ModbusSequentialDataBlock(0, [1, 0, 0] + [0]*7),
        di=ModbusSequentialDataBlock(0, [0]*10),
        hr=ModbusSequentialDataBlock(0, [0]*20),
        ir=ModbusSequentialDataBlock(0, [0]*10)
    )


context = ModbusServerContext(slaves={UNIT_ID: create_datastore()}, single=False)


def calculate_home_load(hour_of_day):
    """Calculate realistic home load based on time of day"""
    # Typical residential load pattern
    # Low: 2-6 AM (sleeping)
    # Medium: 6-9 AM, 12-5 PM (morning/afternoon)
    # High: 6-11 PM (evening peak)
    
    hour = int(hour_of_day)
    
    if 2 <= hour < 6:
        base = 0.5  # Night - minimal load
    elif 6 <= hour < 9:
        base = 2.5  # Morning - cooking, shower
    elif 9 <= hour < 12:
        base = 1.2  # Late morning
    elif 12 <= hour < 17:
        base = 1.5  # Afternoon
    elif 17 <= hour < 23:
        base = 3.5  # Evening peak - cooking, AC, lights, TV
    else:
        base = 1.0  # Late night
    
    # Add random variation for appliances switching on/off
    variation = random.uniform(-0.3, 0.5)
    return max(HOME_MIN_LOAD_KW, base + variation)


def home_logic():
    """Main RTU logic for home consumer"""
    print(f"[RTU-{UNIT_ID}] Home RTU started")
    print(f"[RTU-{UNIT_ID}] Consumer: {HOME_VOLTAGE_V}V, {HOME_CONTRACT_LOAD_KW}kW contract")
    
    # Initialize
    hour_of_day = 8.0  # Start at 8 AM
    energy_today_kwh = 0
    last_time = time.time()
    
    # Connect to Feeder RTU
    feeder_ip = os.getenv("FEEDER_IP", "127.0.0.1")
    feeder_client = ModbusTcpClient(feeder_ip, port=5003)

    # Explicitly initialize coils (Fix for pymodbus init issue)
    # CO0=1 (Supply Available)
    context[UNIT_ID].setValues(1, 0, [1, 0, 0])
    
    while True:
        try:
            # Time simulation (1 sec = 10 min)
            hour_of_day = (hour_of_day + 0.167) % 24
            
            # Reset energy at midnight
            if hour_of_day < 0.167:
                energy_today_kwh = 0
            
            # ================= PLC LOGIC PIPELINE =================
            t_rx = time.time()
            
            # 1. INPUT PROCESSING
            # Read SCADA inputs
            coil_values = context[UNIT_ID].getValues(1, 0, count=3)
            supply_cmd_on = bool(coil_values[0])
            load_shed_cmd = bool(coil_values[2])
            
            # Check Feeder Status (Upstream)
            upstream_power = True
            try:
                if not feeder_client.connected:
                    feeder_client.connect()
                # Read Feeder Coil 0 (Breaker Status)
                rr = feeder_client.read_coils(0, count=1, slave=2)
                if rr and not rr.isError():
                    upstream_power = rr.bits[0]
                else:
                    upstream_power = False # Fail-safe
            except Exception:
                upstream_power = False
            
            # 2. PHYSICAL ABSTRACTION
            # Calculate demand
            demand_kw = calculate_home_load(hour_of_day)
            
            # Apply Load Shedding (Physical response to command)
            if load_shed_cmd:
                demand_kw = min(demand_kw, HOME_MIN_LOAD_KW + 0.5)
                
            # 3. PROTECTION LOGIC
            overload_trip = demand_kw > HOME_CONTRACT_LOAD_KW
            
            if overload_trip:
                 print(f"[RTU-{UNIT_ID}] ⚠️ OVERLOAD TRIP! Load={demand_kw:.2f}kW > {HOME_CONTRACT_LOAD_KW}kW")

            # 4. CONTROL COMMAND & OUTPUT CONDITIONING
            # Supply Status
            if overload_trip:
                supply_on = False
            else:
                supply_on = supply_cmd_on and upstream_power
            
            # Actual Load
            load_kw = demand_kw if supply_on else 0

            # Electrical Params
            if load_kw > 0:
                voltage = HOME_VOLTAGE_V * (0.95 + random.uniform(0, 0.1))
                current = (load_kw * 1000) / voltage
                power_factor = 0.90 + random.uniform(-0.05, 0.05)
                
                # Energy accumulation
                current_time = time.time()
                time_diff_hours = (current_time - last_time) / 3600 * 6
                energy_today_kwh += load_kw * time_diff_hours
                last_time = current_time
            else:
                 voltage, current, power_factor = 0, 0, 0
                 last_time = time.time()
            
            t_update = time.time()

            # Modbus Output (Registers)
            context[UNIT_ID].setValues(3, 0, [
                int(load_kw * 1000), int(voltage), int(current * 10),
                int(energy_today_kwh * 10), int(power_factor * 100)
            ])
            
            # Modbus Output (Coils - feedback)
            # CO1: Overload Trip (Output)
            context[UNIT_ID].setValues(1, 1, [int(overload_trip)])

            # CO0: Supply Status (Feedback if different from command)
            if supply_on != supply_cmd_on:
                 context[UNIT_ID].setValues(1, 0, [int(supply_on)])
                 
            if int(hour_of_day) % 3 == 0 and hour_of_day % 3 < 0.167:
                status = "ON" if supply_on else "OFF"
                shed_str = " [SHED]" if load_shed_cmd else ""
                print(f"[RTU-{UNIT_ID}] Hour {int(hour_of_day):02d}:00 | "
                      f"Load={load_kw:.2f}kW | Supply={status}{shed_str}")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"[RTU-{UNIT_ID}] Error: {e}")
            time.sleep(1)


# Start logic thread
threading.Thread(target=home_logic, daemon=True).start()

# Start Modbus server
print(f"[RTU-{UNIT_ID}] Starting Modbus TCP server on 0.0.0.0:5004")
StartTcpServer(context=context, address=("0.0.0.0", 5004))
