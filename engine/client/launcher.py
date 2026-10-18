"""
Client asset server.

Serves the HTML frontend, static files (JS, CSS), and provides a separate
WebSocket endpoint (/clientlog) for catching browser console output.
"""
import socket, os, re, threading, mimetypes, json, msgpack
from flask import Flask, Response, jsonify
from flask_cors import CORS
from flask_sock import Sock
from werkzeug.serving import make_server

# -- Flask app & global state ----------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
app = Flask(__name__)
CORS(app)
wSocket = Sock(app)

# The mods directory the hosting game points at (PROTEAN_MODS_DIR). The client
# asset server reads mod manifests from here to discover any mod "preload"
# scripts (client_preload_js) that must be injected into the page BEFORE the
# bootstrap scripts run — e.g. a mod that owns the pre-connection screen.
MODS_DIR = os.environ.get("PROTEAN_MODS_DIR") or os.path.join(BASE_DIR, "mods")

flask_server = None

# Track active log-socket connections for clean shutdown
active_log_connections = set()
active_log_connections_lock = threading.Lock()

def decode(data):
    return msgpack.unpackb(data, raw=False)

# -- Routes: frontend page & static assets ---------------------------------------
# Serves the HTML page at "/" and every other file under the project root
# (e.g. client/scripts/*.js, client/styles.css) via the catch-all route.
#
# To keep mod-served frontend files (like a connect screen) reachable, the
# catch-all route also resolves paths under MODS_DIR. If a requested path is
# not an engine file, we look for <MODS_DIR>/<path> so mods can refer to their
# own assets by a normal relative URL.

def _find_mod_preload_scripts():
    """Return the list of mod preload script files to inject into the page.

    Scans MODS_DIR for mod manifests declaring a "client_preload_js" field and
    resolves each to an absolute file path. These scripts are injected into the
    frontend page (as <script> tags) so they run BEFORE the bootstrap scripts.

    :return: list of absolute file paths
    """
    scripts = []
    if not os.path.isdir(MODS_DIR):
        return scripts
    for mod_folder in sorted(os.listdir(MODS_DIR)):
        mod_path = os.path.join(MODS_DIR, mod_folder)
        if not os.path.isdir(mod_path):
            continue
        manifest_path = os.path.join(mod_path, "manifest.json")
        if not os.path.isfile(manifest_path):
            continue
        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        # Respect the same disabled flag the server mod loader uses.
        if not manifest.get("enabled", True):
            continue
        preload = manifest.get("client_preload_js")
        if not preload:
            continue
        preload_path = os.path.join(mod_path, preload)
        if not os.path.isfile(preload_path):
            print(f"\x1b[33m  client_preload_js '{preload}' not found for mod '{manifest.get('modID')}'\033[0m")
            continue
        scripts.append(preload_path)
    return scripts


def _inject_preload_scripts(html):
    """Inject <script> tags for mod preload scripts just after <body>.

    Preload scripts run BEFORE the bootstrap <script> tags (pre_initialization.js,
    main.js), so they can register a connect-screen provider (or any other early
    hook) that the bootstrap checks at load time. They are served from the mods
    directory via the catch-all route, so we reference them by their path
    relative to MODS_DIR (e.g. 'connect_screen/client_preload.js').

    :param html: The frontend HTML page source
    :return: The HTML page with preload <script> tags injected
    """
    scripts = _find_mod_preload_scripts()
    if not scripts:
        return html
    tags = []
    for path in scripts:
        # Path relative to MODS_DIR, e.g. "connect_screen/client_preload.js".
        rel = os.path.relpath(path, MODS_DIR)
        tags.append(f'<script src="{rel}"></script>')
    block = "\n".join(tags)
    # Insert right after the <body> opening tag so preload scripts run before
    # the bootstrap scripts (which live at the end of <body>).
    m = re.search(r"<body[^>]*>", html, flags=re.IGNORECASE)
    if not m:
        return html
    marker = m.group(0)
    return html.replace(marker, marker + "\n" + block, 1)


@app.route("/")
def index():
    with open(os.path.join(BASE_DIR, "client/frontend.html"), "r") as f:
        return Response(_inject_preload_scripts(f.read()), mimetype="text/html")

@app.route("/<path:filename>")
def static_file(filename):
    # First check the engine's own files, then fall back to the mods directory.
    filepath = os.path.join(BASE_DIR, filename)
    if not os.path.isfile(filepath):
        # Only fall back to mods if the resolved path stays within MODS_DIR
        # (guards against ../ path traversal).
        if os.path.isdir(MODS_DIR):
            candidate = os.path.join(MODS_DIR, filename)
            real_candidate = os.path.realpath(candidate)
            real_mods = os.path.realpath(MODS_DIR)
            if os.path.isfile(candidate) and real_candidate.startswith(real_mods + os.sep):
                filepath = candidate
            else:
                return "Not found", 404
        else:
            return "Not found", 404
    mimetype, _ = mimetypes.guess_type(filepath)
    if not mimetype:
        mimetype = "text/plain"
    with open(filepath, "r") as f:
        return Response(f.read(), mimetype=mimetype)

# -- Routes: client log WebSocket -------------------------------------------------
# Separate endpoint from the game server's WebSocket; the browser posts its
# console logs here so they appear in the terminal that launched this server.
@wSocket.route("/clientlog")
def clientlog(ws):
    """Receive browser console/warn/error + onerror/onunhandledrejection and print
    them to the terminal that launched this client asset server. Independent of the
    game server's WebSocket."""
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

# -- Port finder -----------------------------------------------------------------
# Shared helper: find a free TCP port, incrementing until one is open.
def find_port(start=8000):
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

# -- Server lifecycle -------------------------------------------------------------
# start() runs the Flask server on a background thread; shutdown() closes any
# open log sockets and stops Flask.
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