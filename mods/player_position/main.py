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

def testclient_server(gamestate,registry):
    for entry in gamestate.get_client_messages():
        print(entry)

def testserver_client(gamestate,registry):
    gamestate.add_to_broadcast("testsend", "Sent from Server")

def onConnect(gamestate, registry):
    """Set up default position, speed, and yaw for a newly connected player."""
    newPlayerName = gamestate.get(["core:players", "newPlayerName"])
    gamestate.initialize(["core:players", newPlayerName, "pos"], {"x": 0, "y": 0, "z": 0, "pitch":0, "yaw":0})
    gamestate.initialize(["core:players", newPlayerName, "speed"], 8)
    gamestate.initialize(["core:players", newPlayerName, "yaw"], 0)
    gamestate.initialize(["core:players", newPlayerName, "pitch"], 0)

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
        # pos["yaw"]=yaw; pos["pitch"]=positionUpdateData["pitch"]
        gamestate.set(["core:players", data["playerName"], "pos"], pos)

def sendPlayerPosData(gamestate, registry):
    """Inject the current player's position into the per-client sync payload."""
    player = gamestate.get(["core:per_client_sync", "player"])
    pos = gamestate.get(["core:players", player, "pos"])
    gamestate.add_to_client_sync("pos", pos)

def register(registry):
    registry.register_handler("core:on_player_connect", onConnect, "initialize-player-state")
    registry.register_handler("core:tick_hook", updatePlayerPosition, "update-player-pos")
    registry.register_handler("core:calculate_client_display", sendPlayerPosData, "send-player-pos-data")