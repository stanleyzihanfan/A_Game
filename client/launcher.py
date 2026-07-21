import socket, os, threading, mimetypes, msgpack
from flask import Flask, Response, jsonify
from flask_cors import CORS
from flask_sock import Sock
from werkzeug.serving import make_server

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
app = Flask(__name__)
CORS(app)
wSocket = Sock(app)

flask_server = None

# Track active log-socket connections for clean shutdown
active_log_connections = set()
active_log_connections_lock = threading.Lock()

def decode(data):
    return msgpack.unpackb(data, raw=False)

@app.route("/")
def index():
    with open(os.path.join(BASE_DIR, "client/frontend.html"), "r") as f:
        return Response(f.read(), mimetype="text/html")

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

@wSocket.route("/clientlog")
def clientlog(ws):
    """Receives console.log/warn/error + window.onerror/onunhandledrejection
    from the browser client and prints them to whichever terminal launched
    this client asset server. Independent of the game server's WebSocket."""
    with active_log_connections_lock:
        active_log_connections.add(ws)
    try:
        while True:
            data = ws.receive()
            if data is None:
                break
            msg = decode(data)
            level = msg.get("level", "log")
            timestamp = msg.get("timestamp", "")
            playerName = msg.get("playerName")
            args = msg.get("args", [])

            tag = f"[Client #{playerName}]" if playerName is not None else "[Client]"
            line = " ".join(str(a) for a in args)

            if level == "warn":
                print(f"\033[33m{timestamp} {tag} {line}\033[0m")
            elif level == "error":
                print(f"\x1b[38;2;255;0;0m{timestamp} {tag} {line}\033[0m")
            else:
                print(f"{timestamp} {tag} {line}")
    finally:
        with active_log_connections_lock:
            active_log_connections.discard(ws)

def find_port(start=8000):
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

def start():
    global flask_server
    port = find_port()
    print(f"Port {port} open, launching client asset server")
    flask_server = make_server("0.0.0.0", port, app, threaded=True)
    t = threading.Thread(target=flask_server.serve_forever, daemon=True)
    t.start()
    print(f"Client assets served on port {port}")
    return port

def shutdown():
    with active_log_connections_lock:
        for ws in active_log_connections:
            try:
                ws.close()
            except Exception:
                pass
    if flask_server:
        flask_server.shutdown()