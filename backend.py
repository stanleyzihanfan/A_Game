import subprocess, time, re, threading, socket, traceback, json, msgpack
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sock import Sock
from werkzeug.serving import make_server

tunnelProc=None
flaskProc=None
# Track active websocket connections
active_connections = set()
active_connections_lock = threading.Lock()
try:
    app = Flask(__name__)
    CORS(app)

    # Placeholder voxel world — a few cubes at fixed positions
    # Each entry is [x, y, z] in world space, 1 unit per voxel
    voxelAdd = [
        [0, 0, 0], [1, 0, 0], [2, 0, 0],   # a row along X
        [1, 1, 0], [1, 2, 0],               # a column up
        [0, 0, 1], [2, 0, 2],               # scattered
    ]
    voxelRemove=[]
    #voxels to add
    add=[]
    #voxels to remove
    remove=[]
    #Client ID counter
    clientID=0

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

    # @app.route("/init")
    # def state():
    #     global clientID
    #     msg=jsonify(clientID)
    #     clientID+=1
    #     return msg
    
    #Socket initialization
    socketConnected=False
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
    def assignClientID(params):
        global clientID
        msg=clientID
        clientID+=1
        return [{"op":"assignClientID","params":[msg]}]
    def syncModifications(params):
        return [{"op":"block_add","params":[voxelAdd]},{"op":"block_remove","params":[voxelRemove]}]

    #WebSocket Dispatch Table
    wsDispatch={
        "log":log,
        "warn":warn,
        "error":error,
        "syncBlocks":syncModifications
    }
    #WebSocket
    wSocket=Sock(app)
    
    #Receive from client
    @wSocket.route("/server")
    def server(ws):
        global clientID
        #Store & increment clientID
        myID = clientID
        clientID += 1
        
        with active_connections_lock:
            active_connections.add(ws)
        
        try:
            ws.send(encode({"op": "init", "params": [myID]}))
            while True:
                data = ws.receive()
                if data is None:
                    break
                data = decode(data)
                handler = wsDispatch.get(data["op"])
                if handler:
                    returnValue = handler(data["params"])
                    if returnValue:
                        for i in returnValue:
                            ws.send(encode(i))
                else:
                    print(f"\x1b[31mFrontend attempted unknown handler: {data['op']}\033[0m")
        finally:
            with active_connections_lock:
                active_connections.discard(ws)

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
    flaskProc=make_server("0.0.0.0",port,app,threaded=True)
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
    with active_connections_lock:
        for ws in active_connections:
            try:
                ws.close()
            except Exception:
                pass
    if flaskProc is not None:
        flaskProc.shutdown()
    if tunnelProc is not None:
        tunnelProc.terminate()
        tunnelProc.wait()