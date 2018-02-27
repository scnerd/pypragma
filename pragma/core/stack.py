class DictStack:
    """
    Creates a stack of dictionaries to roughly emulate closures and variable environments
    """

    def __init__(self, *base):
        import builtins
        self.dicts = [dict(builtins.__dict__)] + [dict(d) for d in base]
        self.constants = [True] + [False] * len(base)

    def __iter__(self):
        return (key for dct in self.dicts for key in dct.keys())

    def __setitem__(self, key, value):
        # print("SETTING {} = {}".format(key, value))
        self.dicts[-1][key] = value

    def __getitem__(self, item):
        for dct in self.dicts[::-1]:
            if item in dct:
                if dct[item] is None:
                    raise KeyError("Found '{}', but it was set to an unknown value".format(item))
                return dct[item]
        raise KeyError("Can't find '{}' anywhere in the function's context".format(item))

    def __delitem__(self, item):
        for dct in self.dicts[::-1]:
            if item in dct:
                del dct[item]
                return
        raise KeyError()

    def __contains__(self, item):
        return any(item == key for dct in self.dicts for key in dct.keys())

    def items(self):
        items = []
        for dct in self.dicts[::-1]:
            for k, v in dct.items():
                if k not in items:
                    items.append((k, v))
        return items

    def keys(self):
        return set().union(*[dct.keys() for dct in self.dicts])

    def push(self, dct=None, is_constant=False):
        self.dicts.append(dct or {})
        self.constants.append(is_constant)

    def pop(self):
        self.constants.pop()
        return self.dicts.pop()
