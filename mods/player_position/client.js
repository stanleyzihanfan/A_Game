/**
 * Player position handler mod (frontend).
 *
 * Applies the camera rotation from player yaw/pitch,
 * packages movement key states each tick for the server,
 * and updates the camera position when server sync arrives.
 *
 * Namespacing: this mod's manifest.json declares "namespace": "player_position".
 * The client applies it while this script is eval()ed, so every unqualified
 * op, handler name, and message key below is automatically prefixed — e.g.
 * "movement_handler" becomes "player_position:movement_handler". Core hooks
 * ("core:...") are always explicitly qualified and pass through untouched.
 */

// Apply yaw and pitch to the Three.js camera
function update_camera_rotation(gameState) {
    camera.rotation.order = "YXZ";
    camera.rotation.y = gameState.get(["core:playerData", "yaw"]);
    camera.rotation.x = gameState.get(["core:playerData", "pitch"]);
}

wsRegistry.register_handler("core:update_camera", update_camera_rotation, "updateCameraRotation");

function test_client_receive(gameState) {
	if (gameState.readServerMessages().length!==0){
		console.log(gameState.readServerMessages());
	}
}
// wsRegistry.register_handler("core:tick",test_client_receive,"test_client_receive");

// Collect held-movement keys and current yaw/speed into the send buffer
function update_player_move_data(gameState) {
    const moveState = {};
    moveState.yaw = gameState.get(["core:playerData", "yaw"]);
    moveState.pitch = gameState.get(["core:playerData","pitch"]);
    moveState.forward = gameState.isKeyDown("KeyW");
    moveState.back = gameState.isKeyDown("KeyS");
    moveState.left = gameState.isKeyDown("KeyA");
    moveState.right = gameState.isKeyDown("KeyD");
    moveState.up = gameState.isKeyDown("Space");
    moveState.down = gameState.isKeyDown("ShiftLeft");
    moveState.speed = gameState.get(["core:playerData", "speed"]);
    gameState.addToSendBuffer("movement_handler", moveState);
}

wsRegistry.register_handler("core:tick", update_player_move_data, "updatePlayerMoveData");

// Apply authoritative position data sent back from the server
function update_player_position(gameState) {
    for (const playerposdata of gameState.readServerMessages("pos")) {
        camera.position.x = playerposdata["x"];
        camera.position.y = playerposdata["y"];
        camera.position.z = playerposdata["z"];
        // gameState.set(["core:playerData","yaw"],playerposdata["yaw"]);
        // gameState.set(["core:playerData","pitch"],playerposdata["pitch"]);
    }
}

wsRegistry.register_handler("core:tick", update_player_position, "updatePlayerPos");