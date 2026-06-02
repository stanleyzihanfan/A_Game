# Central WebSocket op handler registry
# Replaces the wsDispatch dict in the original backend.py
# Mods call register_handler() to add their own ops
class Registry:
    def __init__(self):
        # op_name -> handler function
        self._handlers = {}

    def register_handler(self, op: str, func):
        if not op in self._handlers:
            self._handlers[op]=[]
            print(f"  Event Handler {op} created.")
        self._handlers[op].append(func)
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