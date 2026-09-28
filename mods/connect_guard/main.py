"""
Connection guard mod (backend).

Owns the connection-acceptance logic that used to live inline in server/core.py:
validating a client's player name and password on connect, creating the player's
state entry on first login, and rejecting the connection when the player is
already online or supplies the wrong password.

Design:
The engine (core.py) sets up a "connect_request" context in game state and
dispatches the "core:on_player_connect_request" hook BEFORE accepting the
websocket. This mod's handler reads that context, decides whether to accept,
and writes the outcome back. The mod only decides — core owns the socket
lifecycle and performs the actual ws.close() based on the recorded decision.
Keeping the socket in core (not in a mod) is deliberate: it preserves a single
owner for connections and active_connections bookkeeping.

Namespacing: this mod's manifest.json declares "namespace": "connect_guard".
All keys below are explicitly qualified ("core:..."), so they pass through the
auto-namespacing machinery untouched.
"""


def handle_connect_request(gamestate, registry):
    """Validate a connect attempt and record accept/reject in the request.

    Reads the request context core set up under ["core:connect_request"] and
    writes back its outcome:
      approved: True to accept the connection, False to reject it
      reason:   Human-readable rejection reason (used by core for logging)
      code:     WebSocket close code to use on rejection

    Accepting also creates the player's state entry (first login) or flips the
    existing player back online; rejecting leaves the stored online flag alone.
    """
    request = gamestate.get(["core:connect_request"])
    playerName = request["playerName"]
    psw = request["psw"]

    # New player: create the state entry and accept.
    if not gamestate.exists(["core:players", playerName]):
        gamestate.set(["core:players", playerName, "online"], True, True)
        gamestate.set(["core:players", playerName, "password"], psw, True)
        request["approved"] = True
        request["reason"] = None
        request["code"] = None
    # Already online: reject.
    elif gamestate.get(["core:players", playerName, "online"]):
        request["approved"] = False
        request["reason"] = "Player already online"
        request["code"] = 1002
    # Existing player: require the correct password.
    elif gamestate.get(["core:players", playerName, "password"]) != psw:
        request["approved"] = False
        request["reason"] = "Incorrect Password"
        request["code"] = 1000
    # Correct password: accept and mark online.
    else:
        gamestate.set(["core:players", playerName, "online"], True)
        request["approved"] = True
        request["reason"] = None
        request["code"] = None

    gamestate.set(["core:connect_request"], request)


def register(registry):
    registry.register_handler(
        "core:on_player_connect_request",
        handle_connect_request,
        "validate-connect",
    )
