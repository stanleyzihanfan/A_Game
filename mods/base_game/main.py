# Base game mod — backend handlers
# Registers all core WebSocket ops with the central registry

# Placeholder voxel world — a few cubes at fixed positions
# Each entry is [x, y, z] in world space, 1 unit per voxel
voxelAdd = [
    [0, 0, 0], [1, 0, 0], [2, 0, 0],   # a row along X
    [1, 1, 0], [1, 2, 0],               # a column up
    [0, 0, 1], [2, 0, 2],               # scattered
]
voxelRemove = []

# -- Handler functions ---------------------------------------------------------

def log(params):
    # Print each param space-separated, first param has no leading space
    for i in range(len(params)):
        if i == 0:
            print(params[i], end='')
        else:
            print(params[i], end=' ')
    print()

def warn(params):
    for i in range(len(params)):
        if i == 0:
            print("\033[33m" + params[i] + "\033[0m", end='')
        else:
            print("\033[33m" + params[i] + "\033[0m", end=' ')
    print()

def error(params):
    for i in range(len(params)):
        if i == 0:
            print("\x1b[38;2;255;0;0m" + params[i] + "\033[0m", end='')
        else:
            print("\x1b[38;2;255;0;0m" + params[i] + "\033[0m", end=' ')
    print()

def syncBlocks(params):
    # Send current voxel state to client on request
    return [{"op": "block_add", "params": [voxelAdd]},
            {"op": "block_remove", "params": [voxelRemove]}]

# -- Mod entry point -----------------------------------------------------------
# Called by mod_loader.py — registers all base game ops with the central registry

def register(registry):
    registry.register_handler("log", log)
    registry.register_handler("warn", warn)
    registry.register_handler("error", error)
    registry.register_handler("syncBlocks", syncBlocks)
    print("  Handlers registered: log, warn, error, syncBlocks")