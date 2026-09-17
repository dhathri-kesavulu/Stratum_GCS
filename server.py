"""
Multi-Vehicle GCS backend.

Connects to ArduPilot SITL instances over MAVLink/UDP — both ArduCopter
(UAV) and ArduPilot Rover (UGV) are the same protocol, just different
vehicle firmware — streams telemetry to the browser over WebSocket, and
accepts click-to-fly / drive waypoint + speed commands.

Run:
    uvicorn server:app --reload
Then open http://localhost:8000/static/index.html
"""

import asyncio
import json
import time
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pymavlink import mavutil

from mock_telemetry import MockDrone

# --- Config -------------------------------------------------------------

# Each vehicle gets a composite key "type:id", matching the frontend's
# scheme exactly — so UAV_1 and UGV_1 are never confused with each other.
# port = the UDP port that SITL instance broadcasts telemetry on.
VEHICLES = {
    "uav:1": {"type": "uav", "port": 14550},   # ArduCopter SITL
    "uav:2": {"type": "uav", "port": 14560},   # ArduCopter SITL
    "ugv:1": {"type": "ugv", "port": 14570},   # ArduPilot Rover SITL
    # add more entries here as you bring up more SITL instances (up to 6 per type)
}

HEARTBEAT_TIMEOUT_S = 5   # how long to wait for real SITL before falling back to mock
FORCE_MOCK = False        # set True to skip SITL entirely and demo with mock data only

# --- App state ------------------------------------------------------------

app = FastAPI()

connections: Dict[str, "mavutil.mavfile"] = {}   # key -> real MAVLink connection
mock_drones: Dict[str, MockDrone] = {}           # key -> mock fallback source
clients: Set[WebSocket] = set()


def try_connect_real(key: str, port: int):
    """Attempt a real SITL connection; return the connection or None."""
    try:
        conn = mavutil.mavlink_connection(f"udpin:localhost:{port}")
        conn.wait_heartbeat(timeout=HEARTBEAT_TIMEOUT_S)
        print(f"[{key}] real heartbeat on port {port}")
        return conn
    except Exception as e:
        print(f"[{key}] no SITL heartbeat on port {port} ({e}) — using mock")
        return None


@app.on_event("startup")
async def start_telemetry():
    loop = asyncio.get_event_loop()
    for key, cfg in VEHICLES.items():
        conn = None
        if not FORCE_MOCK:
            conn = await loop.run_in_executor(None, try_connect_real, key, cfg["port"])
        if conn is not None:
            connections[key] = conn
        else:
            drone_id = int(key.split(":")[1])
            mock_drones[key] = MockDrone(drone_id, vehicle_type=cfg["type"])

    asyncio.create_task(telemetry_loop())


async def telemetry_loop():
    """Poll every real connection + generate mock samples, broadcast to clients."""
    loop = asyncio.get_event_loop()
    while True:
        samples = []

        for key, conn in connections.items():
            vehicle_type = VEHICLES[key]["type"]
            drone_id = int(key.split(":")[1])
            msg = await loop.run_in_executor(
                None, conn.recv_match, "GLOBAL_POSITION_INT", None, False
            )
            if msg is not None:
                samples.append({
                    "drone_id": drone_id,
                    "vehicle_type": vehicle_type,
                    "lat": msg.lat / 1e7,
                    "lon": msg.lon / 1e7,
                    "alt": msg.alt / 1000,
                    "heading": msg.hdg / 100 if msg.hdg != 65535 else 0,
                    "speed": ((msg.vx ** 2 + msg.vy ** 2) ** 0.5) / 100,  # cm/s -> m/s
                    "battery": None,
                    "mock": False,
                })

        for key, mock in mock_drones.items():
            samples.append(mock.next_sample())

        if samples and clients:
            payload = json.dumps({"type": "telemetry", "drones": samples, "t": time.time()})
            dead = set()
            for ws in clients:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.add(ws)
            clients.difference_update(dead)

        await asyncio.sleep(0.2)


def send_goto(vehicle_type: str, drone_id: int, lat: float, lon: float, alt: float = 20.0, speed: float = None):
    """Send a guided-mode waypoint command (and optional speed change) to a real
    vehicle. For mock vehicles, updates the mock's target instead. Works
    identically for UAV (ArduCopter) and UGV (Rover) — MAVLink's guided-mode
    position command is the same regardless of vehicle frame."""
    key = f"{vehicle_type}:{drone_id}"
    conn = connections.get(key)

    if conn is None:
        mock = mock_drones.get(key)
        if mock is not None:
            mock.set_target(lat, lon, alt, speed if speed is not None else 5.0)
            print(f"[{key}] goto ({lat}, {lon}, {alt}m, {speed} m/s) — mock target updated")
        return

    if speed is not None:
        send_change_speed(vehicle_type, drone_id, speed)

    conn.mav.set_position_target_global_int_send(
        0,                                   # time_boot_ms
        conn.target_system,
        conn.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        0b0000111111111000,                  # type_mask: use position only
        int(lat * 1e7),
        int(lon * 1e7),
        alt,
        0, 0, 0,   # vx, vy, vz
        0, 0, 0,   # afx, afy, afz
        0, 0,      # yaw, yaw_rate
    )
    print(f"[{key}] goto ({lat}, {lon}, {alt}m) sent")


def send_change_speed(vehicle_type: str, drone_id: int, speed: float):
    """Send a groundspeed change command to a real vehicle. Independent of the
    waypoint itself — MAVLink treats speed and position as separate commands."""
    key = f"{vehicle_type}:{drone_id}"
    conn = connections.get(key)
    if conn is None:
        return

    conn.mav.command_long_send(
        conn.target_system,
        conn.target_component,
        mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,
        0,        # confirmation
        1,        # speed type: 1 = groundspeed (0 = airspeed)
        speed,    # speed, m/s
        -1, 0, 0, 0, 0,  # throttle (unused, -1), unused params
    )
    print(f"[{key}] speed change to {speed} m/s sent")


# --- WebSocket ------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("action") == "goto":
                send_goto(
                    vehicle_type=msg.get("vehicle_type", "uav"),
                    drone_id=int(msg["drone_id"]),
                    lat=float(msg["lat"]),
                    lon=float(msg["lon"]),
                    alt=float(msg.get("alt", 20.0)),
                    speed=float(msg["speed"]) if msg.get("speed") is not None else None,
                )
    except WebSocketDisconnect:
        clients.discard(websocket)


# --- Static frontend -------------------------------------------------------

app.mount("/static", StaticFiles(directory="static", html=True), name="static")
