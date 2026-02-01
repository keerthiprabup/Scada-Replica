import asyncio
from pymodbus.server.async_io import StartTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext, ModbusSequentialDataBlock

UNIT_ID = 1
PORT = 502

store = ModbusSlaveContext(
    di=ModbusSequentialDataBlock(0, [0]*4),
    co=ModbusSequentialDataBlock(0, [0]*4),
    hr=ModbusSequentialDataBlock(0, [0]*10),
    ir=ModbusSequentialDataBlock(0, [0]*10),
)
context = ModbusServerContext(slaves={UNIT_ID: store}, single=False)

async def run_server_for(seconds):
    server_task = asyncio.create_task(
        StartTcpServer(context=context, host="0.0.0.0", port=PORT)
    )
    await asyncio.sleep(seconds)  # run for X seconds
    server_task.cancel()
    print("Server stopped after timeout")

asyncio.run(run_server_for(5))  # run server for 5 seconds
