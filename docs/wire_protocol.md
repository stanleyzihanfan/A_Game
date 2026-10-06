# Wire Protocol

This describes the messages sent over the game WebSocket (`/server`). All
messages are [msgpack](https://msgpack.org) encoded as objects of the form:

```js
{ "op": "...", "params": [...] }
```

- `op` is the operation name (always explicitly qualified, e.g. `"core:..."`).
- `params` is the payload — typically an array. For sync messages the payload is
  a single object: `{"op": "core:sync_with_client", "data": {...}}`.

The server helpers `encode`/`decode` wrap the msgpack library
(`server/core.py`). The client uses `msgpack-lite` (`encode`/`msgpack.decode`).

## Handshake sequence

A new connection goes through a fixed order. A mod's `client.js` is streamed
during this handshake, before the game loop starts.

| Step | From | Message | Notes |
|---|---|---|---|
| 1 | server → client | `{"op": "init"}` | Request client init. |
| 2 | client → server | `{"op": "init", "playerName": "...", "psw": "..."}` | Player data. |
| 3 | server | dispatches `core:on_player_connect_request` | Connect-guard decision; may reject. |
| 4 | server → client | `{"op": "load_mod_js", "params": [modID, src, namespace]}` (one per mod) | Stream each mod's client.js. |
| 5 | server → client | `{"op": "mods_ready", "params": []}` | All mod scripts sent. |
| 6 | server → client | `{"op": "core:sync_with_client", "data": {...}}` | One-time init payload for the connecting client (filled by `core:on_player_connect` handlers). |
| 7 | client → server | `{"op": "client_init_done", "params": []}` | Client finished loading. |

## Messages

### `core:sync_with_server` (client → server)

The client sends its accumulated send buffer once per tick.

```js
{ "op": "sync_with_server", "params": { "<namespacedKey>": value, ... } }
```

- `params` is the send-buffer object. Keys are namespaced (`addToSendBuffer`
  prefixes them with the mod namespace).
- The server appends `{"playerName": name, "data": params}` to
  `["core:client_receive_buffer"]`. Mods read it with
  `gameState.get_client_messages()`.

### `core:sync_with_client` (server → client)

The server sends display / sync data to a client. Used both for the one-time
init and for per-tick per-client display data.

```js
{ "op": "core:sync_with_client", "data": { "<namespacedKey>": value, ... } }
```

- On the client it is pushed into `["core:server_receive_buffer"]` as a list of
  these `data` objects. Mods read them with `gameState.readServerMessages()`.
- The 6th handshake message of the same op carries the one-time init payload and
  also triggers `core:init`.

### Server → client (handshake control)

| op | Purpose |
|---|---|
| `init` | Kick off the handshake (step 1). |
| `load_mod_js` (`params: [modID, src, namespace]`) | Stream a mod's client.js to the client and set the namespace while it `eval()`s. |
| `mods_ready` (`params: []`) | All mod scripts have been sent. |

### Client → server (handshake control)

| op | Purpose |
|---|---|
| `init` | Send player name + password (step 2). |
| `client_init_done` (`params: []`) | Client finished loading (step 7). |

## Notes for mods

- You usually don't speak the raw protocol. On the **server**, use
  [`add_to_broadcast`](server_game_state.md#add_to_broadcast) /
  [`add_to_client_sync`](server_game_state.md#add_to_client_sync) to
  produce `core:sync_with_client` messages, and
  [`get_client_messages`](server_game_state.md#get_client_messages)
  to consume `core:sync_with_server`.
- On the **client**, use
  [`addToSendBuffer`](client_game_state.md#addtosendbuffer) to produce
  `sync_with_server`, and
  [`readServerMessages`](client_game_state.md#readservermessages) to
  consume `sync_with_client`.
- A raw message whose op is neither a known core op nor a registered mod hook is
  ignored (or logged) by whichever side receives it.
