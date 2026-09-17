// Self-contained map panel. Renders drone markers and sends a "goto"
// command over the shared WebSocket when the user clicks the map.

export function initMapPanel({ container, ws, getSelectedDrone }) {
  const map = L.map(container).setView([-35.363261, 149.165230], 17); // SITL default spawn

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map);

  const markers = new Map(); // drone_id -> L.Marker

  function colorFor(droneId) {
    const palette = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b'];
    return palette[(droneId - 1) % palette.length];
  }

  function update(drones) {
    for (const d of drones) {
      const latlng = [d.lat, d.lon];

      if (!markers.has(d.drone_id)) {
        const marker = L.circleMarker(latlng, {
          radius: 8,
          color: colorFor(d.drone_id),
          fillColor: colorFor(d.drone_id),
          fillOpacity: 0.9,
        }).addTo(map);
        marker.bindPopup(`Drone ${d.drone_id}`);
        markers.set(d.drone_id, marker);
      } else {
        markers.get(d.drone_id).setLatLng(latlng);
      }
    }
  }

  map.on('click', (e) => {
    const droneId = getSelectedDrone();
    ws.send(JSON.stringify({
      action: 'goto',
      drone_id: droneId,
      lat: e.latlng.lat,
      lon: e.latlng.lng,
    }));

    L.circleMarker(e.latlng, { radius: 4, color: '#ffffff' })
      .addTo(map)
      .bindTooltip(`Waypoint → Drone ${droneId}`, { permanent: false })
      .openTooltip();
  });

  return { update };
}
