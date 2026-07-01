import socket, threading, msgpack, traceback, os, mimetypes
from flask import Flask, Response
from flask_cors import CORS
from flask_sock import Sock
from werkzeug.serving import make_server

from server.ws_registry import Registry
from server.game_state import GameState
from server.mod_loader import load_mods

# Resolve project root (one level up from server/)
# so file paths work regardless of where the script is launched from (Colab, PC, etc.)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -- Flask & WebSocket setup ---------------------------------------------------
app = Flask(__name__)
CORS(app)
wSocket = Sock(app)

# -- Global Vars ------------------------------------------------------
# Mod web socket handler registry
registry = Registry()

#Game state storage
game_state=GameState()

#Mod manifests, used for sending JS frontend mod handler registration to frontend
loaded_mods=[]

# Track active websocket connections
active_connections = set()
active_connections_lock = threading.Lock()

# Client ID counter
clientID = 0
flask_server = None

# -- Binary packaging functions ------------------------------------------------
def encode(data):
    return msgpack.packb(data, use_bin_type=True)

def decode(data):
    return msgpack.unpackb(data, raw=False)

# -- Flask routes --------------------------------------------------------------
#Serve html frontend page
@app.route("/")
def index():
    # Read frontend.html from disk, relative to project root
    with open(os.path.join(BASE_DIR, "client/frontend.html"), "r") as f:
        return Response(f.read(), mimetype="text/html")
#Serve JS files(for frontend src requests)
@app.route("/<path:filename>")
def static_file(filename):
    # Serve static files from project root
    filepath = os.path.join(BASE_DIR, filename)
    # Auto-detect mimetype from file extension
    mimetype, _ = mimetypes.guess_type(filepath)
    if not mimetype:
        mimetype = "text/plain"
    if not os.path.isfile(filepath):
        return "Not found", 404
    with open(filepath, "r") as f:
        return Response(f.read(), mimetype=mimetype)

# -- WebSocket -----------------------------------------------------------------
# Patch client mod js scripts
def _send_mod_scripts(ws):
    """Send each loaded mod's client.js source over the websocket, then signal ready."""
    for manifest in loaded_mods:
        client_js = manifest.get("client_js")
        if not client_js:
            continue
        js_path = os.path.join(manifest["_mod_path"], client_js)
        if not os.path.isfile(js_path):
            continue
        with open(js_path, "r") as f:
            src = f.read()
        ws.send(encode({"op": "load_mod_js", "params": [manifest["modID"], src]}))
    # Signal that all mod scripts have been sent
    ws.send(encode({"op": "mods_ready", "params": []}))

@wSocket.route("/server")
def server(ws):
    global clientID
    # Store & increment clientID
    myID = clientID
    clientID += 1

    #Add websocket to connected clients list
    with active_connections_lock:
        active_connections.add(ws)
    try:
        # Send client its assigned ID so it can initialize
        ws.send(encode({"op": "init", "params": [myID]}))
        #Stream client all mod JS files
        _send_mod_scripts(ws)
        while True:
            data = ws.receive()
            if data is None:
                break
            data = decode(data)
            # Route message to handler
            registry.dispatch(data["op"], data["params"], ws, encode)
    finally:
        #Remove from connected clients on client disconnect
        with active_connections_lock:
            active_connections.discard(ws)

def find_port(start=5000):
    """Find open port for Flask server\n
    If current port isn't open, repeated increments port number by 1 until open port is found

    :param start: First port to search
    :return: Number of first open port found
    """
    port = start
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                print(f"Port {port} already in use, trying {port+1} next")
                print()
                port += 1

# -- Server startup ------------------------------------------------------------
def start():
    """Server startup
    """
    global flask_server, loaded_mods
    #load mods
    loaded_mods=load_mods(registry)
    #Launch flask server
    port = find_port()
    print(f"Port {port} open, launching server")
    flask_server = make_server("0.0.0.0", port, app, threaded=True)
    t = threading.Thread(target=flask_server.serve_forever, daemon=True)
    t.start()
    print(f"Flask running on port {port}")
    return port

# -- Graceful shutdown ---------------------------------------------------------
def shutdown():
    """Gracefully shuts down all systems
    """
    with active_connections_lock:
        for ws in active_connections:
            try:
                ws.close()
            except Exception:
                pass
    if flask_server:
        flask_server.shutdown()