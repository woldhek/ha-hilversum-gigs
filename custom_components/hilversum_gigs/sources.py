"""Fetch and parse gig agendas. Pure aiohttp, no Home Assistant imports (testable).

Each source is just a URL. We try, in order:
  1. iCal  (URL ends in .ics / webcal, or the page links to one)
  2. The Events Calendar REST API (common on WordPress venue sites)
  3. schema.org Event JSON-LD embedded in the page (most ticketing/venue sites)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta, timezone
from html import unescape
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import aiohttp

_LOGGER = logging.getLogger(__name__)
TZ = ZoneInfo("Europe/Amsterdam")
HEADERS = {"User-Agent": "Mozilla/5.0 (HomeAssistant hilversum_gigs)", "Accept-Language": "nl,en"}
TIMEOUT = aiohttp.ClientTimeout(total=30)

_LDJSON_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)
_ICS_LINK_RE = re.compile(r'href=["\']((?:webcal|https?)://[^"\']+?\.ics[^"\']*|[^"\']+?\.ics)["\']', re.I)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Gig:
    uid: str
    title: str
    start: datetime
    end: datetime
    venue: str
    url: str | None
    source: str
    description: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        return d


def _uid(source: str, title: str, start: datetime) -> str:
    raw = f"{source}|{title.strip().lower()}|{start.date().isoformat()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _clean(text) -> str:
    if not text:
        return ""
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)
    return re.sub(r"\s+", " ", unescape(_TAG_RE.sub(" ", str(text)))).strip()


def parse_dt(value) -> datetime | None:
    """Parse ISO-ish datetimes/dates; naive values are Europe/Amsterdam."""
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    try:
        if len(s) == 10:
            return datetime.combine(date.fromisoformat(s), time(20, 0), TZ)
        dt = datetime.fromisoformat(s.replace(" ", "T", 1))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def _make(source, venue_default, title, start, end, url, venue=None, desc="") -> Gig | None:
    title = _clean(title)
    if not title or not start:
        return None
    if not end or end <= start:
        end = start + timedelta(hours=3)
    return Gig(
        uid=_uid(source, title, start),
        title=title,
        start=start,
        end=end,
        venue=_clean(venue) or venue_default,
        url=url,
        source=source,
        description=_clean(desc)[:500],
    )


# ---------- JSON-LD ----------
def _walk_events(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk_events(n)
    elif isinstance(node, dict):
        t = node.get("@type", "")
        types = t if isinstance(t, list) else [t]
        if any(isinstance(x, str) and x.endswith("Event") for x in types):
            yield node
        for key in ("@graph", "itemListElement", "item", "subEvent", "event", "events"):
            if key in node:
                yield from _walk_events(node[key])


def parse_jsonld(html: str, source: str, base_url: str) -> list[Gig]:
    gigs = []
    for block in _LDJSON_RE.findall(html):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        for ev in _walk_events(data):
            loc = ev.get("location") or {}
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            venue = loc.get("name") if isinstance(loc, dict) else loc
            url = ev.get("url")
            gig = _make(
                source, source, ev.get("name"), parse_dt(ev.get("startDate")),
                parse_dt(ev.get("endDate")), urljoin(base_url, url) if url else None,
                venue, ev.get("description", ""),
            )
            if gig:
                gigs.append(gig)
    return gigs


# ---------- iCal ----------
def parse_ics(text: str, source: str) -> list[Gig]:
    text = re.sub(r"\r?\n[ \t]", "", text)  # unfold
    gigs = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        props = {}
        for line in block.strip().splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            name, *params = key.split(";")
            props[name.upper()] = (val, params)

        def dt(k):
            if k not in props:
                return None
            val, params = props[k]
            tzid = next((p.split("=", 1)[1] for p in params if p.upper().startswith("TZID=")), None)
            try:
                if len(val) == 8:
                    return datetime.combine(datetime.strptime(val, "%Y%m%d").date(), time(20), TZ)
                d = datetime.strptime(val.rstrip("Z"), "%Y%m%dT%H%M%S")
            except ValueError:
                return None
            if val.endswith("Z"):
                return d.replace(tzinfo=timezone.utc)
            return d.replace(tzinfo=ZoneInfo(tzid) if tzid else TZ)

        def txt(k):
            return props[k][0].replace("\\,", ",").replace("\\n", " ").replace("\\;", ";") if k in props else ""

        gig = _make(source, source, txt("SUMMARY"), dt("DTSTART"), dt("DTEND"),
                    txt("URL") or None, txt("LOCATION") or None, txt("DESCRIPTION"))
        if gig:
            gigs.append(gig)
    return gigs


# ---------- The Events Calendar (WordPress) ----------
def parse_tribe(data: dict, source: str) -> list[Gig]:
    gigs = []
    for ev in data.get("events", []):
        venue = ev.get("venue") or {}
        gig = _make(source, source, ev.get("title"), parse_dt(ev.get("start_date")),
                    parse_dt(ev.get("end_date")), ev.get("url"),
                    venue.get("venue") if isinstance(venue, dict) else None,
                    ev.get("excerpt") or ev.get("description"))
        if gig:
            gigs.append(gig)
    return gigs


async def _get(session: aiohttp.ClientSession, url: str) -> tuple[int, str, str]:
    url = re.sub(r"^webcal://", "https://", url)
    async with session.get(url, headers=HEADERS, timeout=TIMEOUT) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), await resp.text(errors="replace")


async def fetch_source(session: aiohttp.ClientSession, name: str, url: str) -> tuple[list[Gig], str]:
    """Return (gigs, method) for one source. Raises on network errors."""
    status, ctype, body = await _get(session, url)
    if status >= 400:
        raise aiohttp.ClientResponseError(None, (), status=status, message=f"HTTP {status} for {url}")

    if "calendar" in ctype or body.lstrip().startswith("BEGIN:VCALENDAR"):
        return parse_ics(body, name), "ical"

    gigs = parse_jsonld(body, name, url)
    if gigs:
        return gigs, "json-ld"

    # WordPress + The Events Calendar
    if "wp-content" in body or "/wp-json" in body or "/content/uploads/" in body:
        root = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        api = f"{root}/wp-json/tribe/events/v1/events?per_page=100&start_date={date.today().isoformat()}"
        try:
            st, _, apibody = await _get(session, api)
            if st == 200:
                gigs = parse_tribe(json.loads(apibody), name)
                if gigs:
                    return gigs, "tribe-api"
        except (aiohttp.ClientError, json.JSONDecodeError):
            pass

    # A linked iCal feed on the page
    for link in _ICS_LINK_RE.findall(body)[:3]:
        try:
            st, _, ics = await _get(session, urljoin(url, unescape(link)))
            if st == 200 and "BEGIN:VCALENDAR" in ics:
                return parse_ics(ics, name), "ical-link"
        except aiohttp.ClientError:
            continue

    return [], "none"


def filter_gigs(gigs: list[Gig], exclude_keywords: list[str], now: datetime | None = None) -> list[Gig]:
    now = now or datetime.now(TZ)
    ex = [k.lower() for k in exclude_keywords if k]
    out, seen = [], set()
    for g in sorted(gigs, key=lambda g: g.start):
        if g.end < now or g.uid in seen:
            continue
        hay = f"{g.title} {g.description}".lower()
        if any(k in hay for k in ex):
            continue
        seen.add(g.uid)
        out.append(g)
    return out
