import threading,copy
#Central game state storage and accessing handler
class GameState:
    def __init__(self):
        self._state={}
        self._lock=threading.RLock()
    def add(self,key:list,value):
        """Add a key-value pair to game state and overrides existing leaves for related keys\n
        If value is a list, is directly set to key\n
        Else added to key as list with single value
        
        :param key: Key to add
        :param value: Value to add
        """
        with self._lock:
            last = self._state
            for k in key[:-1]:
                if k not in last or not isinstance(last,dict):
                    last[k] = {}
                last = last[k]
            if isinstance(value,list):
                last[key[-1]] = value
            else:
                last[key[-1]]=[value]
    def append(self,key:list,value):
        """Append a value to end of list for key\n
        If key does not exist, adds pair

        :param key: Key to add
        :param value: Value to add
        :return: Index in list of value
        """
        with self._lock:
            last = self._state
            for k in key[:-1]:
                if k not in last:
                    last[k] = {}
                last = last[k]
            if key[-1] in last:
                last[key[-1]].append(value)
                return len(last[key[-1]])-1
            else:
                last[key[-1]]=[value]
                return 0
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