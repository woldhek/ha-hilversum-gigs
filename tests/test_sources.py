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


def test_vorstin_agenda():
    html = (pathlib.Path(__file__).parent / "vorstin_agenda.html").read_text()
    gigs = s.parse_slug_links(html, "De Vorstin", today=NOW.date())
    by = {g.title: g for g in gigs}
    assert len(gigs) > 50
    assert by["Ellen ten Damme"].start.date().isoformat() == "2026-11-13"   # -13-11-2026
    assert any(g.url.endswith("phil-campbells-bastard-sons-13112026/") and g.start.day == 13 for g in gigs)
    assert any(g.url.endswith("paceshifters-play-nirvana-14-11-26/") and g.start.year == 2026 for g in gigs)
    assert all(g.all_day and g.venue == "De Vorstin" for g in gigs)
    assert not any("jamsessie" in g.url or "avrotros" in g.url for g in gigs)  # no date / past without year


def test_slug_dates():
    t = NOW.date()
    assert s.date_from_slug("https://x/a-09012027/", t).isoformat() == "2027-01-09"
    assert s.date_from_slug("https://x/a-24-04-27/", t).isoformat() == "2027-04-24"
    assert s.date_from_slug("https://x/open-podium/", t) is None


def test_vorstin_json():
    import json as _json
    data = _json.loads((pathlib.Path(__file__).parent / "vorstin_agenda.json").read_text())
    gigs = {g.title: g for g in s.parse_vorstin_json(data, "De Vorstin")}
    pride = gigs["Gooise Pride Party"]
    assert pride.start == datetime(2026, 10, 30, 19, 30, tzinfo=TZ) and not pride.all_day
    assert pride.venue == "De Vorstin, Kleine zaal" and pride.price == "€ 17,75"
    assert pride.ticket_url.startswith("https://tickets.vorstin.nl/")
    assert gigs["Jamsessie"].start.hour == 15 and gigs["Jamsessie"].price == "gratis"
    assert gigs["Ellen ten Damme"].sold_out and gigs["Ellen ten Damme"].doors.hour == 19
    assert gigs["Kei Foute Party"].end == datetime(2026, 11, 28, 1, 0, tzinfo=TZ)
    out = s.filter_gigs(list(gigs.values()), ["dansfeest"], NOW)
    assert "Kei Foute Party" not in {g.title for g in out}  # genre is filterable


def test_vioolkist_wp_ptb():
    import json as _json
    data = _json.loads((pathlib.Path(__file__).parent / "vioolkist_agenda.json").read_text())
    assert s._looks_wp_ptb(data)
    gigs = s.parse_wp_ptb(data, "De Vioolkist")
    by = {g.title: g for g in gigs}
    assert len(gigs) == 4  # the item without fields has no date
    koffie = by["Koffieconcert in De Vioolkist"]
    assert koffie.start == datetime(2026, 11, 8, 11, 0, tzinfo=TZ) and koffie.venue == "De Vioolkist"
    assert koffie.ticket_url.startswith("https://studio-theater-de-vioolkist.weticket.io/")
    assert by["DESRAY’S CIRCLE OF LIVE"].start.year == 2027
    assert by["B-fem en de Vioolkist presenteren: Spark Lab Open Podium"].ticket_url.endswith("19-november-2026")
    out = s.filter_gigs(gigs, ["besloten"], NOW)
    assert "Besloten gelegenheid" not in {g.title for g in out}


def test_archive_type_detection():
    html = '<body class="archive post-type-archive post-type-archive-agenda wp-theme-x">'
    assert s._ARCHIVE_TYPE_RE.search(html)[1] == "agenda"


def test_heuvellaan():
    d = pathlib.Path(__file__).parent
    gigs = s.parse_heuvellaan_agenda((d / "heuvellaan_agenda.html").read_text(), "Heuvellaan")
    by = {g.title: g for g in gigs}
    assert len(gigs) == 3 and all(g.all_day for g in gigs)
    assert by["Heuvellaan Serveert: Aisling & Magnus"].genre == "heuvellaan concert"
    jm = by["Jong Metropole + Jeangu Macrooy"]
    detail = s.parse_heuvellaan_detail((d / "heuvellaan_concert.html").read_text())
    assert detail == {"time": (20, 0), "place": "Heuvellaan Hilversum, Studio 1",
                      "tickets": "https://mco.stager.co/shop/default/events/111658400"}
    s.apply_heuvellaan_detail(jm, detail)
    assert jm.start == datetime(2026, 11, 28, 20, 0, tzinfo=TZ) and not jm.all_day
    assert jm.venue == "Heuvellaan Hilversum, Studio 1"
