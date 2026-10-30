"""Sensors: last-minute gigs and newly announced gigs."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (CONF_LAST_MINUTE_HOURS, CONF_NEW_DAYS, DEFAULT_LAST_MINUTE_HOURS,
                    DEFAULT_NEW_DAYS, DOMAIN, setting)


def _brief(g):
    return {"title": g.title, "start": g.start.isoformat(), "venue": g.venue, "url": g.url}


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([LastMinuteSensor(c), NewlyAnnouncedSensor(c)])


class _Base(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "gigs"

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.entry.entry_id)},
                                  "name": "Hilversum Gigs", "entry_type": "service"}

    def _opt(self, key, default):
        return int(setting(self.coordinator.entry, key, default))


class LastMinuteSensor(_Base):
    _attr_icon = "mdi:clock-fast"

    def __init__(self, c):
        super().__init__(c, "last_minute")

    def _gigs(self):
        now = dt_util.now()
        until = now + timedelta(hours=self._opt(CONF_LAST_MINUTE_HOURS, DEFAULT_LAST_MINUTE_HOURS))
        return [g for g in self.coordinator.data or [] if g.end > now and g.start <= until]

    @property
    def native_value(self):
        return len(self._gigs())

    @property
    def extra_state_attributes(self):
        return {"gigs": [_brief(g) for g in self._gigs()],
                "sources": self.coordinator.source_status}


class NewlyAnnouncedSensor(_Base):
    _attr_icon = "mdi:new-box"

    def __init__(self, c):
        super().__init__(c, "newly_announced")

    def _gigs(self):
        return self.coordinator.announced_since(self._opt(CONF_NEW_DAYS, DEFAULT_NEW_DAYS))

    @property
    def native_value(self):
        return len(self._gigs())

    @property
    def extra_state_attributes(self):
        return {"gigs": [_brief(g) for g in self._gigs()]}
