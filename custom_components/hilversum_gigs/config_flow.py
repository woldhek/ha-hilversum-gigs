"""Config and options flow."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (NumberSelector, NumberSelectorConfig,
                                            TextSelector, TextSelectorConfig)

from .const import (CONF_EXCLUDE, CONF_LAST_MINUTE_HOURS, CONF_NEW_DAYS, CONF_SOURCES,
                    DEFAULT_EXCLUDE, DEFAULT_LAST_MINUTE_HOURS, DEFAULT_NEW_DAYS,
                    DEFAULT_SOURCES, DOMAIN, parse_sources)


def _schema(d: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_SOURCES, default=d.get(CONF_SOURCES, DEFAULT_SOURCES)):
            TextSelector(TextSelectorConfig(multiline=True)),
        vol.Optional(CONF_EXCLUDE, default=d.get(CONF_EXCLUDE, DEFAULT_EXCLUDE)): TextSelector(),
        vol.Required(CONF_LAST_MINUTE_HOURS, default=d.get(CONF_LAST_MINUTE_HOURS, DEFAULT_LAST_MINUTE_HOURS)):
            NumberSelector(NumberSelectorConfig(min=6, max=168, step=6, mode="box")),
        vol.Required(CONF_NEW_DAYS, default=d.get(CONF_NEW_DAYS, DEFAULT_NEW_DAYS)):
            NumberSelector(NumberSelectorConfig(min=1, max=30, step=1, mode="box")),
    })


def _validate(user_input):
    return {} if parse_sources(user_input[CONF_SOURCES]) else {CONF_SOURCES: "no_sources"}


class GigsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None and not (errors := _validate(user_input)):
            return self.async_create_entry(title="Hilversum Gigs", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema(user_input or {}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return GigsOptionsFlow()


class GigsOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None and not (errors := _validate(user_input)):
            return self.async_create_entry(data=user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current), errors=errors)
