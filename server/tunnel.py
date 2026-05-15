import argparse, subprocess, threading, traceback
from server import core

# -- Argument parsing ----------------------------------------------------------
# --tunnel flag exposes the server publicly via cloudflared (e.g. for multiplayer)
# Without it the server runs on localhost only (e.g. for local singleplayer)
parser = argparse.ArgumentParser()
parser.add_argument("--tunnel", action="store_true", help="Expose via cloudflared tunnel")
args = parser.parse_args()

tunnelProc = None
try:
    port = core.start()

    # -- Tunnel (optional) -----------------------------------------------------
    # Only started when --tunnel flag is passed (e.g. for public multiplayer)
    # For local singleplayer, the server is accessed directly at localhost:{port}
    if args.tunnel:
        CLOUDFLARED = "/tools/node/lib/node_modules/cloudflared/bin/cloudflared"
        tunnelProc = subprocess.Popen(
            [CLOUDFLARED, "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT  # merge stderr into stdout so one loop sees everything
        )
        print("Starting tunnel, waiting for URL...")
        # Capture & print full output
        for line in tunnelProc.stdout: # type: ignore
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                print(text)
    else:
        print(f"Server running locally at http://localhost:{port}")
        # Block forever so the server stays alive (tunnel loop did this implicitly before)
        threading.Event().wait()

# Cleanly catch KeyboardInterrupt (user stopping server)
except KeyboardInterrupt:
    print("Ctrl+C received, shutting down...")
except BaseException:
    traceback.print_exc()
finally:
    print("Gracefully shutting down server...")
    core.shutdown()
    if tunnelProc:
        tunnelProc.terminate()
        tunnelProc.wait()