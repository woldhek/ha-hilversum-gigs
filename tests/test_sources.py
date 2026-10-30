import sys, pathlib
from datetime import datetime
from zoneinfo import ZoneInfo
import importlib.util
_D = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "hilversum_gigs"
def _load(n):
    spec = importlib.util.spec_from_file_location(n, _D / f"{n}.py"); m = importlib.util.module_from_spec(spec); sys.modules[n] = m; spec.loader.exec_module(m); return m
s = _load("sources")

TZ = ZoneInfo("Europe/Amsterdam")
NOW = datetime(2026, 10, 30, 12, tzinfo=TZ)

HTML = '''<html><script type="application/ld+json">
{"@context":"https://schema.org","@graph":[{"@type":"MusicEvent","name":"Band &amp; Co",
"startDate":"2026-11-01T20:30","location":{"@type":"Place","name":"De Vorstin"},"url":"/event/band"},
{"@type":"Event","name":"Filmavond","startDate":"2026-11-02"},
{"@type":"Event","name":"Oud","startDate":"2026-10-01T20:00"}]}</script></html>'''

ICS = "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Jazz in de\r\n  kerk\r\nDTSTART;TZID=Europe/Amsterdam:20261105T200000\r\nLOCATION:Vituskerk\r\nEND:VEVENT\r\nEND:VCALENDAR"

def test_jsonld():
    g = s.parse_jsonld(HTML, "Vorstin", "https://vorstin.nl/agenda/")
    assert [x.title for x in g] == ["Band & Co", "Filmavond", "Oud"]
    assert g[0].venue == "De Vorstin" and g[0].url == "https://vorstin.nl/event/band"
    assert g[0].start.hour == 20 and g[0].start.tzinfo
    out = s.filter_gigs(g, ["film"], NOW)
    assert [x.title for x in out] == ["Band & Co"]

def test_ics():
    g = s.parse_ics(ICS, "Kerk")
    assert g[0].title == "Jazz in de kerk" and g[0].venue == "Vituskerk"
    assert g[0].start == datetime(2026, 11, 5, 20, tzinfo=TZ)

def test_tribe():
    g = s.parse_tribe({"events":[{"title":"X","start_date":"2026-11-03 21:00:00","venue":{"venue":"Y"}}]}, "WP")
    assert g[0].venue == "Y" and g[0].start.hour == 21

def test_uid_stable():
    a = s.parse_jsonld(HTML, "V", "https://x/")[0]; b = s.parse_jsonld(HTML, "V", "https://x/")[0]
    assert a.uid == b.uid
