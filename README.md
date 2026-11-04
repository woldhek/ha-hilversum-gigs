# Hilversum Gigs

Home Assistant integration for **live music in Hilversum only** — to catch last-minute gigs and to hear about new shows the moment they're announced.

## What you get
| Entity | What it does |
|---|---|
| `calendar.hilversum_gigs_gigs` | All upcoming gigs from the configured venues |
| `sensor.hilversum_gigs_last_minute_gigs` | Count of gigs in the next 48 h (configurable); list in `gigs` attribute (title, start, venue, genre, price, sold_out, status, tickets), per-source health in `sources` |
| `sensor.hilversum_gigs_newly_announced_gigs` | Gigs first seen in the last 7 days |
| Event `hilversum_gigs_new_gig` | Fired once per newly announced gig (not on first install) |

Polls every 3 hours.

## Sources
One per line, `Name | URL`. Any venue page works if it offers one of:
- an iCal feed (`.ics` / `webcal://`), or a link to one on the page
- WordPress *The Events Calendar* REST API
- schema.org `Event` JSON-LD (most ticketing/venue sites)
- WordPress sites whose events are a custom post type with a date field (Themify Post Type Builder), e.g. De Vioolkist: the agenda URL is enough, the REST API is found by itself
- Heuvellaan: date and series from the agenda, start time, studio and ticket link from each concert page (fetched once, then remembered)
- De Vorstin's own feed (`https://vorstin.nl/?agenda_json`, what their agenda page reads): start and door times, hall, genre, price, ticket link, sold out / postponed. A `vorstin.nl` agenda URL finds it by itself.

Defaults: De Vorstin, De Vioolkist, Heuvellaan and Live Hilversum (city agenda, also covers classical/church concerts). `Exclude keywords` filters non-music items (film, workshop, comedy, bingo…); it also matches the genre, so e.g. `dansfeest` drops party nights.

Verify a source before adding it:
```bash
pip install aiohttp
python3 tools/check_sources.py https://vorstin.nl/agenda/
```

## Install
HACS → Custom repositories → `https://github.com/woldhek/ha-hilversum-gigs` (type Integration), or copy `custom_components/hilversum_gigs` into your config. Restart, then *Settings → Devices & services → Add → Hilversum Gigs*.

## Automations
New show announced → phone notification:
```yaml
automation:
  - alias: Nieuw optreden in Hilversum
    triggers:
      - trigger: event
        event_type: hilversum_gigs_new_gig
    actions:
      - action: notify.mobile_app_telefoon
        data:
          title: "Nieuw in {{ trigger.event.data.venue }}"
          message: "{{ trigger.event.data.title }} – {{ as_datetime(trigger.event.data.start).strftime('%a %d %b %H:%M') }}"
          data: { url: "{{ trigger.event.data.url }}" }
```

Last-minute tip in an evening announcement:
```yaml
{% set g = state_attr('sensor.hilversum_gigs_last_minute_gigs', 'gigs') or [] %}
{% if g %}Morgen live in Hilversum: {{ g[0].title }} in {{ g[0].venue }}.{% endif %}
```

## Development
`python3 -m pytest tests` — parser tests run offline.
