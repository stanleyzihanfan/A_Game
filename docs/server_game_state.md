# Server API — `GameState`

The `GameState` (in `server/game_state.py`) is the server's authoritative,
thread-safe, namespaced key-value store. It holds world data, player data, and
runtime values. Server mods receive it as `gameState` (the first argument to
their handlers) and read/write everything through it. It is the same object
created in `server/core.py` as `game_state`.

A `key` is always a **list**, e.g. `["players", "Alice", "pos"]`. The first
element of the list decides the namespace: unqualified first elements are
auto-prefixed with the active mod namespace; first elements containing `:` pass
through untouched.

## Accessors

### `set`

```python
set(key, value, override=False)
```

Set a key-value pair, creating intermediate dicts as needed.

```python
gameState.set(["core:players", "Alice", "pos"], {"x": 0, "y": 0, "z": 0})
gameState.set(["core:players", "Alice", "online"], True, True)  # override
```

| Param | Type | Description |
|---|---|---|
| `key` | `list` | Key path. Unqualified first element auto-namespaced. |
| `value` | `any` | Value to store. |
| `override` | `bool` | If `False`, an existing conflicting leaf raises `KeyError`. If `True`, it is replaced. |

### `get`

```python
get(key, default=None, deepcopy=True)
```

Get a value by key list.

```python
pos = gameState.get(["core:players", "Alice", "pos"])
fallback = gameState.get(["core:players", "Alice", "nonexistent"], default=0)
```

| Param | Type | Description |
|---|---|---|
| `key` | `list` | Key path. |
| `default` | `any` | Returned if the key does not exist. |
| `deepcopy` | `bool` | If `True` (default), returns a **deep copy**. Set `False` only when you hold the lock yourself, so modifications don't escape. Note: `get_client_messages` and the buffer helpers always deep-copy. |

### `exists`

```python
exists(key)
```

Return `True` if the full key path exists.

```python
if gameState.exists(["core:players", "Alice"]):
    ...
```

### `initialize`

```python
initialize(key, value)
```

Set `key` to `value` only if it does not already exist. Handy for defaults.

```python
gameState.initialize(["core:players", "Alice", "speed"], 8)
```

## Namespace helpers

| Method | Description |
|---|---|
| `push_namespace(namespace)` | Push a namespace (used by the loader around `register()` and by `dispatch()` around each handler). |
| `pop_namespace()` | Pop the top namespace. |
| `current_namespace()` | Return the top namespace or `None`. |

## Send / receive buffer helpers

These wrap the core sync buffers so mods never have to touch raw `"core:*"`
keys. Only the **message key** (a string, not a key list) is auto-namespaced
with the active mod namespace.

### `add_to_broadcast`

```python
add_to_broadcast(key, value)
```

Add a key-value pair to the **global broadcast** buffer. The buffer is flushed
to every connected client once per tick.

```python
gameState.add_to_broadcast("greeting", "Hello from the server!")
# key namespaced to "<namespace>:greeting"
```

| Param | Type | Description |
|---|---|---|
| `key` | `str` | Unqualified key; auto-prefixed with the mod namespace. |
| `value` | `any` | Value sent to every client. |

### `add_to_client_sync`

```python
add_to_client_sync(key, value)
```

Add a key-value pair to the **per-client sync** payload. The payload is set up
by core before two hooks: `core:calculate_client_display` (computed per player
each tick) and `core:on_player_connect` (delivered to the just-connected client
as a one-time init message).

```python
gameState.add_to_client_sync("pos", current_pos)
```

| Param | Type | Description |
|---|---|---|
| `key` | `str` | Unqualified key; auto-prefixed. |
| `value` | `any` | Value to include in the payload for whichever client is being handled. |

> Use this inside a handler for `core:on_player_connect` or
> `core:calculate_client_display`. It targets the "current" client — the one
> named in `["core:per_client_sync", "player"]`.

### `get_client_messages`

```python
get_client_messages(playerName=None)
```

Collect the messages a client sent this tick.

```python
for entry in gameState.get_client_messages():
    name = entry["playerName"]
    payload = entry["data"]
```

| Param | Type | Description |
|---|---|---|
| `playerName` | `str, optional` | If given, only that player's entries are returned. If `None`, return every player's entries. |

**Return**: a list of `{"playerName": str, "data": dict}` deep copies. Each
entry is one `sync_with_server` message that arrived since the last tick. The
`data` dict uses the **client-side namespaced** keys — e.g. the
`player_position` mod reads `data.get(f"{ns}:movement_handler")`.

## Concurrency

`GameState` uses a `threading.RLock`, and every accessor acquires it internally.
Mod handlers are already called under `game_state._lock` by `dispatch()` in
`core.py`, so you do **not** need to lock yourself. The `_lock` attribute is
partial-internal (used by `core.py` and `dispatch()`); you normally should not
touch it directly.

## Key conventions

- **Core state** is always explicitly qualified: `["core:players", ...]`,
  `["core:tickRate"]`, `["core:global_broadcast"]`, etc.
- **Mod state** is written unqualified and auto-prefixed. To share across mods,
  write another mod's key explicitly (allowed, not policed).
- Buffer locations live under fixed core keys (`core:global_broadcast`,
  `core:client_receive_buffer`, `core:per_client_sync`) — do not read/write
  those directly; use the buffer helpers.

## Example

```python
def on_tick(gameState, registry):
    for entry in gameState.get_client_messages():
        name = entry["playerName"]
        ns = registry.current_namespace()
        move = entry["data"].get(f"{ns}:movement_handler")
        if move is None:
            continue
        # ... integrate movement ...
        pos = gameState.get(["core:players", name, "pos"])
        pos["x"] += move["dx"]
        gameState.set(["core:players", name, "pos"], pos)
```

See `mods/player_position/main.py` for the full version.

## Source

`server/game_state.py`
