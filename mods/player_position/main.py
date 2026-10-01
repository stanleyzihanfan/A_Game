"""
Player position handler mod (backend).

Initialises player state on connect, processes movement input each tick,
and syncs the computed position back to the respective client.

Namespacing: this mod's manifest.json declares "namespace": "player_position".
Every unqualified op, handler name, and game-state key below is automatically
prefixed with it at load time — e.g. "movement_handler" becomes
"player_position:movement_handler". Core keys ("core:...") are always
explicitly qualified and pass through untouched.
"""
import math

# -- Debug helper (not registered) ----------------------------------------------
# These two functions are standalone test scratch-pads, not wired into register().
# testclient_server dumps whatever the clients sent; testserver_client pushes a
# marker string out to every client. Kept as reference for debugging the
# send/receive buffer helpers.
def testclient_server(gamestate,registry):
    for entry in gamestate.get_client_messages():
        print(entry)

def testserver_client(gamestate,registry):
    gamestate.add_to_broadcast("testsend", "Sent from Server")

# -- Connect handler --------------------------------------------------------------
# Runs on the core:on_player_connect hook: gives a newly connected player its
# default position/speed/look state, then delivers that state to the client as a
# one-time init message.
def onConnect(gamestate, registry):
    """Set up default position, speed, and yaw for a newly connected player."""
    newPlayerName = gamestate.get(["core:players", "newPlayerName"])
    gamestate.initialize(["core:players", newPlayerName, "pos"], {"x": 0, "y": 0, "z": 0, "pitch":0, "yaw":0})
    gamestate.initialize(["core:players", newPlayerName, "speed"], 8)
    gamestate.initialize(["core:players", newPlayerName, "yaw"], 0)
    gamestate.initialize(["core:players", newPlayerName, "pitch"], 0)
    # Deliver the initialized player state to the just-connected client as a
    # one-time init message.
    gamestate.add_to_client_sync("pos", gamestate.get(["core:players", newPlayerName, "pos"]))

# -- Movement handler --------------------------------------------------------------
# Runs on the core:tick_hook once per tick: reads each client's movement input
# from the receive buffer, integrates it into that player's world position, and
# stores the updated position back into game state.
def updatePlayerPosition(gamestate, registry):
    """Process movement input from clients and update their world positions."""
    # The client sends this mod's movement data under the namespaced key
    # ("movement_handler" -> "player_position:movement_handler" on the client).
    ns = registry.current_namespace()
    for data in gamestate.get_client_messages():
        moveState = data["data"].get(f"{ns}:movement_handler")
        if moveState is None:
            continue
        positionUpdateData = moveState
        yaw = positionUpdateData["yaw"]
        speed = positionUpdateData["speed"]

        # forward vector on the horizontal plane (-z is "away" from the camera)
        fx, fz = -math.sin(yaw), -math.cos(yaw)
        # right vector is forward rotated 90 deg around Y
        rx, rz = -fz, fx

        dist = speed * gamestate.get(["core:tickRate"])
        dx = dz = dy = 0.0

        if positionUpdateData["forward"]: dx += fx * dist; dz += fz * dist
        if positionUpdateData["back"]:    dx -= fx * dist; dz -= fz * dist
        if positionUpdateData["left"]:    dx -= rx * dist; dz -= rz * dist
        if positionUpdateData["right"]:   dx += rx * dist; dz += rz * dist
        if positionUpdateData["up"]:      dy += dist
        if positionUpdateData["down"]:    dy -= dist

        pos = gamestate.get(["core:players", data["playerName"], "pos"])
        pos["x"] += dx; pos["y"] += dy; pos["z"] += dz
        # Persist look direction alongside position so it survives to the next
        # login — the init payload that initialize_player_position reads on
        # relog must carry the player's real yaw/pitch, not the default 0/0.
        pos["yaw"] = yaw
        pos["pitch"] = positionUpdateData["pitch"]
        gamestate.set(["core:players", data["playerName"], "pos"], pos)

# -- Per-client display sync --------------------------------------------------------
# Runs on the core:calculate_client_display hook: injects the current player's
# position into the per-client sync payload so it can be sent back to that client.
def sendPlayerPosData(gamestate, registry):
    """Inject the current player's position into the per-client sync payload."""
    player = gamestate.get(["core:per_client_sync", "player"])
    pos = gamestate.get(["core:players", player, "pos"])
    gamestate.add_to_client_sync("pos", pos)

def register(registry):
    registry.register_handler("core:on_player_connect", onConnect, "initialize-player-state")
    registry.register_handler("core:tick_hook", updatePlayerPosition, "update-player-pos")
    registry.register_handler("core:calculate_client_display", sendPlayerPosData, "send-player-pos-data")