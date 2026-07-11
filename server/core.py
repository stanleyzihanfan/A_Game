import socket, threading, msgpack, traceback, os, mimetypes, time
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
#Main game tick thread
tick_thread=None

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
    return Response("<html><body>Server is running.</body></html>", mimetype="text/html")

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
            # Route message to game state
            with game_state._lock:
                if data["op"]=="sync_with_server":
                    clientData=game_state.set(["client_receive_buffer"],data["op"])
                else:
                    clientData=game_state.get(["client_receive_buffer",data["op"]],False)
                    if not game_state.exists(["client_receive_buffer",data["op"]]):
                        game_state.set(["client_receive_buffer",data["op"]],[])
                        clientData=game_state.get(["client_receive_buffer",data["op"]],False)
                    clientData.append(data["params"])
    finally:
        #Remove from connected clients on client disconnect
        with active_connections_lock:
            active_connections.discard(ws)

def find_port(start=5000):
    """Find open port for Flask server\n
    If current port isn't open, repeatedly increments port number by 1 until open port is found

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
                #print()
                port += 1

# -- Server startup ------------------------------------------------------------
def start_tick(interval):
    print("Started game...")
    while True:
        try:
            registry.dispatch("main:tick_hook",game_state)
            wSocket.send(encode({}))
        except Exception as e:
            if "Handled" not in e.__notes__:
                traceback.print_exc()
            input("Please press enter to continue execution:")
        time.sleep(interval)
tick_thread=threading.Thread(target=start_tick,args=(0.05,),daemon=True)
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
    tick_thread.start()
    print("Started ticking thread")
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