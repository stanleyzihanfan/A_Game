from server.game_state import GameState
from server.ws_registry import Registry
# Server-client communication mod — backend handlers

# -- Handler functions ---------------------------------------------------------

def log(gameState:GameState,registry:Registry):
    
    data=gameState.get(["client_receive","client:log"])
    if data==None:
        return
    # Print each param space-separated, first param has no leading space
    for i in range(len(data)):
        if i == 0:
            print(data[i], end='')
        else:
            print(data[i], end=' ')
    print()

def warn(gameState:GameState,registry:Registry):
    data=gameState.get(["client_receive","client:warn"])
    if data==None:
        return
    for i in range(len(data)):
        if i == 0:
            print("\033[33m" + data[i] + "\033[0m", end='')
        else:
            print("\033[33m" + data[i] + "\033[0m", end=' ')
    print()

def error(gameState:GameState,registry:Registry):
    data=gameState.get(["client_receive","client:error"])
    if data==None:
        return
    for i in range(len(data)):
        if i == 0:
            print("\x1b[38;2;255;0;0m" + data[i] + "\033[0m", end='')
        else:
            print("\x1b[38;2;255;0;0m" + data[i] + "\033[0m", end=' ')
    print()


def process_client_hook_handler(gameState:GameState,registry:Registry):
    with gameState._lock:
        gameState.set(["client_receive"],gameState.get(["client_receive_buffer"]))
        gameState.set(["client_receive_buffer"],{})
        registry.dispatch("client_communication:process_client_hook",gameState)

# -- Mod entry point -----------------------------------------------------------
# Called by mod_loader.py — registers all base game ops with the central registry

def register(registry:Registry):
    registry.register_handler("client_communication:process_client_hook", log, "client_communication:log")
    registry.register_handler("client_communication:process_client_hook", warn, "client_communication:warn")
    registry.register_handler("client_communication:process_client_hook", error, "client_communication:error")
    registry.register_handler("main:tick_hook", process_client_hook_handler, "client_communication:process_client_hook_handler")