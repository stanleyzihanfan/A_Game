"""
Example Mod — backend (server side).

This is a self-contained, heavily-commented walkthrough of the server-side
modding API. It is deliberately *defensive* (it never assumes game content is
present) so it runs against a bare engine with zero mods — ideal for learning
the API or for any game that embeds the engine.

It demonstrates, in one mod:

  * The `register(registry)` entry point and auto-namespacing.
  * The server `Registry` (register_handler / dispatch / get_handler).
  * The server `GameState` (get / set / initialize / exists).
  * Reading client input (get_client_messages) and syncing back out
    (add_to_broadcast / add_to_client_sync).
  * The server event hooks (core:on_mods_loaded, core:on_player_connect,
    core:tick, core:calculate_client_display, core:on_player_disconnect).
  * Creating and dispatching a mod's OWN custom event hook.
"""

# The engine calls `register(registry)` once, after the mod loader has pushed
# this mod's namespace onto both the Registry and the GameState namespace
# stacks. While `register()` runs (and later, while any of this mod's handlers
# run), EVERY unqualified op/handler name AND state key is automatically
# prefixed with the namespace declared in manifest.json ("example_mod").
#
# So you write `"core:tick"` (contains ":", passes through) for engine hooks,
# and you write `"my_counter"` (no ":") for your own handler/state names —
# the engine turns it into "example_mod:my_counter" for you. You never write
# the prefix yourself.

import time


# --------------------------------------------------------------------------
# A custom event hook owned by this mod.
#
# A mod can create its own hook and dispatch it later. Because it is declared
# unqualified ("my_event") it becomes fully-qualified ("example_mod:my_event")
# automatically. You can add handlers to it, then dispatch it from any handler
# at runtime. Handlers created here are stored in Registry._handlers under the
# resolved name and are invoked inside this mod's namespace, exactly like a
# core hook.
# --------------------------------------------------------------------------
def on_my_event(gamestate, registry):
    """A handler on this mod's own event hook `my_event`.

    Demonstrates that a mod can dispatch its own hook with its own payload,
    and that the handler runs inside this mod's namespace (so unqualified
    keys/names still resolve to "example_mod:<name>" at runtime).
    """
    # gamestate.get with an unqualified key auto-namespaces to
    # ["example_mod:event_count"].
    count = gamestate.get(["event_count"], 0)
    gamestate.set(["event_count"], count + 1)
    print(f"  [example_mod] my_event fired; event_count -> {count + 1}")


# --------------------------------------------------------------------------
# core:on_mods_loaded
#
# Fires ONCE, after every mod's register() has run, before the server accepts
# any connection. This is where you do cross-mod setup or initialize state that
# needs all mods registered first. Handlers run in mod load order, so a mod
# that depends on another runs after its dependency.
# --------------------------------------------------------------------------
def on_mods_loaded(gamestate, registry):
    """Initialize server-side state that should exist from the very start."""
    # `initialize` only sets the value if the key does not already exist — a
    # safe way to seed defaults without clobbering anything.
    gamestate.initialize(["server_started_at"], time.time())
    gamestate.initialize(["event_count"], 0)
    # Create this mod's own event hook (no handler) so it can be dispatched
    # later. Declared unqualified -> "example_mod:my_event".
    registry.register_handler("my_event", None)
    print("  [example_mod] initialized state and created hook 'my_event'")


# --------------------------------------------------------------------------
# core:on_player_connect
#
# Fires after a client finishes loading, before the one-time init is sent.
# This is where you give a newly connected player its starting state and push
# one-time data down to that client (delivered as the client's core:init).
# The current player's name is in ["core:players", "newPlayerName"].
# --------------------------------------------------------------------------
def on_player_connect(gamestate, registry):
    """Seed a new player's per-player state and push a one-time init payload."""
    player = gamestate.get(["core:players", "newPlayerName"])
    if not player:
        return

    # `set` writes (creates intermediate dicts), `initialize` only writes if
    # absent, `exists` checks presence.
    gamestate.initialize(["core:players", player, "example_data"], {"joined_at": time.time(), "score": 0})
    gamestate.initialize(["core:players", player, "username"], player)

    # `add_to_client_sync` contributes to the per-client init payload. The key
    # is auto-namespaced ("example_data" -> "example_mod:example_data"). This
    # arrives on the client inside the one-time core:init payload.
    gamestate.add_to_client_sync("example_data", gamestate.get(["core:players", player, "example_data"]))
    print(f"  [example_mod] initialized per-player state for '{player}'")


# --------------------------------------------------------------------------
# core:tick
#
# Fires every game tick (default 0.05s ≈ 20 ticks/s). This is the main server
# work loop. Here we read whatever the client sent us this tick, fold it into
# server-authoritative state, and broadcast a value to all clients.
# --------------------------------------------------------------------------
def on_tick(gamestate, registry):
    """Read client input this tick and broadcast this mod's rolling counter."""

    # The client send buffer is read without hits to raw core keys. Each entry
    # is a {"playerName": str, "data": dict}. The send-buffer keys the client
    # used are namespaced on its side, e.g. "example_mod:hello_key".
    messages = gamestate.get_client_messages()

    for msg in messages:
        data = msg.get("data", {})
        # The key is fully qualified on the wire (the client namespaced it).
        value = data.get("example_mod:hello_key")
        if value is not None:
            print(f"  [example_mod] received '{value}' from {msg['playerName']}")

    # Keep and broadcast a rolling counter so every client sees the same value.
    count = gamestate.get(["world_count"], 0) + 1
    gamestate.set(["world_count"], count, override=True)

    # `add_to_broadcast` flushes this key/value to every connected client each
    # tick. The key is auto-namespaced ("world_count" -> "example_mod:world_count").
    gamestate.add_to_broadcast("world_count", count)

    # Fire this mod's own hook each tick too, to show custom hooks in action.
    registry.dispatch("my_event", gamestate)


# --------------------------------------------------------------------------
# core:calculate_client_display
#
# Fires once per client per tick. Only the "current" client is being computed;
# its name is in ["core:per_client_sync", "player"]. Push data with
# add_to_client_sync; it is sent to THAT client every tick.
# --------------------------------------------------------------------------
def on_calculate_client_display(gamestate, registry):
    """Send the current client its own copy of this mod's per-player data."""
    player = gamestate.get(["core:per_client_sync", "player"])
    if not player:
        return
    score = gamestate.get(["core:players", player, "example_data", "score"], 0)
    gamestate.add_to_client_sync("score", score)


# --------------------------------------------------------------------------
# core:on_player_disconnect
#
# Fires when a connection closes. The leaving player's name is in
# ["core:players", "disconnectPlayerName"] (cleared after the hook returns).
# --------------------------------------------------------------------------
def on_player_disconnect(gamestate, registry):
    """Clean up a leaving player's per-player state."""
    player = gamestate.get(["core:players", "disconnectPlayerName"])
    if not player:
        return
    # Demonstrate `exists` before doing cleanup.
    if gamestate.exists(["core:players", player, "example_data"]):
        print(f"  [example_mod] cleaning up per-player state for '{player}'")
    # (No need to delete anything here on the server; per-player state is
    #  replaced on next connect. Show that the registry can be queried too.)
    hook = registry.get_handler("my_event")
    if hook:
        print("  [example_mod] 'my_event' hook has registered handlers:", list(hook.keys()))


# --------------------------------------------------------------------------
# register(registry) — the entry point
# --------------------------------------------------------------------------
def register(registry):
    """Subscribe this mod's handlers to the engine's hooks.

    Called once by the loader, with this mod's namespace active. Unqualified
    op/handler names are auto-prefixed with "example_mod:"; "core:..." names
    pass through untouched.
    """
    registry.register_handler("core:on_mods_loaded", on_mods_loaded, "setup-state")
    registry.register_handler("core:on_player_connect", on_player_connect, "seed-player")
    registry.register_handler("core:tick", on_tick, "tick-work")
    registry.register_handler("core:calculate_client_display", on_calculate_client_display, "sync-score")
    registry.register_handler("core:on_player_disconnect", on_player_disconnect, "cleanup-player")
    # This mod's OWN hook. Handlers can be registered on it; the engine also
    # lets you dispatch it later (see register_handler with func=None to only
    # create the hook, and dispatch(name, gamestate) to fire it).
    registry.register_handler("my_event", on_my_event, "handle-my-event")
