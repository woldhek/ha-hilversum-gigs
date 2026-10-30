import sys, types
try:
    import aiohttp  # noqa: F401
except ImportError:  # parsers don't need it; stub for offline test runs
    m = types.ModuleType("aiohttp")
    m.ClientTimeout = lambda **k: None
    m.ClientSession = m.ClientError = m.ClientResponseError = Exception
    sys.modules["aiohttp"] = m
