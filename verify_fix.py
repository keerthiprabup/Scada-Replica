from pymodbus.client import ModbusTcpClient
import time

def test():
    print("Connecting to RTUs...")
    # Ports are mapped to localhost: 5003 (Feeder) and 5004 (Home)
    feeder = ModbusTcpClient('localhost', port=5003)
    home = ModbusTcpClient('localhost', port=5004)
    
    if not feeder.connect():
        print("Failed to connect to Feeder RTU")
        return
    if not home.connect():
        print("Failed to connect to Home RTU")
        return
    
    print("\n--- TEST 1: Normal Operation ---")
    # Close Feeder Breaker (Cmd=True)
    print("Closing Feeder Breaker...")
    feeder.write_coil(0, True, slave=2)
    time.sleep(2)
    
    # Check Home Supply
    rr = home.read_coils(0, 1, slave=3)
    if rr and not rr.isError():
        home_supply = rr.bits[0]
        print(f"Feeder Closed -> Home Supply: {home_supply} (Expected: True)")
    else:
        print("Error reading Home Supply")

    print("\n--- TEST 2: Trip/Open Feeder ---")
    # Open Feeder Breaker (Cmd=False)
    print("Opening Feeder Breaker...")
    feeder.write_coil(0, False, slave=2)
    time.sleep(2)
    
    # Check Feeder Power (HR4)
    # Note: Logic says if breaker open, load -> 0.
    rr = feeder.read_holding_registers(0, 1, slave=2) # HR0 is Load %
    if rr and not rr.isError():
        feeder_load = rr.registers[0]
        print(f"Feeder Open -> Feeder Load: {feeder_load}% (Expected: 0)")
    else:
        print("Error reading Feeder Load")
        
    # Check Home Supply
    rr = home.read_coils(0, 1, slave=3)
    if rr and not rr.isError():
        home_supply_trip = rr.bits[0] 
        print(f"Feeder Open -> Home Supply: {home_supply_trip} (Expected: False)")
    else:
        print("Error reading Home Supply")
    
    feeder.close()
    home.close()

if __name__ == "__main__":
    test()
