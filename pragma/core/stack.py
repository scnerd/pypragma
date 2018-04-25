from collections import ChainMap
import builtins


class DictStack:
    """
    Creates a stack of dictionaries to roughly emulate closures and variable environments
    """

    def __init__(self, *base):
        self._dicts = ChainMap(builtins.__dict__)
        for d in base:
            self.push(d)

    def __iter__(self):
        return iter(self._dicts)

    def __setitem__(self, key, value):
        self._dicts[key] = value

    def __getitem__(self, item):
        return self._dicts[item]

    def __delitem__(self, item):
        del self._dicts[item]

    def __contains__(self, item):
        return item in self._dicts

    def items(self):
        return self._dicts.items()

    def keys(self):
        return self._dicts.keys()

    def push(self, dct=None):
        self._dicts = self._dicts.new_child(dct)

    def pop(self):
        cur = self._dicts.maps[0]
        self._dicts = self._dicts.parents
        return cur

    def __repr__(self):
        return repr(self._dicts)
