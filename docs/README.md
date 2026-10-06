# A-Game Modding API Reference

This is the reference for everything a mod can access in A-Game. A mod is a
folder under `mods/` that the backend auto-discovers and loads at server start.
It can contribute server-side logic (Python), client-side logic (JavaScript),
or both.

> The easiest way to get started is to read a real mod. Two are small and fully
> commented: `mods/connect_guard` (server-only) and `mods/ui_demo`
> (client-only). `mods/player_position` does both sides and shows how the two
> halves talk to each other.

## Table of contents

| Topic | File |
|---|---|
| Concepts, lifecycle, and the namespacing rule | [Concepts](concepts.md) |
| The `manifest.json` schema | [Manifest](manifest.md) |
| Server API — `Registry` (Python) | [Server: Registry](server_registry.md) |
| Server API — `GameState` (Python) | [Server: GameState](server_game_state.md) |
| Client API — `wsRegistry` (JavaScript) | [Client: wsRegistry](client_ws_registry.md) |
| Client API — `GameState` (JavaScript) | [Client: GameState](client_game_state.md) |
| Client API — `uiRegistry` (JavaScript) | [Client: uiRegistry](client_ui_registry.md) |
| Event hooks (server & client) | [Event hooks](hooks.md) |
| Wire protocol (server ↔ client messages) | [Wire protocol](wire_protocol.md) |

## A 30-second summary

Every mod declares a **namespace** (defaults to its `modID`) in its
`manifest.json`. While a mod's code is loaded and while any of its handlers run,
that namespace is pushed onto a stack, so any **unqualified** name — an op name,
a handler name, a game-state key, or a UI name — is automatically prefixed:
`"movement_handler"` becomes `"player_position:movement_handler"`.

This means a mod never writes its own prefix and never collides with another
mod. Anything already containing `:` (e.g. `"core:tick"`) passes through
untouched; core hooks and core state keys are always explicitly qualified.

- **Server mods** expose `def register(registry):` and use
  [`registry.register_handler(...)`](server_registry.md#register_handler) to
  subscribe to hooks, plus [`registry.dispatch(...)`](server_registry.md#dispatch)
  to fire their own. They read/write world and player data through
  [`gameState`](server_game_state.md).
- **Client mods** are a JS file that is `eval()`ed during the WebSocket
  handshake. They use the same pattern against
  [`wsRegistry`](client_ws_registry.md), [`gameState`](client_game_state.md),
  and [`uiRegistry`](client_ui_registry.md), and can access the Three.js
  objects (`scene`, `renderer`, `camera`, `voxelGeo`, …) that the
  `scene_setup` mod exposes on `window`.

## Reading the method signatures

This project deliberately keeps its own naming conventions, so a few symbols
appear slightly differently on each side. Here is the correspondence:

| Server (Python) | Client (JavaScript) |
|---|---|
| `registry.register_handler(op, func, name)` | `wsRegistry.register_handler(op, func, name)` |
| `registry.dispatch(op, gameState)` | `wsRegistry.dispatch(op, gameState)` |
| `registry.current_namespace()` | `wsRegistry.currentNamespace()` |
| `gameState.set(key, value, override)` | `gameState.set(key, value, override)` |
| `gameState.get(key, default, deepcopy)` | `gameState.get(key, defaultVal)` |
| `gameState.add_to_broadcast(key, value)` | `gameState.addToSendBuffer(key, value)` |
| `gameState.get_client_messages(playerName)` | `gameState.readServerMessages(key)` |

## Source of truth

This reference is generated from the code in this repository. The authoritative
implementations live in:

- `server/ws_registry.py` — Python `Registry`
- `server/game_state.py` — Python `GameState`
- `server/core.py` — server tick loop, handshake, and hook dispatch points
- `server/mod_loader.py` — load order, namespace push/pop, `register()` call
- `client/scripts/client_ws_registry.js` — JS `Registry` (`wsRegistry`)
- `client/scripts/game_state.js` — JS `GameState`
- `client/scripts/ui.js` — JS `UIRegistry` (`uiRegistry`)
- `client/scripts/initialization.js` — client bootstrap and hook dispatch points
