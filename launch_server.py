#!/usr/bin/env python3
"""
Game server launcher (wrapper).

Sets UNBOXED_MODS_DIR to this game's mods/ folder, then delegates to the
vendored Unboxed-Engine server launcher at engine/launch_server.py. This keeps
the game's mods in its own repo while the engine stays a reusable subtree.

Usage:
    python3 launch_server.py [--tunnel]
"""
import os, sys

GAME_ROOT = os.path.dirname(os.path.abspath(__file__))

# Point the engine at this game's mods directory (the engine ships with none).
os.environ["UNBOXED_MODS_DIR"] = os.path.join(GAME_ROOT, "mods")

ENGINE_LAUNCHER = os.path.join(GAME_ROOT, "engine", "launch_server.py")

if not os.path.isfile(ENGINE_LAUNCHER):
    print(f"Engine launcher not found at {ENGINE_LAUNCHER}", file=sys.stderr)
    sys.exit(1)

# Re-exec with the same interpreter and forwarded args so the engine can
# resolve `import server` against its own root.
os.execv(sys.executable, [sys.executable, ENGINE_LAUNCHER] + sys.argv[1:])
