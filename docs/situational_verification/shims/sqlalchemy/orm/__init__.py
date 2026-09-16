class Session:
    """Type-hint-only placeholder (db: Session in real function
    signatures) - Python does not enforce type hints at runtime, so
    an empty class is sufficient unless a function body actually
    calls a real Session method, which is out of scope for this shim."""
    pass


def relationship(*a, **k):
    return None


def sessionmaker(*a, **k):
    return None
