# Example Mod

`mods/example_mod/` is a complete, self-contained walkthrough of the modding
API. It runs against a bare engine (no game content) because every handler is
**defensive** — it never assumes a scene, camera, or player exists. Copy the
folder, rename it, and edit the manifest to start a new mod.

## What it demonstrates

### Server — `main.py`

- **`register(registry)`** — the entry point the loader calls once, inside this
  mod's namespace.
- **`Registry`** — `register_handler`, `dispatch`, `get_handler`, and a mod-owned
  custom event hook.
- **`GameState`** — `get`, `set`, `initialize`, `exists`.
- **Client input / sync** — `get_client_messages` (read what clients sent this
  tick), `add_to_broadcast` (broadcast to every client), `add_to_client_sync`
  (send per-client data).
- **Server hooks** — `core:on_mods_loaded`, `core:on_player_connect`,
  `core:tick`, `core:calculate_client_display`, `core:on_player_disconnect`.

### Client — `client.js`

- **`wsRegistry`** — handlers on `core:init`, `core:tick`, `core:update_camera`,
  `core:on_disconnect`, and a custom hook.
- **`gameState`** — `get` / `set`, `isKeyDown`, `addToSendBuffer` (out),
  `readServerMessages` (in).
- **`uiRegistry`** — `createView` + bound handle, `bindEvent`, `register_style`.

## Namespacing reminder

Throughout the example, notice the difference between:

- **Engine hooks and core state** — always written fully qualified
  (`"core:tick"`, `["core:playerData", ...]`), so they pass through untouched.
- **This mod's own names** — always written *unqualified* (`"my_event"`,
  `"hud"`, `"world_count"`), and the engine auto-prefixes them with the
  namespace from `manifest.json` (`"example_mod"`).

You never write the prefix yourself. See
[Concepts](concepts.md#3-namespacing) for the full rule.
