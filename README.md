# A-Game

A voxel/block game with a moddable client-server architecture. The engine is
split into two separate processes:

- **Backend (`server/`)** — a Flask server that owns the game WebSocket, runs
  the fixed-timestep tick loop, holds authoritative game state, and loads mods.
- **Client (`client/`)** — a separate Flask asset server that serves the HTML
  page (`client/frontend.html`) plus static JS/CSS, and provides a WebSocket
  endpoint that relays browser console logs to the terminal.

Both are launched from the repository root via `launch_server.py` and
`launch_client.py`. Mods live in `mods/` and are auto-discovered from their
`manifest.json` (see `server/mod_loader.py`).

## Quick start

Install dependencies:

```bash
pip install flask flask-cors flask-sock msgpack
```

Start the backend server (it picks a free port, defaults to 5000):

```bash
python3 launch_server.py
```

Start the client asset server (serves the frontend page on port 8000):

```bash
python3 launch_client.py
```

Then open the client URL (`http://localhost:8000`) in a browser and enter the
backend server link (`http://localhost:5000`) on the connect screen.

### Public multiplayer (tunnel)

Both launchers accept a `--tunnel` flag that exposes the server publicly via
cloudflared so remote clients can connect:

```bash
python3 launch_server.py --tunnel
python3 launch_client.py --tunnel
```

## Layout

```
server/          Backend engine (Flask + WebSocket + tick loop + mod loader)
  core.py        Server lifecycle, the /server WebSocket, handshake, tick loop
  game_state.py  Thread-safe namespaced key-value store
  ws_registry.py Central op handler registry for mods
  mod_loader.py  Discovers and loads mods from the /mods directory
client/          Client asset server + browser frontend
  launcher.py    Serves frontend.html, static files, and the /clientlog socket
  frontend.html  HTML page
  scripts/       Core JS (game_state.js, client_ws_registry.js, main.js, ...)
mods/            Mods, each a folder with a manifest.json + backend/client code
launch_server.py Backend entry point
launch_client.py Client entry point
```

## Mods

Each mod is a folder under `mods/` containing a `manifest.json` that declares a
`modID`, an optional `namespace` (defaults to `modID`), a backend `main.py`
(exposes a `register(registry)` function), and an optional `client.js` (eval()ed
on the client). See `server/mod_loader.py` for details.
