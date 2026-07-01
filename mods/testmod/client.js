// Test base game client mod
// Runs via eval() after load_mod_js is received
// Registers frontend WebSocket handlers for block_add and block_remove

// Storage of meshes & wireframes in scene
let meshReference = new Map();

// Add blocks to scene
function block_add(params) {
    params[0].forEach(e => {
        console.log(e);
        const x = e[0];
        const y = e[1];
        const z = e[2];
        // Solid cube
        const mesh = new THREE.Mesh(voxelGeo.clone(), voxelMat.clone());
        mesh.position.set(x + 0.5, y + 0.5, z + 0.5); // +0.5 so voxel sits on grid
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        scene.add(mesh);
        // Wireframe outline
        const edges = new THREE.LineSegments(new THREE.EdgesGeometry(voxelGeo), edgeMat);
        edges.position.copy(mesh.position);
        scene.add(edges);
        meshReference.set(`${x},${y},${z}`, [mesh, edges]);
    });
}

// Remove blocks from scene
function block_remove(params) {
    params.forEach(e => {
        const x = e[0];
        const y = e[1];
        const z = e[2];
        const toDelete = meshReference.get(`${x},${y},${z}`);
        if (toDelete !== undefined) {
            const mesh = toDelete[0];
            scene.remove(mesh);
            mesh.geometry.dispose();
            mesh.material.dispose();
            const edge = toDelete[1];
            scene.remove(edge);
            edge.geometry.dispose();
            edge.material.dispose();
        }
    });
}

// Register handlers
wsRegistry.register_handler("block_add",block_add);
wsRegistry.register_handler("block_remove",block_remove);