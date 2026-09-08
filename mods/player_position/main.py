import math

def testclient_server(gamestate,registry):
    if gamestate.exists(["core:client_receive_buffer"]) and gamestate.get(["core:client_receive_buffer"])!=[]:
        print(gamestate.get(["core:client_receive_buffer"]))

def testserver_client(gamestate,registry):
    if not (gamestate.exists(["core:sync_with_client"]) or isinstance(gamestate.get(["core:sync_with_client"]),list)):
        return
    with gamestate._lock:
        cursync=gamestate.get(["core:sync_with_client"])
        cursync.append("Sent from Server")
        # cursync["player_position:testsend"]="Sent from Server"
        gamestate.set(["core:sync_with_client"],cursync)

def updatePlayerPosition(gamestate, registry):
    # TODO:Adapt to use gamestate
    yaw = move_state["yaw"]
    speed = gamestate.get(["players", player_name, "speed"]) or 8

    # Unit circle (cos(yaw),sin(yaw)) rotated 90 degrees (sin(yaw),cos(yaw)), negated for -z=away from camera
    # y=0 because yaw affects only horizontal plane
    # forward vector: (-sin(yaw), 0, -cos(yaw))
    fx, fz = -math.sin(yaw), -math.cos(yaw)
    # right = forward x up, up = (0,1,0) -> right = (-fz, 0, fx) normalized (already unit length)
    rx, rz = -fz, fx

    dist = speed * dt
    dx = dz = dy = 0.0

    if move_state.get("forward"): dx += fx * dist; dz += fz * dist
    if move_state.get("back"):    dx -= fx * dist; dz -= fz * dist
    if move_state.get("left"):    dx -= rx * dist; dz -= rz * dist
    if move_state.get("right"):   dx += rx * dist; dz += rz * dist
    if move_state.get("up"):      dy += dist
    if move_state.get("down"):    dy -= dist

    pos = gamestate.get(["players", player_name, "position"]) or {"x":0,"y":0,"z":0}
    pos["x"] += dx; pos["y"] += dy; pos["z"] += dz
    gamestate.set(["players", player_name, "position"], pos, True)

def register(registry):
    registry.register_handler("core:tick_hook",testclient_server,"player_position:client-server-test")
    registry.register_handler("core:tick_hook",testserver_client,"player_position:server-client-test")
    pass
