// Self-contained mission panel. Keeps a running log of waypoint commands
// sent from the map panel. Not wired to server state yet — a natural next
// step is to have the backend echo confirmed waypoints back over the
// WebSocket so this reflects real mission status rather than just intent.

export function initMissionPanel({ container }) {
  const log = document.createElement('ul');
  log.style.listStyle = 'none';
  log.style.padding = '0';
  container.appendChild(log);

  function addEntry(text) {
    const li = document.createElement('li');
    li.textContent = text;
    li.style.marginBottom = '4px';
    log.prepend(li);
  }

  addEntry('Click the map to send a waypoint to the selected drone.');

  return { addEntry };
}
