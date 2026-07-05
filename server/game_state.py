import threading,copy
#Central game state storage and accessing handler
class GameState:
    def __init__(self):
        self._state={}
        self._lock=threading.RLock()
    def set(self,key:list,value,override=False):
        """Sets a key-value pair to game state
        
        :param key: Key to add
        :param value: Value to add
        :param override: Whether to override any conflicting leaves
        """
        with self._lock:
            last = self._state
            for k in key[:-1]:
                if not isinstance(last,dict) and not override:
                    raise KeyError('`Key {key} does not exist in game state`')
                if k not in last:
                    last[k] = {}
                last = last[k]
            last[key[-1]] = value
    def get(self,key:list,deepcopy=True):
        """Gets value for key\n
        WARNING: When using deepcopy=False, make sure it is used with thread lock

        :param key: Key to get value for
        :param deepcopy: Whether to return a deep copy of value
        :return: Returns value if key exists, else returns None
        """
        with self._lock:
            last=self._state
            for k in key:
                if k not in last:
                    return None
                last=last[k]
            if deepcopy:
                return copy.deepcopy(last)
            else:
                return 
    def exists(self,key:list):
        """Get if a key exists

        :param key: Key to check
        :return: Boolean if key exists or not
        """
        with self._lock:
            last = self._state
            for k in key:
                if k not in last:
                    return False
                last = last[k]
            return True