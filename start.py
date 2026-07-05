import argparse, subprocess, threading, traceback, shutil, os
from server import core

# -- Argument parsing ----------------------------------------------------------
# --tunnel flag exposes the server publicly via cloudflared (e.g. for multiplayer)
# Without it the server runs on localhost only (e.g. for local singleplayer)
parser = argparse.ArgumentParser()
parser.add_argument("--tunnel", action="store_true", help="Expose via cloudflared tunnel")
args = parser.parse_args()

#Helper function to locate cloudflared installation
def find_cloudflared():
    """
    Search for cloudflared in common locations.
    Returns the path to the cloudflared binary, or None if not found.
    """
    # Common locations on different systems
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
    # Only started when --tunnel flag is passed (e.g. for public multiplayer)
    # For local singleplayer, the server is accessed directly at localhost:{port}
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
        # Capture & print full output
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
    print("Gracefully shutting down server...")
    core.shutdown()
    if tunnelProc:
        tunnelProc.terminate()
        tunnelProc.wait()