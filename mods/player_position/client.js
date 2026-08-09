function update_camera_rotation(gameState){
    camera.rotation.order = "YXZ";
    camera.rotation.y = gameState.get(["playerData","yaw"]); 
    camera.rotation.x = gameState.get(["playerData","pitch"]);
}

wsRegistry.register_handler("core:update_camera",update_camera_rotation);

function update_player_position(gameState){
    const forward = new THREE.Vector3();
    const right = new THREE.Vector3();
    const up = new THREE.Vector3(0, 1, 0);
    const dt=gameState.get(["deltaTime"]);
    const dist = gameState.get(["playerData","speed"])*dt;
    forward.set(Math.sin(gameState.get(["playerData","yaw"])), 0, Math.cos(gameState.get(["playerData","yaw"]))).negate();
    right.crossVectors(forward, up).normalize();
    if (keys["KeyW"]) camera.position.addScaledVector(forward, dist);
    if (keys["KeyS"]) camera.position.addScaledVector(forward, -dist);
    if (keys["KeyA"]) camera.position.addScaledVector(right, -dist);
    if (keys["KeyD"]) camera.position.addScaledVector(right, dist);
    if (keys["Space"]) camera.position.y += dist;
    if (keys["ShiftLeft"] || keys["ShiftRight"]) camera.position.y -= dist;
}

wsRegistry.register_handler("core:tick",update_player_position);