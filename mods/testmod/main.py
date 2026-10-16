# Test base game backend mod (deprecated — kept for reference)
# Placeholder voxel world — a few cubes at fixed positions, each [x, y, z] in
# world space (1 unit per voxel).
voxelAdd = [
    [0, 0, 0], [1, 0, 0], [2, 0, 0],   # a row along X
    [1, 1, 0], [1, 2, 0],               # a column up
    [0, 0, 1], [2, 0, 2],               # scattered
]
voxelRemove = []

def syncBlocks(params):
    return [{"op": "block_add", "params": [voxelAdd]},
            {"op": "block_remove", "params": [voxelRemove]}]

def register(registry):
    # Deprecated op registration — uncomment to bring testmod back.
    # Under auto-namespacing this registers under "testmod:syncBlocks", so the
    # caller must use that fully-qualified form.
    # registry.register_handler("syncBlocks", syncBlocks)
    pass