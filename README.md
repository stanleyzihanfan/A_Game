# A-Game

A voxel/block game built on **Unboxed-Engine** — a reusable, moddable
client-server game engine. This repo is the game itself: it vendors the engine
as an `engine/` subtree and adds the game's own mods in `mods/`.

The engine is split into two separate processes:

- **Backend (`engine/server/`)** — a Flask server that owns the game WebSocket,
  runs the fixed-timestep tick loop, holds authoritative game state, and loads
  mods.
- **Client (`engine/client/`)** — a separate Flask asset server that serves the
  HTML page (`engine/client/frontend.html`) plus static JS/CSS, and provides a
  WebSocket endpoint that relays browser console logs to the terminal.

Both are launched from the repository root via `launch_server.py` and
`launch_client.py`. The root launchers set the `UNBOXED_MODS_DIR` env var to
this game's `mods/` folder, then delegate to the engine launchers under
`engine/`. Mods live in `mods/` and are auto-discovered from their
`manifest.json` (see `engine/server/mod_loader.py`).

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
engine/           Vendored Unboxed-Engine (git subtree; reusable, sandbox-free)
  server/         Backend engine (Flask + WebSocket + tick loop + mod loader)
  client/         Client asset server + browser frontend
  docs/           Modding API reference (built with MkDocs)
  launch_server.py  Engine backend entry point
  launch_client.py  Engine client entry point
mods/             This game's mods, each a folder with manifest.json + code
launch_server.py  Game root launcher (sets UNBOXED_MODS_DIR=mods, delegates)
launch_client.py  Game root launcher (sets UNBOXED_MODS_DIR=mods, delegates)
```

The `engine/` folder is a subtree of the
[`Unboxed-Engine`](https://github.com/stanleyzihanfan/Unboxed-Engine) repo. To
update the engine, `git subtree pull` it from that repo; keeping the game's
mods in `mods/` (outside the engine subtree) means engine updates never touch
them.

## Mods

Each mod is a folder under `mods/` containing a `manifest.json` that declares a
`modID`, an optional `namespace` (defaults to `modID`), a backend `main.py`
(exposes a `register(registry)` function), and an optional `client.js` (eval()ed
on the client). See `engine/server/mod_loader.py` for details.

## Documentation

The modding API reference (`engine/docs/`) is a standalone MkDocs site built
from `engine/mkdocs.yml`. It has its own virtualenv at `.venv-docs/` so its
dependencies don't clash with the game's runtime.

Start the local docs server:

```bash
./.venv-docs/bin/mkdocs serve --config-file engine/mkdocs.yml --docs-dir engine/docs
```

To build the site once as static files (output to `site/`), run:

```bash
./.venv-docs/bin/mkdocs build --config-file engine/mkdocs.yml --docs-dir engine/docs
```
