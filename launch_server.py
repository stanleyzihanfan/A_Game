"""
Server launcher script.

Starts the game backend server (Flask + WebSocket) and optionally creates a
public tunnel via cloudflared so remote clients can connect.
"""
import argparse, subprocess, threading, traceback, shutil, os
from server import core

# -- Argument parsing ----------------------------------------------------------
# --tunnel flag exposes the server publicly via cloudflared (e.g. for multiplayer).
# Without it the server runs on localhost only (e.g. for local singleplayer).
parser = argparse.ArgumentParser()
parser.add_argument("--tunnel", action="store_true", help="Expose via cloudflared tunnel")
args = parser.parse_args()

# -- Cloudflared discovery -------------------------------------------------------
def find_cloudflared():
    """Search for cloudflared in common locations; returns its path or None."""
    candidates = [
        "/usr/local/bin/cloudflared",           # Local Linux install
        "/usr/bin/cloudflared",                 # System-wide Linux install
        "/tools/node/lib/node_modules/cloudflared/bin/cloudflared",  # Colab
        shutil.which("cloudflared"),            # In PATH
    ]
    
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    
    return None

tunnelProc = None
try:
    port = core.start()

    # -- Tunnel (optional) -----------------------------------------------------
    # Only started when --tunnel is passed (e.g. for public multiplayer).
    if args.tunnel:
        CLOUDFLARED = find_cloudflared()
        if CLOUDFLARED==None:
            raise FileNotFoundError("Cloudflared Installation not found on machine.\nDid you forget to install cloudflared?")
        tunnelProc = subprocess.Popen(
            [CLOUDFLARED, "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT  # merge stderr into stdout so one loop sees everything
        )
        print("Starting tunnel, waiting for URL...")
        for line in tunnelProc.stdout: # type: ignore
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                print(text)
    else:
        print(f"Server running locally at http://localhost:{port}")
        # Block forever so the server stays alive
        threading.Event().wait()

# Cleanly catch KeyboardInterrupt (user stopping server)
except KeyboardInterrupt:
    print("\nCtrl+C received, shutting down...")
except BaseException:
    traceback.print_exc()
finally:
    print("Gracefully shutting down backend server...")
    core.shutdown()
    if tunnelProc:
        tunnelProc.terminate()
        tunnelProc.wait()