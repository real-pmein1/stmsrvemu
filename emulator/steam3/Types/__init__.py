from enum import Enum, IntEnum


class SteamIntEnum(IntEnum):
    @classmethod
    def get_name(cls, value):
        # Attempt to find a member with the given value and return its name; if not found, return 'Unknown'
        return cls(value).name if value in cls._value2member_map_ else 'Unknown'


# Meta function to get the enum name from its integer value
def get_enum_name(enum_class, value):
    return enum_class.get_name(value)