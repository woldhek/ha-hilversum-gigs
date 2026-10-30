"""Calendar of upcoming Hilversum gigs."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .sources import Gig


def _to_event(g: Gig) -> CalendarEvent:
    desc = " ".join(x for x in (g.description, g.url or "") if x)
    return CalendarEvent(start=g.start, end=g.end, summary=g.title,
                         location=g.venue, description=desc, uid=g.uid)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([GigsCalendar(entry.runtime_data)])


class GigsCalendar(CoordinatorEntity, CalendarEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "gigs"
    _attr_icon = "mdi:guitar-electric"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_calendar"
        self._attr_device_info = {"identifiers": {(DOMAIN, coordinator.entry.entry_id)},
                                  "name": "Hilversum Gigs", "entry_type": "service"}

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        nxt = next((g for g in self.coordinator.data or [] if g.end > now), None)
        return _to_event(nxt) if nxt else None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime):
        return [_to_event(g) for g in self.coordinator.data or []
                if g.end > start_date and g.start < end_date]
