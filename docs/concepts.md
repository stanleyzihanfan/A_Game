# Concepts

This page explains the model every mod follows: the mod lifecycle, how the
needed namespace machinery works, and where code runs. Understanding this makes
the rest of the reference much easier to read.

## 1. What a mod is

A mod is a folder under `mods/` containing a `manifest.json`. The loader
(`server/mod_loader.py`) scans the directory, reads each manifest, and loads
the mod in alphabetical order by `modID`. Each mod may contribute:

- **Backend logic** — a Python file (default `main.py`) that exposes
  `def register(registry)`. Runs on the **server**.
- **Client logic** — a JavaScript file (`client.js`) that is `eval()`ed inside
  the browser during the WebSocket handshake. Runs on the **client**.

Either half is optional. A mod with only `backend_py` is server-side only; a mod
with only `client_js` is client-side only.

## 2. The mod lifecycle

### Server side

1. The mod loader discovers the mod from its `manifest.json`.
2. It pushes the mod's namespace onto the **registry** (and the **game state**)
   namespace stacks.
3. It imports the mod's Python module and calls `module.register(registry)`.
4. Inside `register()`, every unqualified op, handler name, and state key is
   auto-prefixed with the mod's namespace.
5. After `register()` returns, the namespace is popped. The handlers it
   registered **remember** the namespace they were registered under, and
   `dispatch()` re-enters it when they later run — so their own unqualified
   names still resolve correctly at runtime.
6. If `register()` raises, the loader re-raises (it does not silently swallow a
   broken mod), but the namespace stack is always restored.

### Client side

1. During the handshake, the server sends each loaded mod's `client.js` as a
   `load_mod_js` message, together with the mod's `modID` and namespace.
2. The client pushes the namespace onto `wsRegistry`, `gameState`, and
   `uiRegistry`.
3. It `eval()`s the script.
4. After `eval()`, all three namespaces are popped.

Because client scripts are `eval()`ed (not `import`ed), **top-level `const` /
`let` are not visible to other scripts**. Anything another mod needs — the
Three.js scene, renderer, camera, geometry, materials — must be attached to
`window` (see `mods/scene_setup/client.js`).

## 3. Namespacing

This is the single most important rule. Every object that accepts a name or a
key prefixes **unqualified** inputs with the currently active namespace.

An input is **unqualified** if it contains no `:`.

| Input | Active namespace | Result |
|---|---|---|
| `"syncBlocks"` | `testmod` | `"testmod:syncBlocks"` |
| `"movement_handler"` | `player_position` | `"player_position:movement_handler"` |
| `["pos"]` | `player_position` | `["player_position:pos"]` |
| `"core:tick"` | anything | `"core:tick"` (contains `:`, untouched) |
| `["core:players", "Alice", "pos"]` | anything | unchanged (contains `:`) |

Rules to remember:

- **You never write your own prefix.** Write `"syncBlocks"`, not
  `"mymod:syncBlocks"`. The machinery adds it.
- **Core hooks and core state keys are always explicitly qualified.** You write
  `"core:tick"` and it passes through untouched. This is how you subscribe
  to engine hooks.
- **If a name is unqualified and no namespace is active, it is an error.** This
  happens if you try to use an unqualified name at runtime (outside mod
  loading / outside a dispatched handler). For that reason, use the **bound
  handle** and **bound event** helpers in the UI registry when working at
  runtime (see [Client: uiRegistry](client_ui_registry.md#createview)).
- **Cross-namespace references are allowed but not policed.** You *may* write
  `"othermod:something"`; the registry does not stop you. Only unqualified
  names get auto-prefixed.

## 4. Where code runs

| Concern | Server (`server/`) | Client (`client/`) |
|---|---|---|
| API objects | `registry` (`Registry`), `game_state` (`GameState`) | `wsRegistry` (`Registry`), `gameState` (`GameState`), `uiRegistry` (`UIRegistry`) |
| Entry point | `def register(registry)` in the mod's `main.py` | top-level code in `client.js` |
| World state | authoritative, in `game_state` | soft copy, in `gameState` |
| Input | reads the client-receive buffer | reads keyboard/mouse, writes to the send buffer |
| Sync out | `add_to_broadcast`, `add_to_client_sync` | `addToSendBuffer` |
| Sync in | `get_client_messages` | `readServerMessages` |

The server is **authoritative**. A client mod can read shared state and send
input, but the server decides what is true and broadcasts it back.

## 5. Ticks

The server runs a fixed-timestep tick loop (default `0.05`s ≈ 20 ticks/s, see
`server/core.py`). The client runs its own fixed-timestep loop (also `1/20`) and
a render loop via `requestAnimationFrame`. Each tick:

- Server: dispatch `core:tick`, flush the global broadcast buffer, then
  compute and send per-client display data, then clear the receive buffer.
- Client: dispatch `core:tick`, then send the accumulated send buffer, then
  clear the receive buffer.

A mod's per-tick work goes in a `core:tick` (server) or `core:tick`
(client) handler.
