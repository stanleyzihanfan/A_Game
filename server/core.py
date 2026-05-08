import socket, threading, msgpack, traceback, os
from flask import Flask, Response
from flask_cors import CORS
from flask_sock import Sock
from werkzeug.serving import make_server

from server.ws_registry import Registry

# Resolve project root (one level up from server/)
# so file paths work regardless of where the script is launched from (Colab, PC, etc.)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -- Flask & WebSocket setup ---------------------------------------------------
app = Flask(__name__)
CORS(app)
wSocket = Sock(app)

# -- Central mod registry ------------------------------------------------------
# Mods register their WebSocket op handlers here
registry = Registry()

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
@app.route("/")
def index():
    # Read frontend.html from disk, relative to project root
    with open(os.path.join(BASE_DIR, "frontend.html"), "r") as f:
        return Response(f.read(), mimetype="text/html")

# -- WebSocket -----------------------------------------------------------------
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
        while True:
            data = ws.receive()
            if data is None:
                break
            data = decode(data)
            # Route message to registered handler; warn if op is unknown
            if not registry.dispatch(data["op"], data["params"], ws, encode):
                print(f"\x1b[31mFrontend attempted unknown handler: {data['op']}\033[0m")
    finally:
        #Remove from connected clients on client disconnect
        with active_connections_lock:
            active_connections.discard(ws)

# -- Find open port for Flask server -------------------------------------------
def find_port(start=5000):
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
    global flask_server
    port = find_port()
    print(f"Port {port} open, launching server")
    flask_server = make_server("0.0.0.0", port, app, threaded=True)
    t = threading.Thread(target=flask_server.serve_forever, daemon=True)
    t.start()
    print(f"Flask running on port {port}")
    return port

# -- Graceful shutdown ---------------------------------------------------------
def shutdown():
    with active_connections_lock:
        for ws in active_connections:
            try:
                ws.close()
            except Exception:
                pass
    if flask_server:
        flask_server.shutdown()