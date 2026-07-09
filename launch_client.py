import argparse, subprocess, threading, traceback, shutil, os
from client import launcher

parser = argparse.ArgumentParser()
parser.add_argument("--tunnel", action="store_true", help="Expose client page via cloudflared tunnel")
args = parser.parse_args()

def find_cloudflared():
    candidates = [
        "/usr/local/bin/cloudflared",
        "/usr/bin/cloudflared",
        "/tools/node/lib/node_modules/cloudflared/bin/cloudflared",
        shutil.which("cloudflared"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None

tunnelProc = None
try:
    port = launcher.start()

    if args.tunnel:
        CLOUDFLARED = find_cloudflared()
        if CLOUDFLARED is None:
            raise FileNotFoundError("Cloudflared Installation not found on machine.\nDid you forget to install cloudflared?")
        tunnelProc = subprocess.Popen(
            [CLOUDFLARED, "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        print("Starting tunnel, waiting for URL...")
        for line in tunnelProc.stdout:  # type: ignore
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                print(text)
    else:
        print(f"Client available at http://localhost:{port}")
        threading.Event().wait()

except KeyboardInterrupt:
    print("\nCtrl+C received, shutting down...")
except BaseException:
    traceback.print_exc()
finally:
    print("Gracefully shutting down client asset server...")
    launcher.shutdown()
    if tunnelProc:
        tunnelProc.terminate()
        tunnelProc.wait()