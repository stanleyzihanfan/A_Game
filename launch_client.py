#!/usr/bin/env python3
"""
Game client launcher (wrapper).

Sets UNBOXED_MODS_DIR to this game's mods/ folder, then delegates to the
vendored Unboxed-Engine client launcher at engine/launch_client.py.

Usage:
    python3 launch_client.py [--tunnel]
"""
import os, sys

GAME_ROOT = os.path.dirname(os.path.abspath(__file__))

# Point the engine at this game's mods directory (the engine ships with none).
os.environ["UNBOXED_MODS_DIR"] = os.path.join(GAME_ROOT, "mods")

ENGINE_LAUNCHER = os.path.join(GAME_ROOT, "engine", "launch_client.py")

if not os.path.isfile(ENGINE_LAUNCHER):
    print(f"Engine launcher not found at {ENGINE_LAUNCHER}", file=sys.stderr)
    sys.exit(1)

# Re-exec with the same interpreter and forwarded args so the engine can
# resolve `import client` against its own root.
os.execv(sys.executable, [sys.executable, ENGINE_LAUNCHER] + sys.argv[1:])
