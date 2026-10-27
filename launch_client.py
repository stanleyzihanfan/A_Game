#!/usr/bin/env python3
"""
Game client launcher (wrapper).

Sets PROTEAN_MODS_DIR to this game's mods/ folder, then delegates to the
vendored Protean-Engine client launcher at engine/launch_client.py.

The engine launcher is executed IN-PROCESS (not via os.execv) so this wrapper is
also safe to run from a Jupyter/Colab notebook cell with `%run`. os.execv would
replace the whole interpreter — i.e. the notebook kernel — which makes the launch
cell show no output and leaves the session impossible to stop.

Usage:
    python3 launch_client.py [--tunnel]
"""
import os, sys, importlib.util

GAME_ROOT = os.path.dirname(os.path.abspath(__file__))

# Point the engine at this game's mods directory (the engine ships with none).
os.environ["PROTEAN_MODS_DIR"] = os.path.join(GAME_ROOT, "mods")

ENGINE_LAUNCHER = os.path.join(GAME_ROOT, "engine", "launch_client.py")

if not os.path.isfile(ENGINE_LAUNCHER):
    print(f"Engine launcher not found at {ENGINE_LAUNCHER}", file=sys.stderr)
    sys.exit(1)

# Load and run the engine launcher in this interpreter rather than re-execing.
# main() blocks while the client asset server runs and returns on interrupt
# (KeyboardInterrupt), so the calling process (CLI or notebook kernel) survives
# and the engine can resolve `import client` against its own root.
_launcher_spec = importlib.util.spec_from_file_location("_protean_client_launcher", ENGINE_LAUNCHER)
_launcher = importlib.util.module_from_spec(_launcher_spec)
_launcher_spec.loader.exec_module(_launcher)
_launcher.main()
