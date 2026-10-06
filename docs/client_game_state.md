# Client API — `GameState`

The client-side `GameState` (in `client/scripts/game_state.js`) mirrors the
server's `GameState` so mod logic stays consistent on both ends. It is a
namespaced key-value store. Client mod code reaches it as the global
`gameState`.

As on the server, a `key` is an **array** (e.g. `["core:playerData", "yaw"]`),
and unqualified first elements are auto-prefixed with the active namespace.

> Unlike the server store, the client store is **not** authoritative and not
> shared across processes — it is the browser-side copy. The `get()` method
> returns a JSON deep copy (no `deepcopy` flag, no separate lock).

## Accessors

### `set`

```javascript
set(key, value, override = false)
```

```javascript
gameState.set(["core:playerData", "yaw"], 0, true);
```

### `get`

```javascript
get(key, defaultVal = null)
```

```javascript
const yaw = gameState.get(["core:playerData", "yaw"], 0);
```

Returns a JSON deep copy. Returns `defaultVal` if the key doesn't exist.

### `exists`

```javascript
exists(key)
```

```javascript
if (gameState.exists(["core:initialized"])) { ... }
```

### `initialize`

```javascript
initialize(key, value)
```

Set only if the key doesn't already exist.

### `isKeyDown`

```javascript
isKeyDown(code)
```

Convenience wrapper for reading key state.

```javascript
const moving = gameState.isKeyDown("KeyW");
```

Returns `gameState.get(["core:keys", code], false)`. The key/up handlers in
`main.js` write `["core:keys", e.code]`.

## Send / receive buffer helpers

These wrap the core sync buffers. Only the **message key** (a string) is
auto-namespaced.

### `addToSendBuffer`

```javascript
addToSendBuffer(key, value)
```

Add a key-value pair to this tick's send buffer, which is sent to the server
once per tick and then cleared.

```javascript
gameState.addToSendBuffer("movement_handler", moveState); // -> "<namespace>:movement_handler"
```

| Param | Type | Description |
|---|---|---|
| `key` | `string` | Unqualified key; auto-prefixed with the active namespace. |
| `value` | `*` | Value to send. |

### `readServerMessages`

```javascript
readServerMessages(key = null)
```

Read this mod's messages from the server receive buffer for the current tick.

```javascript
// All messages whose key starts with this mod's namespace:
const all = gameState.readServerMessages();
// Only messages for a specific namespaced key:
const positions = gameState.readServerMessages("pos");
```

| Param | Type | Description |
|---|---|---|
| `key` | `string, optional` | Unqualified key to filter on. If `null`, returns every message whose key starts with this mod's namespace. |

**Return**: 
- With `key`: an array of the values for that key (e.g. position objects).
- With `key = null`: an array of `{ namespacedKey: value }` objects.

This mirrors the server's `get_client_messages` but the other direction.

## Internal helpers

`_rawGet` / `_rawSet` bypass namespace resolution entirely and are used by the
buffer helpers to always hit the core buffer locations. You should not need to
call them directly. `_resolveSingle` resolves a single string key.

## Sync flow (client side)

- Each client tick (`core:tick` handler), a mod reads input and pushes data via
  `addToSendBuffer`. `main.js` sends the whole send buffer to the server as a
  `sync_with_server` message and clears it.
- The server replies with `core:sync_with_client` messages; `initialization.js`
  pushes each message's `data` into `["core:server_receive_buffer"]`, then
  dispatches `core:tick` (and, once, `core:init`). Mods read those messages in
  their `core:tick` handler with `readServerMessages`.

## Example

```javascript
function updatePlayerMoveData(gameState) {
    const move = {
        yaw:   gameState.get(["core:playerData", "yaw"]),
        pitch: gameState.get(["core:playerData", "pitch"]),
        forward: gameState.isKeyDown("KeyW"),
        back:    gameState.isKeyDown("KeyS"),
        left:    gameState.isKeyDown("KeyA"),
        right:   gameState.isKeyDown("KeyD"),
        up:      gameState.isKeyDown("Space"),
        down:    gameState.isKeyDown("ShiftLeft"),
        speed:   gameState.get(["core:playerData", "speed"]),
    };
    gameState.addToSendBuffer("movement_handler", move);
}
wsRegistry.register_handler("core:tick", updatePlayerMoveData, "updatePlayerMoveData");
```

See `mods/player_position/client.js` for the full bidirectional example.

## Source

`client/scripts/game_state.js`
