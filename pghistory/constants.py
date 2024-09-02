import enum


class Default(enum.Enum):
    token = 0


class Unset(enum.Enum):
    token = 0


DEFAULT = Default.token
"""
For setting a configuration value back to its default value
"""

UNSET = Unset.token
