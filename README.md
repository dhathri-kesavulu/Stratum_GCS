<div align="center">

# 🛰️ Multi-Vehicle Ground Control System

**A browser-based command-and-control dashboard for simulated UAVs and UGVs, speaking real MAVLink.**

[![Python](https://img.shields.io/badge/Python-3.10+-004830?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-004830?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![MAVLink](https://img.shields.io/badge/MAVLink-Protocol-708238?style=for-the-badge)](https://mavlink.io)
[![ArduPilot](https://img.shields.io/badge/ArduPilot-SITL-708238?style=for-the-badge)](https://ardupilot.org)
[![Three.js](https://img.shields.io/badge/Three.js-3D_View-3F301D?style=for-the-badge&logo=three.js&logoColor=white)](https://threejs.org)
[![Leaflet](https://img.shields.io/badge/Leaflet-Mapping-3F301D?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com)

</div>

---

## 📖 About This Project

This is a **hobby project** I built to teach myself how ground control systems actually work under the hood — the kind of software operators use to monitor and command drones and ground robots.

I wanted to understand the full pipeline end to end, not just the dashboard on top:

> *How does a click on a map turn into a real command a flight controller understands? How does a vehicle's position get from its GPS, through a radio protocol, into a browser, in real time?*

So I built the whole path myself: **simulated vehicles → MAVLink over UDP → Python backend → WebSocket → live browser dashboard**, and back again for commands.

Nothing here wraps an existing GCS. The MAVLink handling, telemetry streaming, command encoding, and the entire interface are written from scratch — which was the entire point.

---

## ✨ What It Does

<table>
<tr>
<td width="50%" valign="top">

### 🎯 Live Telemetry
Streams position, altitude, speed, heading and battery from every connected vehicle, several times a second, over a persistent WebSocket.

</td>
<td width="50%" valign="top">

### 🖱️ Click-to-Command
Click anywhere on the map to send a real guided-mode waypoint command to the selected vehicle. It actually flies or drives there.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🚁 UAV **and** 🛻 UGV Support
Toggle between aerial drones and ground rovers. The interface adapts — rovers lose altitude control, markers change shape, labels update.

</td>
<td width="50%" valign="top">

### 🗺️ Multi-Waypoint Missions
Plan up to **15 sequential waypoints** per vehicle, then execute the whole route. Each vehicle holds its own independent mission.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🎛️ Per-Vehicle Parameters
Set target altitude and speed independently per vehicle. The dashboard remembers each one's last commanded values.

</td>
<td width="50%" valign="top">

### 🌐 2D + 3D Views
Switch between a top-down tactical map and a fully orbitable 3D scene where **altitude is rendered as literal height** above the ground.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🚀 Fleet-Wide Execution
**RUN ALL** launches every planned mission across the fleet simultaneously — genuinely concurrent, not one after another.

</td>
<td width="50%" valign="top">

### 📡 Graceful Degradation
If no simulator is reachable, the dashboard falls back to a built-in simulation automatically. It never shows a dead screen.

</td>
</tr>
</table>

---

## 🏗️ Architecture

```
┌─────────────────────┐         ┌─────────────────────┐
│  ArduCopter SITL    │         │    Rover SITL       │
│  (UAV · port 14550) │         │  (UGV · port 14570) │
└──────────┬──────────┘         └──────────┬──────────┘
           │                               │
           └───────  MAVLink / UDP  ───────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │        server.py          │
              │  ├─ pymavlink connections │
              │  ├─ telemetry poll loop   │
              │  └─ command encoder       │
              └─────────────┬─────────────┘
                            │
                  WebSocket (bidirectional)
                            │
                            ▼
              ┌───────────────────────────┐
              │    Browser Dashboard      │
              │  ├─ Leaflet 2D map        │
              │  ├─ Three.js 3D scene     │
              │  ├─ Fleet / Telemetry     │
              │  └─ Mission planner       │
              └───────────────────────────┘
```

**Two directions of traffic over one connection:**

| Direction | Payload | Rate |
|:---|:---|:---|
| ⬇️ Server → Browser | Telemetry for every vehicle | ~5 Hz |
| ⬆️ Browser → Server | Waypoint + speed commands | On interaction |

---

## 🧰 Tech Stack

| Layer | Technology | Why this choice |
|:---|:---|:---|
| **Simulation** | ArduPilot SITL | Runs the *real* flight controller firmware — same guidance logic as physical hardware |
| **Protocol** | MAVLink (`pymavlink`) | The actual industry-standard drone protocol, not a custom toy format |
| **Backend** | Python + FastAPI | Native async support, clean WebSocket handling, minimal boilerplate |
| **Transport** | WebSocket | Persistent and bidirectional — the right fit for live telemetry *and* commands |
| **2D Map** | Leaflet.js | Lightweight, no API key, precise lat/lon handling |
| **3D Scene** | Three.js | Renders altitude as real spatial height with a free-orbit camera |
| **Frontend** | Vanilla HTML/CSS/JS | No build step, no framework — everything inspectable in one file |

---

## 🔬 MAVLink Implementation Details

The parts that took the most learning:

**Telemetry — `GLOBAL_POSITION_INT`**
```python
lat     = msg.lat / 1e7          # degrees × 10⁷ → degrees
lon     = msg.lon / 1e7
alt     = msg.alt / 1000         # millimetres → metres
heading = msg.hdg / 100          # centidegrees → degrees (65535 = unknown)
speed   = (msg.vx**2 + msg.vy**2) ** 0.5 / 100   # cm/s → m/s
```

**Commanding position — `SET_POSITION_TARGET_GLOBAL_INT`**
```python
conn.mav.set_position_target_global_int_send(
    0,
    conn.target_system, conn.target_component,
    mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
    0b0000111111111000,            # type_mask: position only
    int(lat * 1e7), int(lon * 1e7), alt,
    0, 0, 0,   0, 0, 0,   0, 0,
)
```

**Commanding speed — `MAV_CMD_DO_CHANGE_SPEED`**

A detail I didn't expect: MAVLink treats *speed* and *position* as completely separate commands. Setting a waypoint doesn't set a speed — that needs its own `command_long_send`, with speed type `1` for groundspeed.

> 💡 The same guided-mode position command works for both copters and rovers — the vehicle's own firmware decides what "go here" means for its frame type. Discovering that is what made multi-vehicle support surprisingly clean.

---

## 📁 Project Structure

```
multi_vehicle_gcs/
│
├── server.py              # FastAPI app · MAVLink connections · WebSocket · command encoding
├── mock_telemetry.py      # Fallback data source when no simulator is reachable
├── first_telemetry.py     # Standalone script — the very first thing I got working
├── requirements.txt       # Python dependencies
│
└── static/
    └── index.html         # The entire dashboard — UI, 2D map, 3D scene, mission planner
```

---

## 🚀 Running It

### 1️⃣ Install dependencies
```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2️⃣ Start the simulated vehicles

**Aerial vehicle (UAV):**
```bash
cd ~/ardupilot/ArduCopter
../Tools/autotest/sim_vehicle.py --console --map --out udp:localhost:14550
```

**Ground vehicle (UGV):**
```bash
cd ~/ardupilot/Rover
../Tools/autotest/sim_vehicle.py --console --map --out udp:localhost:14570
```

> ℹ️ Additional vehicles run on further ports — add them to the `VEHICLES` dictionary in `server.py`.

### 3️⃣ Start the backend
```bash
uvicorn server:app --reload
```

Look for `real heartbeat on port ...` in the logs — that confirms a live MAVLink link.

### 4️⃣ Open the dashboard
```
http://localhost:8000/static/index.html
```

> ⚠️ Open it **through the server**, not by double-clicking the HTML file — the WebSocket connection depends on it.

---

## 🎮 Using It

| Action | How |
|:---|:---|
| **Switch vehicle type** | `UAV · DRONES` / `UGV · ROVERS` toggle, top bar |
| **Add a vehicle** | `+` tile in the Fleet panel (up to 6 per type) |
| **Select a vehicle** | Click its tile in the Fleet panel |
| **Send one waypoint** | Click anywhere on the map |
| **Plan a route** | Set waypoint count → `PLAN` → click the map that many times |
| **Execute** | `RUN` for the selected vehicle, `RUN ALL` for the whole fleet |
| **Orbit the 3D view** | `3D VIEW` tab → drag to rotate, scroll to zoom |

---

## 🧠 What I Learned

<table>
<tr><td width="30px">🔌</td><td><b>Protocols are unforgiving about units.</b> Latitude arrives as an integer scaled by 10⁷, altitude in millimetres, heading in centidegrees. Every one is a chance to be silently, confidently wrong.</td></tr>
<tr><td>⚡</td><td><b>Blocking I/O will freeze an async server.</b> <code>pymavlink</code>'s reads are synchronous, so they run in an executor — otherwise one slow read stalls the WebSocket for every connected client.</td></tr>
<tr><td>🧩</td><td><b>Shared state needs namespacing from day one.</b> Keying vehicles by ID alone meant "Drone 1" and "Rover 1" silently collided. Composite <code>type:id</code> keys fixed a whole category of bug at once.</td></tr>
<tr><td>🎞️</td><td><b>An animation loop must reschedule itself first.</b> Calling <code>requestAnimationFrame</code> after the render work means one thrown error kills the loop permanently — the screen just freezes with nothing visibly wrong.</td></tr>
<tr><td>🖱️</td><td><b>Rebuilding DOM nodes eats user input.</b> Re-rendering cards 5× a second detached elements mid-click, so buttons felt broken. Updating text in place instead of regenerating HTML fixed it entirely.</td></tr>
<tr><td>🛡️</td><td><b>Design for the failure case.</b> Tile servers go down, simulators aren't always running. Every external dependency here has a fallback, so the interface degrades instead of breaking.</td></tr>
</table>

---

## 🗺️ Scope & Honesty

**What's real:**
- ✅ Genuine MAVLink protocol over UDP — the same messages a physical vehicle uses
- ✅ ArduPilot SITL runs actual flight controller firmware, including real guidance behaviour
- ✅ Commands sent here would work unchanged against real hardware over a telemetry radio

**What's not:**
- ⚠️ No physical vehicles — everything is simulated
- ⚠️ Mission legs advance on a fixed dwell time rather than confirmed arrival
- ⚠️ No authentication or multi-operator session handling
- ⚠️ The 3D view is a stylised instrument display, not photorealistic terrain

---

## 🔭 Possible Next Steps

- [ ] Arrival detection — advance mission legs on actual proximity instead of a timer
- [ ] Flight path trails rendered in the 3D scene
- [ ] Geofencing and return-to-launch
- [ ] Telemetry logging and post-flight playback
- [ ] A camera/sensor feed panel as a pluggable module

---

<div align="center">

*Built to learn how the real thing works.*

</div>
