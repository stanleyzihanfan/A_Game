"""
Client launcher script.

Starts the client asset server (Flask) and optionally creates a public tunnel
via cloudflared so remote browsers can connect.

The engine's ``client`` package is resolved from the engine root (the folder
containing this script), so this launcher works both from the engine repo root
and from a game that embeds the engine under an ``engine/`` subfolder.
"""
import argparse, subprocess, threading, traceback, shutil, os, sys

# Make sure the engine root is on sys.path so `import client` resolves whether
# this file is run from the engine repo root or from a game that embeds the
# engine under an `engine/` subfolder.
_ENGINE_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ENGINE_ROOT not in sys.path:
    sys.path.insert(0, _ENGINE_ROOT)

from client import launcher

# -- Cloudflared discovery -------------------------------------------------------
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


def main(argv=None):
    """Entry point. Returns an exit code."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--tunnel", action="store_true", help="Expose client page via cloudflared tunnel")
    args = parser.parse_args(argv)

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
                stderr=subprocess.STDOUT,
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
        return 130
    except BaseException:
        traceback.print_exc()
        return 1
    finally:
        print("Gracefully shutting down client asset server...")
        launcher.shutdown()
        if tunnelProc:
            tunnelProc.terminate()
            tunnelProc.wait()
    return 0


if __name__ == "__main__":
    sys.exit(main())
