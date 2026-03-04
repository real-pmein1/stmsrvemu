class WrapperBase(int):
    def __new__(cls, value):
        # build the int-subclass instance
        return super().__new__(cls, int(value))

    def __int__(self) -> int:
        # call int.__int__ under the hood, not our override
        return super().__int__()

    def __index__(self) -> int:
        # likewise for indexing contexts
        return super().__index__()

    def __repr__(self) -> str:
        # show the real underlying integer
        return f"{self.__class__.__name__}({super().__int__()})"

    def __eq__(self, other):
        if isinstance(other, WrapperBase):
            return type(self) is type(other) and int(self) == int(other)
        if isinstance(other, int):
            return int(self) == other
        return NotImplemented

    def __hash__(self):
        return hash((type(self), int(self)))

    # arithmetic, bitwise, and shift operators can stay as-is,
    # since int(self) now calls our fixed __int__
    def __add__(self, other):   return type(self)(int(self) + int(other))
    def __radd__(self, other):  return type(self)(int(other) + int(self))
    def __mul__(self, other):   return type(self)(int(self) * int(other))
    def __rmul__(self, other):  return type(self)(int(other) * int(self))
    def __or__(self, other):    return type(self)(int(self) | int(other))
    def __ror__(self, other):   return type(self)(int(other) | int(self))
    def __and__(self, other):   return type(self)(int(self) & int(other))
    def __rand__(self, other):  return type(self)(int(other) & int(self))
    def __xor__(self, other):   return type(self)(int(self) ^ int(other))
    def __rxor__(self, other):  return type(self)(int(other) ^ int(self))
    def __lshift__(self, other):return type(self)(int(self) << int(other))
    def __rlshift__(self, other): return type(self)(int(other) << int(self))
    def __rshift__(self, other): return type(self)(int(self) >> int(other))
    def __rrshift__(self, other):return type(self)(int(other) >> int(self))


class AccountID(WrapperBase):
    """Distinct type for account IDs"""
    pass


class ConnectionID(WrapperBase):
    """Distinct type for connection IDs"""
    pass
