"""
Day 1 goal: see live lat/lon/altitude printing in your terminal.

Run ArduPilot SITL first:
    cd ardupilot/ArduCopter
    ../Tools/autotest/sim_vehicle.py --console --map

Then, in another terminal:
    python first_telemetry.py
"""

from pymavlink import mavutil

# Connect to SITL's default MAVLink output.
# SITL prints the udp target it's broadcasting to on startup — match that port.
master = mavutil.mavlink_connection("udpin:localhost:14550")

print("Waiting for heartbeat...")
master.wait_heartbeat()
print(f"Heartbeat received from system {master.target_system} component {master.target_component}")

while True:
    msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True)
    if msg is None:
        continue

    lat = msg.lat / 1e7
    lon = msg.lon / 1e7
    alt = msg.alt / 1000  # mm -> m

    print(f"Lat: {lat:.6f}, Lon: {lon:.6f}, Alt: {alt:.1f} m")
