"""
Core server module.

Sets up the Flask HTTP/WebSocket server, manages client connections,
runs the game tick loop, and coordinates mods via the WebSocket registry.
"""
import socket, threading, msgpack, traceback, os, mimetypes, time
from datetime import datetime
from flask import Flask, Response
from flask_cors import CORS
from flask_sock import Sock
from werkzeug.serving import make_server
from server.ws_registry import Registry
from server.game_state import GameState
from server.mod_loader import load_mods

# Resolve project root so file paths work regardless of launch location.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -- Flask & WebSocket setup ---------------------------------------------------
app = Flask(__name__)
CORS(app)
wSocket = Sock(app)

# -- Global state ------------------------------------------------------------
tick_thread = None                    # main game tick thread (started in start())
registry = Registry()                 # mod op handler registry
game_state = GameState()              # central world/player state store
loaded_mods = []                      # loaded manifests -> which client.js to stream
active_connections = {}               # {playerName: {"socket": ws, "status": ...}}
active_connections_lock = threading.Lock()
flask_server = None                   # Flask/Werkzeug server (set in start())

# -- Binary packaging functions ------------------------------------------------
# The game protocol speaks msgpack over WebSocket. encode/decode wrap the
# library calls so every module uses these helpers rather than msgpack directly.
def encode(data):
    return msgpack.packb(data, use_bin_type=True)

def decode(data):
    return msgpack.unpackb(data, raw=False)

# -- Flask routes --------------------------------------------------------------
@app.route("/")
def index():
    return Response("<html><body>Server is running.</body></html>", mimetype="text/html")

# -- WebSocket -----------------------------------------------------------------
# The single game WebSocket endpoint. A new connection goes through a fixed
# handshake sequence (init -> player data -> connect-guard decision -> mod script
# stream -> client_init_done) before entering the steady-state message loop.
def _send_mod_scripts(ws):
    """Send each loaded mod's client.js source over the websocket, then signal ready.

    The mod's manifest namespace travels with the script so the client can
    apply the same auto-namespacing while eval()ing it.
    """
    for manifest in loaded_mods:
        client_js = manifest.get("client_js")
        if not client_js:
            # No client_js means server-side only; nothing to stream, no warning.
            continue
        js_path = os.path.join(manifest["_mod_path"], client_js)
        if not os.path.isfile(js_path):
            print(f"\x1b[33m  client.js '{client_js}' not found for mod '{manifest['modID']}'\033[0m")
            continue
        with open(js_path, "r") as f:
            src = f.read()
        ws.send(encode({"op": "load_mod_js", "params": [manifest["modID"], src, manifest.get("_namespace", manifest["modID"])]}))
    # Signal that all mod scripts have been sent
    ws.send(encode({"op": "mods_ready", "params": []}))

@wSocket.route("/server")
def server(ws):
    # playerName is referenced by the cleanup in `finally`; initialize up front
    # so a connection that aborts during the handshake doesn't raise a NameError.
    playerName = None
    try:
        # -- Handshake step 1: request client init --------------------------
        ws.send(encode({"op": "init"}))
        # Wait for client to respond with player data
        data = ws.receive()
        if data is None:
            return
        data = decode(data)
        if data["op"] != "init":
            print("\033[33mA client attempted to connect but failed to send player data. Connection terminated.\033[0m")
            ws.close(1002, "Server did not receive initial player data")
            return
        if "playerName" not in data or "psw" not in data:
            print("\033[33mA client attempted to connect but sent invalid player data. Connection terminated.\033[0m")
            ws.close(1003, "Server received invalid player data")
            return

        # -- Handshake step 2: register connection, run connect-guard --------
        playerName = data["playerName"]
        with active_connections_lock:
            active_connections[playerName] = {"socket": ws, "status": "pre-connect"}
        print(f"Client {playerName} connected.")
        # Connection-acceptance logic lives in the connect_guard mod. Core owns
        # the socket lifecycle: it sets up a request context, dispatches
        # "core:on_player_connect_request", then enforces the mod's decision
        # (performing the actual ws.close() on rejection). If no guard mod is
        # loaded the decision stays None and the connection is accepted.
        with game_state._lock:
            game_state.set(["core:connect_request"], {
                "playerName": playerName,
                "psw": data["psw"],
                "approved": None,
                "reason": None,
                "code": None,
            })
            registry.dispatch("core:on_player_connect_request", game_state)
            connect_decision = game_state.get(["core:connect_request"])
            game_state.set(["core:connect_request"], None)
        if connect_decision["approved"] is False:
            print(f"\033[33mPlayer {playerName} connection rejected: {connect_decision.get('reason', 'Unknown reason')}\033[0m")
            ws.close(connect_decision.get("code") or 1002, connect_decision.get("reason") or "Connection rejected")
            return
        # -- Handshake step 3: stream mod client scripts ----------------------
        with active_connections_lock:
            active_connections[playerName]["status"] = "streaming"
        _send_mod_scripts(ws)
        with active_connections_lock:
            active_connections[playerName]["status"] = "modLoad_client"

        # -- Handshake step 4: wait for client to finish loading --------------
        data = decode(ws.receive())
        if data is None:
            raise ConnectionResetError(f"Connection {playerName} closed before initialization finished")
        if data.get("op") != "client_init_done":
            print(f"Client {playerName} failed to finalize initialization")
            raise ValueError(f"Client {playerName} failed to finalize initialization")

        # -- Handshake step 5: run connect handlers, deliver one-time init -----
        with game_state._lock:
            game_state.set(["core:players", "newPlayerName"], playerName)
            # Set up the per-client sync payload so mods can call
            # add_to_client_sync() in their core:on_player_connect handler and
            # have the data delivered to this client as a one-time init message.
            game_state.set(["core:per_client_sync"], {"player": playerName, "data": {}})
            registry.dispatch("core:on_player_connect", game_state)
            # Flush any data the connect handlers added into the payload, then
            # clear it (never reused across clients).
            init_payload = game_state.get(["core:per_client_sync", "data"])
            if init_payload:
                ws.send(encode({"op": "core:sync_with_client", "data": init_payload}))
            game_state.set(["core:per_client_sync"], {"player": playerName, "data": {}})
            game_state.set(["core:players", "newPlayerName"], "")
        with active_connections_lock:
            active_connections[playerName]["status"] = "ready"

        # -- Steady-state: forward client messages into the receive buffer -----
        # The tick loop consumes this buffer once per tick, letting mods read
        # each client's input (and for per-player broadcast) via game_state.
        while True:
            data = ws.receive()
            if data is None:
                break
            data = decode(data)
            with game_state._lock:
                game_state.get(["core:client_receive_buffer"], False, False).append({"playerName": playerName, "data": data["params"]})
    finally:
        # -- Disconnect cleanup --------------------------------------------------
        # Notify mods first (they may need their own cleanup), then remove the
        # socket from active_connections and mark the player offline.
        with game_state._lock:
            game_state.set(["core:players", "disconnectPlayerName"], playerName)
            registry.dispatch("core:on_player_disconnect", game_state)
            game_state.set(["core:players", "disconnectPlayerName"], "")
        # If playerName is None the socket closed before it was added to
        # active_connections, so there is nothing to remove or mark offline.
        if playerName is not None:
            with active_connections_lock:
                active_connections.pop(playerName, None)
            with game_state._lock:
                game_state.set(["core:players", playerName, "online"], False, True)
            print(f"Client {playerName} disconnected.")

def find_port(start=5000):
    """Find the first open port at or after `start`."""
    port = start
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                print(f"Port {port} already in use, trying {port+1} next")
                port += 1

# -- Game tick loop ------------------------------------------------------------
# Fixed-timestep loop: (1) dispatch tick handlers, (2) broadcast global data,
# (3) compute per-client display data, then (4) clear the receive buffer.
def start_tick(interval):
    print("Started game...")
    lastTime = datetime.now()
    deltaTick = 0
    # Initialize core communication game-state fields
    game_state.set(["core:global_broadcast"], [])
    game_state.set(["core:client_receive_buffer"], [])
    game_state.set(["core:client_receive_buffer"], [], True)
    while True:
        delta = datetime.now() - lastTime
        # Cap delta to prevent a spiral of death on heavy frames
        deltaSec = min(delta.total_seconds(), 0.05)
        deltaTick += deltaSec
        lastTime = datetime.now()
        while deltaTick >= interval:
            try:
                game_state.set(["core:tickRate"], interval)

                # -- Step 1: dispatch tick handlers (mod world/state logic) ----
                with game_state._lock:
                    registry.dispatch("core:tick", game_state)

                # -- Step 2: send global broadcast data to every client -------
                with game_state._lock:
                    toSync = game_state.get(["core:global_broadcast"])
                    for i in toSync:
                        with active_connections_lock:
                            for connection in active_connections.values():
                                if connection["status"] == "ready":
                                    connection["socket"].send(encode({"op": "core:sync_with_client", "data": i}))
                    game_state.set(["core:global_broadcast"], [])

                # -- Step 3: send client-specific data to each client ---------
                with active_connections_lock:
                    with game_state._lock:
                        for player, connection in active_connections.items():
                            if connection["status"] == "ready":
                                game_state.set(["core:per_client_sync"], {"player": player, "data": {}})
                                registry.dispatch("core:calculate_client_display", game_state)
                                connection["socket"].send(encode({"op": "core:sync_with_client", "data": game_state.get(["core:per_client_sync", "data"])}))

                # -- Step 4: clear the receive buffer for the next tick --------
                game_state.set(["core:client_receive_buffer"], [])
            except Exception as e:
                if "Handled" not in e.__notes__:
                    traceback.print_exc()
                input("Please press enter to continue execution:")
            deltaTick -= interval

# Tick thread is created at module scope so it exists before start() runs, then
# started once (and only once) inside start().
tick_thread = threading.Thread(target=start_tick, args=(0.05,), daemon=True)

def start():
    """Server startup: load mods, find a free port, launch Flask, start the tick thread."""
    global flask_server, loaded_mods
    loaded_mods = load_mods(registry, game_state)
    port = find_port()
    print(f"Port {port} open, launching server")
    flask_server = make_server("0.0.0.0", port, app, threaded=True)
    t = threading.Thread(target=flask_server.serve_forever, daemon=True)
    t.start()
    print(f"Flask running on port {port}")
    tick_thread.start()
    print("Started ticking thread")
    return port

# -- Graceful shutdown ---------------------------------------------------------
def shutdown():
    """Gracefully shut down all systems: close client sockets, then stop Flask."""
    with active_connections_lock:
        for k, ws in active_connections.items():
            try:
                ws["socket"].close()
            except Exception:
                pass
    if flask_server:
        flask_server.shutdown()