# Server-client communication mod — backend handlers

# -- Handler functions ---------------------------------------------------------

def log(params):
    # Print each param space-separated, first param has no leading space
    for i in range(len(params)):
        if i == 0:
            print(params[i], end='')
        else:
            print(params[i], end=' ')
    print()

def warn(params):
    for i in range(len(params)):
        if i == 0:
            print("\033[33m" + params[i] + "\033[0m", end='')
        else:
            print("\033[33m" + params[i] + "\033[0m", end=' ')
    print()

def error(params):
    for i in range(len(params)):
        if i == 0:
            print("\x1b[38;2;255;0;0m" + params[i] + "\033[0m", end='')
        else:
            print("\x1b[38;2;255;0;0m" + params[i] + "\033[0m", end=' ')
    print()

# -- Mod entry point -----------------------------------------------------------
# Called by mod_loader.py — registers all base game ops with the central registry

def register(registry):
    registry.register_handler("client_communication:log", log)
    registry.register_handler("client_communication:warn", warn)
    registry.register_handler("client_communication:error", error)