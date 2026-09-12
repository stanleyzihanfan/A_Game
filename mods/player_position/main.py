"""
Player position handler mod (backend).

Initialises player state on connect, processes movement input each tick,
and syncs the computed position back to the respective client.
"""
import math

def testclient_server(gamestate,registry):
    if gamestate.exists(["core:client_receive_buffer"]) and gamestate.get(["core:client_receive_buffer"])!=[]:
        print(gamestate.get(["core:client_receive_buffer"]))

def testserver_client(gamestate,registry):
    if not (gamestate.exists(["core:global_broadcast"]) or isinstance(gamestate.get(["core:global_broadcast"]),list)):
        return
    cursync=gamestate.get(["core:global_broadcast"])
    cursync.append("Sent from Server")
    # cursync["player_position:testsend"]="Sent from Server"
    gamestate.set(["core:global_broadcast"],cursync)

def onConnect(gamestate, registry):
    """Set up default position, speed, and yaw for a newly connected player."""
    newPlayerName = gamestate.get(["players", "newPlayerName"])
    gamestate.initialize(["players", newPlayerName, "pos"], {"x": 0, "y": 0, "z": 0})
    gamestate.initialize(["players", newPlayerName, "speed"], 8)
    gamestate.initialize(["players", newPlayerName, "yaw"], 0)

def updatePlayerPosition(gamestate, registry):
    """Process movement input from clients and update their world positions."""
    for data in gamestate.get(["core:client_receive_buffer"]):
        if data["data"] == []:
            continue
        positionUpdateData = data["data"]["player_position:movement_handler"]
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

        pos = gamestate.get(["players", data["playerName"], "pos"])
        pos["x"] += dx; pos["y"] += dy; pos["z"] += dz
        gamestate.set(["players", data["playerName"], "pos"], pos)

def sendPlayerPosData(gamestate, registry):
    """Inject the current player's position into the per-client sync payload."""
    player = gamestate.get(["core:per_client_sync", "player"])
    curdata = gamestate.get(["core:per_client_sync", "data"])
    curdata["player_position:pos"] = gamestate.get(["players", player, "pos"])
    gamestate.set(["core:per_client_sync", "data"], curdata)

def register(registry):
    registry.register_handler("core:on_player_connect", onConnect, "player_position:initialize-player-state")
    registry.register_handler("core:tick_hook", updatePlayerPosition, "player_position:update-player-pos")
    registry.register_handler("core:calculate_client_display", sendPlayerPosData, "player_position:send-player-pos-data")
