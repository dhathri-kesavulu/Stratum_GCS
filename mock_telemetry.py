"""
Fallback telemetry source so the rest of the stack (backend, WebSocket,
frontend) can be built and demoed even if ArduPilot SITL isn't running.
server.py falls back to this automatically per-vehicle if a heartbeat isn't
received within HEARTBEAT_TIMEOUT_S.

Works for both UAV and UGV — vehicle_type is just carried through in the
telemetry payload so the frontend can label/render it correctly. Each mock
vehicle moves in a small circle around a center point, so the map shows
visible, believable motion — and responds to click-to-fly/drive waypoints
the same way a real vehicle would (drifting toward the target).
"""

import math
import time

# SITL's default spawn location (CMAC, Australia)
DEFAULT_CENTER = (-35.363261, 149.165230)


class MockDrone:
    def __init__(self, drone_id: int, vehicle_type: str = "uav",
                 center=DEFAULT_CENTER, radius_deg=0.0015, period_s=50):
        self.drone_id = drone_id
        self.vehicle_type = vehicle_type
        self.center_lat, self.center_lon = center
        self.radius = radius_deg
        self.period = period_s
        # stagger start angle per vehicle so multiple mocks don't overlap
        self.phase = (drone_id * 2 * math.pi) / 6
        self.start_time = time.time()
        self.target = None  # set externally when a waypoint command arrives

    def set_target(self, lat: float, lon: float, alt: float, speed: float):
        self.target = {"lat": lat, "lon": lon, "alt": alt, "speed": speed}

    def next_sample(self) -> dict:
        t = time.time() - self.start_time
        angle = self.phase + (2 * math.pi * t / self.period)

        base_lat = self.center_lat + self.radius * math.sin(angle)
        base_lon = self.center_lon + self.radius * math.cos(angle)
        alt = 20 + 5 * math.sin(angle / 2) if self.vehicle_type == "uav" else 0.3
        speed = 3.5 + 0.5 * math.sin(angle * 2)

        lat, lon = base_lat, base_lon
        if self.target:
            pull = min(0.95, 0.3 + (self.target["speed"] / 15) * 0.6)
            lat = base_lat * (1 - pull) + self.target["lat"] * pull
            lon = base_lon * (1 - pull) + self.target["lon"] * pull
            alt = alt * (1 - pull) + self.target["alt"] * pull
            speed = self.target["speed"]

        heading = (math.degrees(angle) + 90) % 360
        battery = max(20, 100 - (t / 10) % 80)

        return {
            "drone_id": self.drone_id,
            "vehicle_type": self.vehicle_type,
            "lat": round(lat, 7),
            "lon": round(lon, 7),
            "alt": round(alt, 1),
            "heading": round(heading, 1),
            "speed": round(speed, 1),
            "battery": round(battery, 1),
            "mock": True,
        }
