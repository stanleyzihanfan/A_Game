import socket, threading, msgpack, traceback, os, mimetypes, time
from datetime import datetime
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
active_connections = {}
active_connections_lock = threading.Lock()

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
    try:
        # Send request to client to initialize
        ws.send(encode({"op": "init"}))
        #Wait for client to respond with player data
        data=ws.receive()
        if data is None:
            return
        data=decode(data)
        if data["op"]!="init":
            print("\033[33mA client attempted to connect but failed to send player data. Connection terminated.\033[0m")
            ws.close(1002,"Server did not receive initial player data")
            return
        if "playerName" not in data or "psw" not in data:
            print("\033[33mA client attempted to connect but sent invalid player data. Connection terminated.\033[0m")
            ws.close(1003,"Server received invalid player data")
            return
        #Store player name
        playerName=data["playerName"]
        #Add socket to connected clients
        with active_connections_lock:
            active_connections[data["playerName"]]=ws
        print(f"Client {playerName} connected.")
        #TODO: Move connection logic to mod
        with game_state._lock:
            #Generate new player entry if it doesn't exist
            if not game_state.exists(["players",playerName]):
                game_state.set(["players",playerName,"online"],True,True)
                game_state.set(["players",playerName,"password"],data["psw"],True)
            #Check if player is already online
            elif game_state.get(["players",playerName,"online"]):
                print(f"\033[33mA client attempted to connect but player {playerName} is already online. Connection terminated.\033[0m")
                ws.close(1002,"Player already online")
                return
            else:
                #Check password
                if game_state.get(["players",playerName,"password"])!=data["psw"]:
                    print(f"\033[33mPlayer {playerName} connected with incorrect password.\033[0m")
                    ws.close(1000,"Incorrect Password")
                    return
                game_state.set(["players",playerName,"online"],True)
        registry.dispatch("core:on_player_connect",game_state)
        #Initialize core:client_receive_buffer in gamestate
        game_state.set(["core:client_receive_buffer"],[],True)
        #Stream client all mod JS files
        _send_mod_scripts(ws)
        while True:
            data = ws.receive()
            if data is None:
                break
            data = decode(data)
            # Route message to game state
            with game_state._lock:
                game_state.get(["core:client_receive_buffer"],False).append({"playerName":playerName,"data":data["params"]})
    finally:
        registry.dispatch("core:on_player_disconnect",game_state)
        #Remove from connected clients on client disconnect
        #If playerName is none, the websocket was closed before it was added to active_connections
        if playerName is not None:
            with active_connections_lock:
                active_connections.pop(playerName,None)
            #Set player to be offline
            with game_state._lock:
                game_state.set(["players",playerName,"online"],False,True)
            print(f"Client {playerName} disconnected.")

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
    lastTime=datetime.now()
    deltaTick=0
    while True:
        delta=datetime.now()-lastTime
        #Cap delta to prevent spiral
        deltaSec=min(delta.total_seconds(),0.05)
        deltaTick+=deltaSec
        lastTime=datetime.now()
        while deltaTick>=interval:
            try:
                game_state.set(["core:tickRate"],interval)
                #Dispatch tick handler
                registry.dispatch("core:tick_hook",game_state)
                #Send global broadcast data to client
                if game_state.exists(["core:sync_with_client"]):
                    with game_state._lock:
                        toSync=game_state.get(["core:sync_with_client"])
                        for i in toSync:
                            with active_connections_lock:
                                for connection in active_connections.values():
                                    connection.send(encode({"op":"core:sync_with_client","params":i}))
                        game_state.set(["core:sync_with_client"],[])
                else:
                    game_state.set(["core:sync_with_client"],[])
                #Send client-specific data to each client
                with active_connections_lock:
                    for player,connection in active_connections.items():
                        game_state.set(["core:per_client_sync"],{"player":player,"data":{}})
                        registry.dispatch("core:calculate_client_display",game_state)
                        connection.send(encode(game_state.get(["core:per_client_sync","data"])))
                game_state.set(["core:client_receive_buffer"],[])
            except Exception as e:
                if "Handled" not in e.__notes__:
                    traceback.print_exc()
                input("Please press enter to continue execution:")
            deltaTick-=interval
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
        for k,ws in active_connections.items():
            try:
                ws.close()
            except Exception:
                pass
    if flask_server:
        flask_server.shutdown()