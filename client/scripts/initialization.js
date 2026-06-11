// -- WebSocket bootstrap -------------------------------------------------------
// Raw message handler before client is initialized
// Routes init, load_mod_js, and mods_ready — then hands off to mod dispatch
let WSConnectStartTime = -1;

socket.onopen = () => {
    WSConnectStartTime = performance.now();
}

//Global 

//Handler registration helper
function registerHandler(name,func){
    if (!Object.hasOwn(wsDispatch,name)) {
        wsDispatch[name]=[];
        console.log(`  Frontend Event Hook ${name} registered.`);
    }
    wsDispatch[name].push(func);
    console.log(`  Frontend Handler registered under ${name}`);
}
// Init handler — only runs until mods_ready is received
socket.onmessage = (e) => {
    const msg = msgpack.decode(new Uint8Array(e.data));
    if (msg["op"] === "init") {
        clientID = msg["params"][0];
        initClient();
        return;
    }
    else if (msg["op"] === "load_mod_js") {
        const [modID, src] = msg["params"];
        try {
            console.log(`Loading frontend mod script: ${modID}`);
            eval(src);
            console.log(`  ${modID} loaded OK`);
        } catch(err) {
            const div = document.getElementById("errorlog");
            if (div) div.innerText += `MOD LOAD ERROR (${modID}): ${err}\n`;
        }
        return;
    }
    else if (msg["op"] === "mods_ready") {
        onModsReady();
        return;
    }else{
        console.warn("Backend attempted to access frontend handler " + msg["op"]+" before mod initialization finished with params "+msg["params"]+".");
    }
}