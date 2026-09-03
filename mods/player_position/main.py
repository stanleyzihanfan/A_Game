def testclient_server(gamestate,registry):
    print(gamestate.get(["client_receive_buffer"]))

def testserver_client(gamestate,registry):
    if not gamestate.exists(["sync_with_client"]):
        return
    with gamestate._lock:
        cursync=gamestate.get(["sync_with_client"])
        cursync["player_position:testsend"]="Sent from Server"
        gamestate.set(["sync_with_client"],cursync)

def register(registry):
    registry.register_handler("core:tick_hook",testclient_server,"player_position:client-server-test")
