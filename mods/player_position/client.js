function update_camera_rotation(gameState){
    camera.rotation.order = "YXZ";
    camera.rotation.y = gameState.get(["playerData","yaw"]); 
    camera.rotation.x = gameState.get(["playerData","pitch"]);
}

wsRegistry.register_handler("core:update_camera",update_camera_rotation);

function update_player_position(gameState) {
	// const forward = new THREE.Vector3();
	// const right = new THREE.Vector3();
	// const up = new THREE.Vector3(0, 1, 0);
	// const dt=gameState.get(["deltaTime"]);
	// const dist = gameState.get(["playerData","speed"])*dt;
	// forward.set(Math.sin(gameState.get(["playerData","yaw"])), 0, Math.cos(gameState.get(["playerData","yaw"]))).negate();
	// right.crossVectors(forward, up).normalize();
	// if (gameState.get(["keys","KeyW"])) camera.position.addScaledVector(forward, dist);
	// if (gameState.get(["keys","KeyS"])) camera.position.addScaledVector(forward, -dist);
	// if (gameState.get(["keys","KeyA"])) camera.position.addScaledVector(right, -dist);
	// if (gameState.get(["keys","KeyD"])) camera.position.addScaledVector(right, dist);
	// if (gameState.get(["keys","Space"])) camera.position.y += dist;
	// if (gameState.get(["keys","ShiftLeft"]) || gameState.get(["keys","ShiftRight"])) camera.position.y -= dist;
    sendbuffer = gameState.get(["client_send_buffer"]);
    let moveState = {};
	moveState.yaw=gameState.get(["playerData","yaw"]);
	moveState.forward=gameState.get(["keys","KeyW"]);
	moveState.back=gameState.get(["keys","KeyS"]);
	moveState.left=gameState.get(["keys","KeyA"]);
	moveState.right=gameState.get(["keys","KeyD"]);
	moveState.up=gameState.get(["keys","Space"]);
	moveState.down=gameState.get(["keys","ShiftLeft"]);
    sendbuffer.push(moveState);
	gameState.set(["client_send_buffer"],sendbuffer);
}

wsRegistry.register_handler("core:tick",update_player_position);