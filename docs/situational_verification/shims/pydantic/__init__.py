"""Minimal shim providing just enough of pydantic.BaseModel for
app/schemas/chat.py to genuinely import and run unmodified in this
network-isolated sandbox (no pydantic package available - confirmed
via direct curl evidence, not assumed). This is NOT a reimplementation
of chat.py's own logic - chat.py's real source file is imported as-is;
only the BaseModel it inherits from is stood in for.

Deliberately minimal ("do not overengineer
the alternative") - supports exactly what chat.py's classes actually
use: typed class attributes with defaults, becoming instance attributes
settable via keyword arguments at construction. No validation, no
Field(), no Config - chat.py's real classes use none of those.
"""
import typing


class BaseModel:
    def __init__(self, **data):
        annotations = {}
        for klass in reversed(type(self).__mro__):
            annotations.update(getattr(klass, "__annotations__", {}))
        for name in annotations:
            default = getattr(type(self), name, None)
            setattr(self, name, data.get(name, default))
        for key, value in data.items():
            if key not in annotations:
                setattr(self, key, value)
