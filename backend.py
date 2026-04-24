import subprocess, time, re, threading, socket, traceback
from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.serving import make_server

tunnelProc=None
flaskProc=None
try:
    app = Flask(__name__)
    CORS(app)

    # Placeholder voxel world — a few cubes at fixed positions
    # Each entry is [x, y, z] in world space, 1 unit per voxel
    VOXELS = [
        [0, 0, 0], [1, 0, 0], [2, 0, 0],   # a row along X
        [1, 1, 0], [1, 2, 0],               # a column up
        [0, 0, 1], [2, 0, 2],               # scattered
    ]
    #voxels to add
    add=[]
    #voxels to remove
    remove=[]

    #Flask routes
    @app.route("/")
    def index():
        from flask import Response
        return Response(HTML, mimetype="text/html")

    @app.route("/init")
    def state():
        return jsonify({"voxels": VOXELS})
    #WebSocket
    sock=Sock(app)
    @sock.route("/ws")
    def ws():
        if add:
            return jsonify({"op":"ADD_VOXELS","voxels":add})
        if remove:
            return jsonify({"op":"REMOVE_VOXELS","voxels":add})

    #Flask server launch sequence
    port=5000
    #Find open port
    def find_port():
        global port
        while (True):
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                try:
                    s.bind(("",port))
                    break
                except OSError:
                    print(f"Port {port} already in use, trying {port+1} next")
                    print()
                    port+=1
                    continue
    find_port()
    print(f"Port {port} open, launching server")
    flaskProc=make_server("0.0.0.0",port,app)
    t = threading.Thread(target=flaskProc.serve_forever, daemon=True)
    t.start()
    print(f"Flask running on port {port}")

    CLOUDFLARED = "/tools/node/lib/node_modules/cloudflared/bin/cloudflared"

    tunnelProc = subprocess.Popen(
        [CLOUDFLARED, "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT  # merge stderr into stdout so one loop sees everything
    )

    print("Starting tunnel, waiting for URL...")
    #Capture & print full output
    for line in tunnelProc.stdout: #type:ignore
        text = line.decode("utf-8", errors="replace").strip()
        if text:
            print(text)
except:
    print("Exeption caut in server")
    print("Gracefully shutting down server...")
    tunnelProc.terminate()
    flaskProc.shutdown()
    tunnelProc.wait()