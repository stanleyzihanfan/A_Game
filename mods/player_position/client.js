/**
 * Player position handler mod (frontend).
 *
 * Applies the camera rotation from player yaw/pitch,
 * packages movement key states each tick for the server,
 * and updates the camera position when server sync arrives.
 */

// Apply yaw and pitch to the Three.js camera
function update_camera_rotation(gameState) {
    camera.rotation.order = "YXZ";
    camera.rotation.y = gameState.get(["playerData", "yaw"]);
    camera.rotation.x = gameState.get(["playerData", "pitch"]);
}

wsRegistry.register_handler("core:update_camera", update_camera_rotation, "player_position:updateCameraRotation");

function test_client_receive(gameState) {
	if (gameState.exists(["server_receive_buffer"]) && gameState.get(["server_receive_buffer"])?.length!==0){
		console.log(gameState.get(["server_receive_buffer"]));
	}
}
wsRegistry.register_handler("core:tick",test_client_receive,"player_position:test_client_receive");

// Collect held-movement keys and current yaw/speed into the send buffer
function update_player_move_data(gameState) {
    const sendbuffer = gameState.get(["client_send_buffer"]);
    const moveState = {};
    moveState.yaw = gameState.get(["playerData", "yaw"]);
    moveState.forward = gameState.get(["keys", "KeyW"]);
    moveState.back = gameState.get(["keys", "KeyS"]);
    moveState.left = gameState.get(["keys", "KeyA"]);
    moveState.right = gameState.get(["keys", "KeyD"]);
    moveState.up = gameState.get(["keys", "Space"]);
    moveState.down = gameState.get(["keys", "ShiftLeft"]);
    moveState.speed = gameState.get(["playerData", "speed"]);
    sendbuffer["player_position:movement_handler"] = moveState;
    gameState.set(["client_send_buffer"], sendbuffer);
}

wsRegistry.register_handler("core:tick", update_player_move_data, "player_position:updatePlayerMoveData");

// Apply authoritative position data sent back from the server
function update_player_position(gamestate) {
    if (gameState.exists(["server_receive_buffer"])) {
        for (const data of gamestate.get(["server_receive_buffer"])) {
            if (Object.hasOwn(data, "player_position:pos")) {
                const playerposdata = data["player_position:pos"];
                camera.position.x = playerposdata["x"];
                camera.position.y = playerposdata["y"];
                camera.position.z = playerposdata["z"];
            }
        }
    }
}

wsRegistry.register_handler("core:tick", update_player_position, "player_position:updatePlayerPos");