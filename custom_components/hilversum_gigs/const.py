"""Constants for Hilversum Gigs."""
from datetime import timedelta

DOMAIN = "hilversum_gigs"
CONF_SOURCES = "sources"
CONF_LAST_MINUTE_HOURS = "last_minute_hours"
CONF_EXCLUDE = "exclude_keywords"
CONF_NEW_DAYS = "new_days"

DEFAULT_LAST_MINUTE_HOURS = 48
DEFAULT_NEW_DAYS = 7
SCAN_INTERVAL = timedelta(hours=3)

# One per line: "Name | URL". Hilversum venues only; extend in the options.
DEFAULT_SOURCES = "\n".join([
    "De Vorstin | https://vorstin.nl/?agenda_json",
    "Live Hilversum | https://www.livehilversum.com/nl/agenda",
])
DEFAULT_EXCLUDE = "film, rondleiding, workshop, markt, expositie, tentoonstelling, comedy, bingo"

EVENT_NEW_GIG = f"{DOMAIN}_new_gig"
STORAGE_VERSION = 1


def parse_sources(text: str) -> list[tuple[str, str]]:
    out = []
    for line in (text or "").splitlines():
        if "|" in line:
            name, url = (p.strip() for p in line.split("|", 1))
        else:
            url = line.strip()
            name = url.split("//")[-1].split("/")[0]
        if url.startswith(("http", "webcal")):
            out.append((name, url))
    return out


def parse_keywords(text: str) -> list[str]:
    return [k.strip() for k in (text or "").split(",") if k.strip()]


def setting(entry, key: str, default):
    """An option, else what the setup chose, else the default."""
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)
