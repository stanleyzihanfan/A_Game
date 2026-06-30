import threading
#Central game state storage and accessing handler
class GameState:
    def __init__(self):
        self._state={}
        self._lock=threading.RLock()
    def add(self,key,value):
        """Add a key-value pair to game state and overrides existing value\n
        If value is a list, is directly set to key\n
        Else added to key as list with single value
        
        :param key: Key to add
        :param value: Value to add
        """
        with self._lock:
            if isinstance(value,list):
                self._state[key]=value
            else:
                self._state[key]=[value]
    def append(self,key,value):
        """Append a value to end of list for key\n
        If key does not exist, adds pair

        :param key: Key to add
        :param value: Value to add
        """
        with self._lock:
            if key in self._state:
                self._state[key].append(value)
            else:
                self.add(key,value)
    def get(self,key):
        """Gets value for key

        :param key: Key to get value for
        :return: Returns value if key exists, else returns None
        """
        return self._state.get(key)
    def exists(self,key):
        """Get if a key exists

        :param key: Key to check
        :return: Boolean if key exists or not
        """
        return key in self._state
    