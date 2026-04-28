import subprocess, time, re, threading, socket, traceback, json, msgpack
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sock import Sock
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

    #Binary Packaging functions
    def encode(data):
        return msgpack.packb(data,use_bin_type=True)
    def decode(data):
        return msgpack.unpackb(data,raw=False)
    #Flask routes
    @app.route("/")
    def index():
        from flask import Response
        return Response(HTML, mimetype="text/html")

    @app.route("/init")
    def state():
        return jsonify({"voxels": VOXELS})
    #WebSocket Handlers
    def log(params):
        for i in range(len(params)):
            if (i==0):
                print(params[i],end='')
            else:
                print(params[i],end=' ')
        print()
    def warn(params):
        for i in range(len(params)):
            if (i==0):
                print("\033[33m"+params[i]+"\033[0m",end='')
            else:
                print("\033[33m"+params[i]+"\033[0m",end=' ')
        print()
    def error(params):
        for i in range(len(params)):
            if (i==0):
                print("\x1b[38;2;255;0;0m"+params[i]+"\033[0m",end='')
            else:
                print("\x1b[38;2;255;0;0m"+params[i]+"\033[0m",end=' ')
        print()
    #WebSocket Dispatch Table
    wsDispatch={"log":log,"warn":warn,"error":error}
    #WebSocket
    wSocket=Sock(app)
    #Send to client
    @wSocket.route("/client")
    def client():
        if add:
            return jsonify({"op":"ADD_VOXELS","voxels":add})
        if remove:
            return jsonify({"op":"REMOVE_VOXELS","voxels":add})
    
    #Receive from client
    @wSocket.route("/server")
    def server(ws):
        while (True):
            data=ws.receive()
            data=decode(data)
            handler=wsDispatch[data["op"]]
            if handler:
                handler(data["params"])
            else:
                print(data)

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
#Cleanly catch KeyboardInterupt(user stopping server)
except KeyboardInterrupt:
    print("Ctrl+C Received,")
except BaseException as e:
    print("Exeption caut in server:")
    traceback.print_exc()
finally:
    print("Gracefully shutting down server...")
    if flaskProc is not None:
        flaskProc.shutdown()
    if tunnelProc is not None:
        tunnelProc.terminate()
        tunnelProc.wait()