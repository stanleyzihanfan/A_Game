# Event Hooks

Hooks are the events a mod can subscribe to. A mod registers a handler on a hook
with `register_handler` (server `Registry`) or `register_handler` (client
`wsRegistry`), and the engine calls it when the event happens. Hook names are
always explicitly qualified (`"core:..."`) because the engine that dispatches
them is core code.

A handler always receives the same first two arguments on the server
(`gameState`, `registry`) or first argument on the client (`gameState`), then
whatever extras the hook provides.

## Server hooks

These are dispatched by `server/core.py` and `server/ws_registry.py`. Each
handler is called as `func(gameState, registry)`.

| Hook | When it fires | Purpose / notes |
|---|---|---|
| `core:tick` | Every game tick (default 0.05s). | Per-tick server logic: process input, integrate world/player state. This is the main server work loop. |
| `core:on_player_connect_request` | During the handshake, *before* the WebSocket is accepted. | The **connect-guard** decision point. The engine sets `["core:connect_request"]` with `playerName`, `psw`, `approved`, `reason`, `code`; your handler validates and writes back the decision. Core performs the actual `ws.close()` if `approved` is `False`. |
| `core:on_player_connect` | After the client finishes loading (`client_init_done` received), before the one-time init is sent. | Initialize a new player's state and push one-time data via `add_to_client_sync` (delivered as the client's `core:init`). |
| `core:calculate_client_display` | Once per client per tick. | Compute per-client display data. The "current client" is `["core:per_client_sync", "player"]`; push data with `add_to_client_sync`. |
| `core:on_player_disconnect` | When a connection closes (in the `finally` cleanup). | Run cleanup for a leaving player. The engine sets `["core:players", "disconnectPlayerName"]` before dispatching, then clears it after. |

### Hook argument details

**`core:on_player_connect_request`**
The engine builds this context under `["core:connect_request"]` before
dispatching:

| Key | Type | Description |
|---|---|---|
| `playerName` | `str` | The connecting player's name. |
| `psw` | `str` | The password supplied in the `init` message. |
| `approved` | `bool\|None` | Your handler sets this. `None` (unset) means "accept" (no guard mod), `True` accept, `False` reject. |
| `reason` | `str\|None` | Human-readable rejection reason (used by core for logging). |
| `code` | `int\|None` | WebSocket close code used on rejection (defaults to `1002` if unset). |

Write your decision back with `gameState.set(["core:connect_request"], request)`.

**`core:on_player_connect` / `core:calculate_client_display`**
Use `gameState.add_to_client_sync(key, value)` to contribute data. In the
connect case it's delivered as a one-time `core:init`; in the display case it's
sent every tick.

**`core:on_player_disconnect`**
Read `["core:players", "disconnectPlayerName"]` to know who left. The entry is
cleared after the hook returns.

## Client hooks

These are dispatched in `client/scripts/main.js` and
`client/scripts/initialization.js`. Each handler is called as
`func(gameState, wsRegistry)`.

| Hook | When it fires | Purpose / notes |
|---|---|---|
| `core:tick` | Every client tick (fixed `1/20`). | Per-tick client logic: collect input, read server messages, update the scene. Dispatched only after `["core:initialized"]` is true. |
| `core:init` | Once, on the first `core:sync_with_client` message after `mods_ready`. | Apply the one-time init payload from the server (e.g. detect initial player position/look). |
| `core:update_camera` | Every render frame (`requestAnimationFrame`), in the render loop. | Apply camera transform. Dispatched by `main.js` right before `renderer.render(...)`. |
| `core:keydown` | On a key press, when the game screen is focused. | Handle gameplay key-down. `gameState` already has `["core:keys", e.code]` set. |
| `core:keyup` | On a key release, when the game screen is focused. | Handle gameplay key-up. |
| `core:on_disconnect` | When the game socket closes. | Client-side cleanup (mirrors the server `core:on_player_disconnect`). The engine sets `["core:disconnect"]` with `{code, reason, wasClean}` first. If the socket never fully opened, no handlers may be registered yet — `dispatch()` is then a no-op. |

### Client hook argument details

**`core:tick`** — called with `(gameState)`. Read server messages with
`gameState.readServerMessages()`, push input with `gameState.addToSendBuffer()`.

**`core:keydown` / `core:keyup`** — called with `(gameState)`. `gameState` has
`["core:keys", e.code]` set to `true`/`false` before the hook fires.

**`core:on_disconnect`** — read `gameState.get(["core:disconnect"])` for the
close code/reason/clean-flag. Note the engine dispatches this through
`wsRegistry` which also re-enters `uiRegistry`'s namespace, so unqualified UI
names resolve.

## Registering on a hook

### Server (Python)

```python
def on_tick(gameState, registry):
    ...

def register(registry):
    registry.register_handler("core:tick", on_tick, "my-tick-handler")
```

### Client (JavaScript)

```javascript
function onTick(gameState) {
    ...
}
wsRegistry.register_handler("core:tick", onTick, "my-tick-handler");
```

## Custom hooks (owned by a mod)

A mod can also create and dispatch its **own** hooks.

**Server:**
```python
# Declare the hook (no handler) or add a handler:
registry.register_handler("core:my_mod_event", None)

# Later, fire it:
registry.dispatch("core:my_mod_event", game_state)
```

**Client:**
```javascript
wsRegistry.register_handler("core:my_event", handler, "my-handler");
// ...
wsRegistry.dispatch("core:my_event", gameState);
```

Because names are auto-prefixed, a mod's own hook can also be declared
unqualified (it becomes `<namespace>:<name>`). Since you're already inside your
mod's namespace when you declare it, prefer the unqualified form for your own
private hooks and the `core:` qualified form only when you want to hook into the
engine.
