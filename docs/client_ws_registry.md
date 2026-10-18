# Client API — `wsRegistry`

`wsRegistry` is the client-side handler registry (`Registry` in
`client/scripts/client_ws_registry.js`). It mirrors the server's `Registry` so
client mod code uses the same shape. Client mod code reaches it as the global
`wsRegistry`.

A client mod's `client.js` is `eval()`ed during the handshake (see
`client/scripts/initialization.js`). While it is eval()ed, the namespace is
active, so unqualified op/handler names auto-prefix.

## `register_handler`

```javascript
register_handler(op, func = null, name = null)
```

Register a handler on an event hook.

```javascript
wsRegistry.register_handler("core:tick", updatePlayerMoveData, "updatePlayerMoveData");
wsRegistry.register_handler("core:update_camera", updateCameraRotation, "updateCameraRotation");
```

| Param | Type | Description |
|---|---|---|
| `op` | `string` | Event hook name. Unqualified names auto-prefix with namespace; `"core:..."` passes through. |
| `func` | `Function` | Handler, called as `func(gameState, wsRegistry)` on dispatch. If `null`, only the hook is created. |
| `name` | `string, optional` | Handler name. If omitted, a `_lambda_<n>` name is generated. |

- If the hook doesn't exist, it's created.
- Duplicate handler names overwrite (with a console warning).
- The handler captures the active namespace for later re-entry.

## `dispatch`

```javascript
dispatch(op, gameState)
```

Run every handler under `op`, each inside its captured namespace.

```javascript
wsRegistry.dispatch("core:tick", gameState);
```

| Param | Type | Description |
|---|---|---|
| `op` | `string` | Hook to dispatch. Not auto-namespaced. |
| `gameState` | `GameState` | Passed to each handler; also gets its namespace pushed/popped. |

Handlers are called `func(gameState, wsRegistry)`. If one throws, it is logged
and re-thrown (with `e.handled = true`), and the namespace is restored.

## `get_handler`

```javascript
get_handler(op, name = null)
```

Look up a handler record or a whole hook.

```javascript
const rec = wsRegistry.get_handler("core:tick", "updatePlayerMoveData"); // {func, namespace}
const hook = wsRegistry.get_handler("core:tick");                          // {name: record}
```

- With `name`: returns `{func, namespace}` or `null`.
- Without `name`: returns the hook object or `null`.

## `currentNamespace()`

Return the active namespace or `null`.

```javascript
const ns = wsRegistry.currentNamespace();
```

## Namespace helpers

| Method | Description |
|---|---|
| `pushNamespace(namespace)` | Push a namespace. |
| `popNamespace()` | Pop the top namespace. |
| `currentNamespace()` | Return the top namespace or `null`. |

## Pre-seeded hooks

The client `Registry` is seeded with these hooks in its constructor
(`this._handlers`):

- `"core:tick"`
- `"core:keydown"`
- `"core:keyup"`

Core dispatches these from `main.js` (keydown/keyup) and the render loop
(`core:tick`, `core:update_camera`). The server dispatches the same `core:tick`
hook for per-tick work, so both sides use the same hook name.

## Example

```javascript
// Runs every client tick.
wsRegistry.register_handler("core:tick", function (gameState) {
    const move = {
        yaw:   gameState.get(["core:playerData", "yaw"]),
        pitch: gameState.get(["core:playerData", "pitch"]),
        forward: gameState.isKeyDown("KeyW"),
        // ...
    };
    gameState.addToSendBuffer("movement_handler", move);
}, "updatePlayerMoveData");
```

See `mods/player_position/client.js` and `mods/ui_demo/client.js` for real uses
(including the client disconnect hook `core:on_disconnect`).

## Source

`client/scripts/client_ws_registry.js`
