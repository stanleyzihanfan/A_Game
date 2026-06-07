# Central WebSocket op handler registry
# Replaces the wsDispatch dict in the original backend.py
# Mods call register_handler() to add their own ops
class Registry:
    def __init__(self):
        # op_name -> handler function
        self._handlers = {}

    def register_handler(self, op: str, func, name:str = None):
        handlerName=name or func.__name__
        if not op in self._handlers:
            self._handlers[op]={}
            print(f"  Event Hook {op} created.")
        if handlerName=='<lambda>':
            handlerName=f"_lambda_{id(func)}"
        if handlerName in self._handlers:
            print(f"\033[33m  [WARN] Handler {handlerName} already registered under {op}, overwriting!\033[0m")
        self._handlers[op][handlerName]=func
        print(f"  New handler registered under {op}.")

    def get_handler(self, op:str):
        return self._handlers.get(op)

    def dispatch(self, op: str, params, ws, encode):
        handler = self._handlers.get(op)
        if handler:
            for i in handler:
                result = i(params)
                # Handlers optionally return a list of messages to send back
                if result:
                    for msg in result:
                        ws.send(encode(msg))
            return True
        return False