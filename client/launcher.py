import socket, os, threading, mimetypes
from flask import Flask, Response,jsonify
from flask_cors import CORS
from werkzeug.serving import make_server

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
app = Flask(__name__)
CORS(app)

flask_server = None

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

@app.route('/requestAPIlink_fallback/', defaults={'item_id': None})
@app.route("/requestAPIlink_fallback/<default>")
def request_link(default):
    print("\x1b[38;2;255;0;0mIt appears that the client was unable to open a prompt pop-up for API link input!\033[0m")
    print("\033[33m  Please enter the link here instead.\033[0m")
    raw=None
    while not raw:
        print("  Enter server API link (e.g. https://xxxx.trycloudflare.com or http://localhost:5000),")
        if default:
            print(f"  Or press enter to autofill last link({default}):")
        raw=input()
        if raw=="":
            raw=default
        if not raw:
            print("\x1b[38;2;255;0;0m  Invalid input, try again.\033[0m")
    return jsonify({"rawURL":raw})
    #print("It appears that the client was unable to open a prompt pop-up for API link input!")

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
    if flask_server:
        flask_server.shutdown()