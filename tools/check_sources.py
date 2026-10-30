"""Run on any machine with internet: python3 tools/check_sources.py [URL ...]
Shows which parsing method works for each source and the first upcoming gigs."""
import asyncio, sys, pathlib
import importlib.util
_D = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "hilversum_gigs"
def _load(n):
    spec = importlib.util.spec_from_file_location(n, _D / f"{n}.py"); m = importlib.util.module_from_spec(spec); sys.modules[n] = m; spec.loader.exec_module(m); return m
import aiohttp
s = _load("sources"); _c = _load("const")
DEFAULT_SOURCES, DEFAULT_EXCLUDE, parse_sources, parse_keywords = _c.DEFAULT_SOURCES, _c.DEFAULT_EXCLUDE, _c.parse_sources, _c.parse_keywords

async def main(urls):
    srcs = [(u, u) for u in urls] or parse_sources(DEFAULT_SOURCES)
    async with aiohttp.ClientSession() as session:
        for name, url in srcs:
            try:
                gigs, method = await s.fetch_source(session, name, url)
            except Exception as e:
                print(f"✗ {name}: {e}"); continue
            gigs = s.filter_gigs(gigs, parse_keywords(DEFAULT_EXCLUDE))
            print(f"{'✓' if gigs else '–'} {name}: {len(gigs)} upcoming via {method}")
            for g in gigs[:8]:
                print(f"    {g.start:%a %d %b %H:%M}  {g.title}  @ {g.venue}")

asyncio.run(main(sys.argv[1:]))
