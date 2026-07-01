# Placeholder voxel world — a few cubes at fixed positions
# Each entry is [x, y, z] in world space, 1 unit per voxel
voxelAdd = [
    [0, 0, 0], [1, 0, 0], [2, 0, 0],   # a row along X
    [1, 1, 0], [1, 2, 0],               # a column up
    [0, 0, 1], [2, 0, 2],               # scattered
]
voxelRemove = []

def syncBlocks(params):
    # Send current voxel state to client on request
    return [{"op": "block_add", "params": [voxelAdd]},
            {"op": "block_remove", "params": [voxelRemove]}]

def register(registry):
    registry.register_handler("testmod:syncBlocks", syncBlocks)