// Self-contained telemetry sidebar. Shows altitude/speed/heading/battery
// per drone and lets the user click a card to select which drone receives
// the next map-click waypoint command.

export function initTelemetryPanel({ container, onSelectDrone }) {
  const cards = new Map(); // drone_id -> HTMLElement
  let selectedId = null;

  function selectDrone(id) {
    selectedId = id;
    onSelectDrone(id);
    for (const [droneId, el] of cards) {
      el.classList.toggle('selected', droneId === id);
    }
  }

  function update(drones) {
    for (const d of drones) {
      let card = cards.get(d.drone_id);

      if (!card) {
        card = document.createElement('div');
        card.className = 'drone-card';
        card.onclick = () => selectDrone(d.drone_id);
        container.appendChild(card);
        cards.set(d.drone_id, card);

        if (selectedId === null) selectDrone(d.drone_id);
      }

      card.innerHTML = `
        <div class="label">Drone ${d.drone_id}${d.mock ? ' (mock)' : ''}</div>
        <div class="stat-row"><span>Alt</span><span>${d.alt.toFixed(1)} m</span></div>
        <div class="stat-row"><span>Speed</span><span>${d.speed.toFixed(1)} m/s</span></div>
        <div class="stat-row"><span>Heading</span><span>${d.heading.toFixed(0)}&deg;</span></div>
        <div class="stat-row"><span>Battery</span><span>${d.battery != null ? d.battery.toFixed(0) + '%' : 'n/a'}</span></div>
      `;
    }
  }

  return { update };
}
