"""Coordinator: polls sources, tracks newly announced gigs."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EXCLUDE, CONF_SOURCES, DEFAULT_EXCLUDE, DEFAULT_SOURCES, DOMAIN,
    EVENT_NEW_GIG, SCAN_INTERVAL, STORAGE_VERSION, STORAGE_KEY_SUFFIX, parse_keywords, parse_sources, setting,
)
from .sources import Gig, fetch_source, filter_gigs

_LOGGER = logging.getLogger(__name__)


class GigsCoordinator(DataUpdateCoordinator[list[Gig]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL, config_entry=entry)
        self.entry = entry
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.{STORAGE_KEY_SUFFIX}")
        self.first_seen: dict[str, str] = {}  # uid -> ISO timestamp first discovered
        self.source_status: dict[str, str] = {}
        self._loaded = False

    async def _async_update_data(self) -> list[Gig]:
        if not self._loaded:
            self.first_seen = (await self._store.async_load()) or {}
            self._loaded = True
        initial_run = not self.first_seen

        session = async_get_clientsession(self.hass)
        sources = parse_sources(setting(self.entry, CONF_SOURCES, DEFAULT_SOURCES))
        results = await asyncio.gather(
            *(fetch_source(session, n, u) for n, u in sources), return_exceptions=True
        )
        gigs: list[Gig] = []
        for (name, _), res in zip(sources, results):
            if isinstance(res, Exception):
                self.source_status[name] = f"error: {res}"
                _LOGGER.warning("Source %s failed: %s", name, res)
                continue
            found, method = res
            self.source_status[name] = f"{len(found)} via {method}"
            if not found:
                _LOGGER.warning("Source %s returned no parseable events", name)
            gigs.extend(found)

        if sources and all(isinstance(r, Exception) for r in results):
            raise UpdateFailed("All sources failed")

        gigs = filter_gigs(gigs, parse_keywords(setting(self.entry, CONF_EXCLUDE, DEFAULT_EXCLUDE)), dt_util.now())

        now_iso = dt_util.now().isoformat()
        for g in gigs:
            if g.uid in self.first_seen:
                continue
            if initial_run:
                # Already on the agenda when the integration was set up: not "new", and no alert.
                self.first_seen[g.uid] = "1970-01-01T00:00:00+00:00"
                continue
            self.first_seen[g.uid] = now_iso
            self.hass.bus.async_fire(EVENT_NEW_GIG, g.as_dict())

        # forget past events
        live = {g.uid for g in gigs}
        cutoff = (dt_util.now() - timedelta(days=60)).isoformat()
        self.first_seen = {u: t for u, t in self.first_seen.items() if u in live or t > cutoff}
        await self._store.async_save(self.first_seen)
        return gigs

    def announced_since(self, days: int) -> list[Gig]:
        cutoff = dt_util.now() - timedelta(days=days)
        return [
            g for g in (self.data or [])
            if (ts := self.first_seen.get(g.uid)) and datetime.fromisoformat(ts) >= cutoff
        ]
