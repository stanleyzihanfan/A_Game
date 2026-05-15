import os, json, importlib.util

# -- Mod Loader ----------------------------------------------------------------
# Scans the /mods directory, reads each manifest.json, and loads each mod's
# backend_py in order, calling register(registry) on each one.

# Absolute path to /mods folder at project root
MODS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mods")

def _load_order(manifests):
    """
    Returns mod folders in load order.
    Phase 2: alphabetical only.
    Phase 5: will topologically sort by dependencies field.
    """
    return sorted(manifests.keys())

def load_mods(registry):
    """
    Scans MODS_DIR, loads each valid mod, and calls register(registry) on its backend module.
    Returns a list of loaded manifest dicts (for use by core.py to know which client.js to serve).
    """
    if not os.path.isdir(MODS_DIR):
        print("No mods directory found, skipping mod loading")
        return []

    # -- Discover mods ---------------------------------------------------------
    # Read all manifests first so load order can be determined before any imports
    manifests = {}
    for mod_folder in os.listdir(MODS_DIR):
        mod_path = os.path.join(MODS_DIR, mod_folder)
        if not os.path.isdir(mod_path):
            continue
        manifest_path = os.path.join(mod_path, "manifest.json")
        if not os.path.isfile(manifest_path):
            print(f"\x1b[33mMod folder '{mod_folder}' has no manifest.json, skipping\033[0m")
            continue
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        manifest["_mod_path"] = mod_path  # stash path for later use
        manifests[manifest["modID"]] = manifest

    # -- Load in order ---------------------------------------------------------
    loaded = []
    for modID in _load_order(manifests):
        manifest = manifests[modID]
        mod_path = manifest["_mod_path"]
        backend_py = manifest.get("backend_py")
        # with open(manifest_path, "r") as f:
        #     manifest = json.load(f)
        # print(f"  DEBUG manifest keys: {list(manifest.keys())}")
        # print(f"  DEBUG backend_py value: {repr(manifest.get('backend_py'))}")

        print(f"Loading mod: {manifest['name']} v{manifest['version']} ({modID})")

        # backend_py is nullable — frontend-only mods skip this
        if backend_py:
            py_path = os.path.join(mod_path, backend_py)
            if not os.path.isfile(py_path):
                print(f"\x1b[33m  main.py '{backend_py}' not found for mod '{modID}', skipping\033[0m")
                continue
            # Dynamically import the mod's main.py without polluting sys.modules
            # with a generic name — use modID as the module name
            spec = importlib.util.spec_from_file_location(f"mod_{modID}", py_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Every backend mod must expose a register(registry) function
            if not hasattr(module, "register"):
                print(f"\x1b[33m  Mod '{modID}' has no register() function, skipping\033[0m")
                continue
            module.register(registry)
            print(f"  Backend registered: {backend_py}")
        else:
            print(f"\x1b[33m  main.py '{backend_py}' not registered in registry for mod '{modID}', skipping\033[0m")

        loaded.append(manifest)
        print(f"  Loaded OK")

    print(f"Mod loading complete: {len(loaded)} mod(s) loaded")
    return loaded