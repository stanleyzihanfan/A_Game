# Central WebSocket op handler registry
# Replaces the wsDispatch dict in the original backend.py
# Mods call register_handler() to add their own ops
class Registry:
    def __init__(self):
        # op_name -> handler function
        self._handlers = {}

    def register_handler(self, op: str, func):
        self._handlers[op] = func
        print("Handler "+op+" registered.")

    def get_handler(self, op:str):
        return self._handlers.get(op)

    def dispatch(self, op: str, params, ws, encode):
        handler = self._handlers.get(op)
        if handler:
            result = handler(params)
            # Handlers optionally return a list of messages to send back
            if result:
                for msg in result:
                    ws.send(encode(msg))
            return True
        return False