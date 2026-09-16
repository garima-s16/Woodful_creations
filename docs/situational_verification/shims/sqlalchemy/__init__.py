"""Minimal shim for the parts of sqlalchemy the real Woodful models/
services reference at IMPORT time (class-body column definitions,
function type hints) - not a real ORM. Model class bodies only
*define* columns as class attributes when imported; they never
execute real SQL just by being imported, so inert placeholders are
sufficient for import-time success. Any function that actually
QUERIES a database still needs a real or fake Session passed to it
explicitly - this shim does not attempt that.
"""

class _InertColumnFactory:
    """Column(...), Integer, String(255), ForeignKey(...) etc. all just
    need to be *something* class bodies can assign - never actually
    consulted unless real ORM query execution happens, which no
    import-time code path does."""
    def __call__(self, *a, **k):
        return _InertColumnFactory()
    def __getitem__(self, item):
        return self


Column = _InertColumnFactory()
Integer = _InertColumnFactory()
String = _InertColumnFactory()
Text = _InertColumnFactory()
Boolean = _InertColumnFactory()
DateTime = _InertColumnFactory()
Date = _InertColumnFactory()
Time = _InertColumnFactory()
JSON = _InertColumnFactory()
Numeric = _InertColumnFactory()
ForeignKey = _InertColumnFactory()
UniqueConstraint = _InertColumnFactory()
Index = _InertColumnFactory()


def or_(*a, **k):
    return None


def and_(*a, **k):
    return None
