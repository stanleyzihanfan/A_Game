# Unboxed-Engine

A reusable, sandbox-free **game engine** with a moddable client-server
architecture. It is the engine behind A-Game, but is designed to be forked and
used as the base for literally any game — it ships with no restrictions and no
built-in game content, so mods can build anything on top of it.

The engine is split into two separate processes:

- **Backend (`server/`)** — a Flask server that owns the game WebSocket, runs
  the fixed-timestep tick loop, holds authoritative game state, and loads mods.
- **Client (`client/`)** — a separate Flask asset server that serves the HTML
  page (`client/frontend.html`) plus static JS/CSS, and provides a WebSocket
  endpoint that relays browser console logs to the terminal.

Both are launched from the engine root via `launch_server.py` and
`launch_client.py`. **The engine ships with no mods.** Mods live in a mods
folder and are auto-discovered from their `manifest.json` (see
`server/mod_loader.py`).

## Quick start (run the engine with no mods)

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
backend server link (`http://localhost:5000`) on the connect screen. With no
mods loaded the engine boots fine, but there is no game content to render —
mods provide everything.

## Using the engine from a game (embedding)

A game embeds the engine as a repo subtree under an `engine/` folder and points
the engine at its own mods folder with the `UNBOXED_MODS_DIR` environment
variable (or creates a `mods/` folder next to the engine). For example:

```bash
# From the game root, with the engine vendored at engine/:
UNBOXED_MODS_DIR="$PWD/mods" python3 engine/launch_server.py
```

The engine's `server`/`client` packages resolve from the engine root, so they
work both standalone (`import server`) and when vendored (`import engine.server`).

## Layout

```
server/          Backend engine (Flask + WebSocket + tick loop + mod loader)
  core.py        Server lifecycle, the /server WebSocket, handshake, tick loop
  game_state.py  Thread-safe namespaced key-value store
  ws_registry.py Central op handler registry for mods
  mod_loader.py  Discovers and loads mods (dir controlled by UNBOXED_MODS_DIR)
client/          Client asset server + browser frontend
  launcher.py    Serves frontend.html, static files, and the /clientlog socket
  frontend.html  HTML page
  scripts/       Core JS (game_state.js, client_ws_registry.js, main.js, ...)
launch_server.py Backend entry point
launch_client.py Client entry point
docs/            Modding API reference (built with MkDocs)
```

## Mods

Each mod is a folder under the game's mods directory (set via
`UNBOXED_MODS_DIR`, or `mods/` relative to the engine) containing a
`manifest.json` that declares a `modID`, an optional `namespace` (defaults to
`modID`), a backend `main.py` (exposes a `register(registry)` function), and an
optional `client.js` (eval()ed on the client). See `server/mod_loader.py` for
details. The full modding API reference lives in `docs/`.

## Documentation server

The modding API reference (`docs/`) is a standalone MkDocs site built from
`mkdocs.yml`. It has its own virtualenv at `.venv-docs/` so its dependencies
don't clash with the game's runtime.

Start the local docs server:

```bash
./.venv-docs/bin/mkdocs serve
```

This builds the site and serves it at `http://127.0.0.1:8000/` with live reload,
so edits to `docs/` are rebuilt automatically as you save.

To build the site once as static files (output to `site/`), run:

```bash
./.venv-docs/bin/mkdocs build
```
