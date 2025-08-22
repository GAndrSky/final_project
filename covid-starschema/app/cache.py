import time
from functools import wraps

def ttl_cache(seconds: int = 300):
    store = {}
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, frozenset(kwargs.items()))
            now = time.time()
            if key in store:
                ts, val = store[key]
                if now - ts < seconds:
                    return val
            val = fn(*args, **kwargs)
            store[key] = (now, val)
            return val
        return wrapper
    return deco
