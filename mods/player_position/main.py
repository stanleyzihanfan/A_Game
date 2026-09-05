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

def updatePlayerPosition(gamestate,registry):
	# const forward = new THREE.Vector3();
	# const right = new THREE.Vector3();
	# const up = new THREE.Vector3(0, 1, 0);
	# const dt=gameState.get(["deltaTime"]);
	# const dist = gameState.get(["playerData","speed"])*dt;
	# forward.set(Math.sin(gameState.get(["playerData","yaw"])), 0, Math.cos(gameState.get(["playerData","yaw"]))).negate();
	# right.crossVectors(forward, up).normalize();
	# if (gameState.get(["keys","KeyW"])) camera.position.addScaledVector(forward, dist);
	# if (gameState.get(["keys","KeyS"])) camera.position.addScaledVector(forward, -dist);
	# if (gameState.get(["keys","KeyA"])) camera.position.addScaledVector(right, -dist);
	# if (gameState.get(["keys","KeyD"])) camera.position.addScaledVector(right, dist);
	# if (gameState.get(["keys","Space"])) camera.position.y += dist;
	# if (gameState.get(["keys","ShiftLeft"]) || gameState.get(["keys","ShiftRight"])) camera.position.y -= dist;
    pass

def register(registry):
    registry.register_handler("core:tick_hook",testclient_server,"player_position:client-server-test")
    registry.register_handler("core:tick_hook",testserver_client,"player_position:server-client-test")
    pass
