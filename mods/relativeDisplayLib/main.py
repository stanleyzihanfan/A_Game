def initialize(gamestate,registry):
    gamestate.initialize(["objects"],[])

def register(registry):
    registry.register_handler("core:on_mods_loaded",initialize,"init")
    registry.register_handler

