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


def onConnect(gamestate,registry):
    newPlayerName=gamestate.get(["players","newPlayerName"])
    if not gamestate.exists(["players",newPlayerName,"pos"]):
        gamestate.set(["players",newPlayerName,"pos"],{"x":0,"y":0,"z":0},True)

def updatePlayerPosition(gamestate, registry):
    # TODO:Adapt to use gamestate
    for data in gamestate.get(["core:client_receive_buffer"]):
        print(data)
        if data["data"]==[]:
            continue
        positionUpdateData=data["data"]["player_position:movement_handler"]
        yaw = positionUpdateData["yaw"]
        speed = positionUpdateData["speed"]

        # Unit circle (cos(yaw),sin(yaw)) rotated 90 degrees (sin(yaw),cos(yaw)), negated for -z=away from camera
        # y=0 because yaw affects only horizontal plane
        # forward vector: (-sin(yaw), 0, -cos(yaw))
        fx, fz = -math.sin(yaw), -math.cos(yaw)
        # right = forward x up, up = (0,1,0) -> right = (-fz, 0, fx) normalized (already unit length)
        rx, rz = -fz, fx

        dist = speed * gamestate.get(["core:tickRate"])
        dx = dz = dy = 0.0

        if positionUpdateData["forward"]: dx += fx * dist; dz += fz * dist
        if positionUpdateData["back"]:    dx -= fx * dist; dz -= fz * dist
        if positionUpdateData["left"]:    dx -= rx * dist; dz -= rz * dist
        if positionUpdateData["right"]:   dx += rx * dist; dz += rz * dist
        if positionUpdateData["up"]:      dy += dist
        if positionUpdateData["down"]:    dy -= dist

        pos = gamestate.get(["players",data["playerName"],"pos"])
        pos["x"] += dx; pos["y"] += dy; pos["z"] += dz
        gamestate.set(["players", data["playerName"], "position"], pos)

def sendPlayerPosData(gamestate,registry):
    player=gamestate.get(["core:per_client_sync","player"])
    curdata=gamestate.get(["core:per_client_sync","data"])
    curdata["player_position:pos"]=gamestate.get(["players",player,"position"])
    gamestate.set(["core:per_client_sync","data"],curdata)
    print(gamestate.get(["core:per_client_sync","data"]))

def register(registry):
    # registry.register_handler("core:tick_hook",testclient_server,"player_position:client-server-test")
    # registry.register_handler("core:tick_hook",testserver_client,"player_position:server-client-test")
    registry.register_handler("core:on_player_connect",onConnect,"player_position:initialize-player-state")
    registry.register_handler("core:tick_hook",updatePlayerPosition,"player_position:update-player-pos")
    registry.register_handler("core:calculate_client_display",sendPlayerPosData,"player_position:send-player-pos-data")
