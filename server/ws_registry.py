# Central WebSocket op handler registry
# Replaces the wsDispatch dict in the original backend.py
# Mods call register_handler() to add their own ops
class Registry:
    def __init__(self):
        # op_name -> handler function
        self._handlers = {}

    def register_handler(self, op: str, func:function, name:str = None):
        """
        Register a handler

        :param op: Name of event hook
        :param funct: Function object of handler
        :param name: Name of handler function
        """
        #If name is not provided, func.__name__ is always "<lambda>"
        handlerName=name or func.__name__
        #Create new event hook if not created
        if not op in self._handlers:
            self._handlers[op]={}
            print(f"  Event Hook {op} created.")
        #If name is not provided, replace with _lambda+unique function ID to prevent collision
        if handlerName=='<lambda>':
            handlerName=f"_lambda_{id(func)}"
        #Warn if another handler with same name already exists & override
        if handlerName in self._handlers[op]:
            print(f"\033[33m  [WARN] Handler {handlerName} already registered under {op}, overwriting!\033[0m")
        #Register function in _handlers
        self._handlers[op][handlerName]=func
        print(f"  New handler registered under {op}.")

    def get_handler(self, op:str, name:str = None):
        """
        Get a handler

        :param op: Event hook to look under
        :param name: Optional, name of handler to get
        :return: If name is provided, returns specified handler function.\n
         If name is not provided/None, returns full event hook of handler+name as a dictionary.\n
         Returns None if not found.
        """
        #Return handler if name is provided
        if name and op in self._handlers:
            return self._handlers[op].get(name)
        #Return full dict under event hook(name not provided)
        return self._handlers.get(op)

    #Dispatch a hook/handler
    def dispatch(self, op: str, params:list, ws, encode):
        """
        Dispatch a hook/handler

        :param op: Event hook to dispatch
        :param params: List of parameters to be passed to functions
        :param ws: WebSocket object
        :param encode: msgPack encoding function
        """
        handlers=self.get_handler(op)
        if handlers:
            for handlerName,func in handlers:
                try:
                    result = func(params)
                    # Handlers optionally return a list of messages to send back
                    if result:
                        for msg in result:
                            ws.send(encode(msg))
                except Exception as e:
                    print(f"\x1b[31mHandler '{handlerName}' under '{op}' failed:\033[0m")
                    print(f"  {type(e).__name__}: {e}")