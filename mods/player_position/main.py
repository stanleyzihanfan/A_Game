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

def register(registry):
    registry.register_handler("core:tick_hook",testclient_server,"player_position:client-server-test")
    registry.register_handler("core:tick_hook",testserver_client,"player_position:server-client-test")
