def testclient_server(gamestate,registry):
    print(gamestate.get(["client_receive_buffer"]))

def testserver_client(gamestate,registry):
    if not gamestate.exists(["sync_with_client"]):
        return
    cursync=gamestate.get(["sync_with_client"])
    cursync[]

def register(registry):
    registry.register_handler("core:tick_hook",testclient_server,"player_position:client-server-test")
