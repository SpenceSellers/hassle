# hassle

A [Home Assistant](https://www.home-assistant.io/) CLI.

## Installation

```sh
uv tool install .
```

or

```sh
pipx install .
```

Requires [uv](https://docs.astral.sh/uv/) or [pipx](https://pipx.pypa.io/).

## CLI reference

```
Usage: hassle [OPTIONS] COMMAND [ARGS]...

  hassle — a Home Assistant CLI.

Options:
  --help  Show this message and exit.

Commands:
  add-event     Create a calendar event.
  calendars     List calendars, optionally filtered by name or entity ID...
  call          Call an arbitrary HA service.
  events        List events from one or more calendars (matched by name...
  get           Get detailed info and recent history for matched entities.
  history       Show interleaved state history, filtered by entity ID or...
  off           Turn off an entity.
  on            Turn on an entity.
  services      Browse available HA services.
  set           Set attributes on an entity (e.g.
  states        List entity states, optionally filtered by substring...
  todo          Show items on a todo list.
  todo-add      Add an item to a todo list.
  todo-check    Mark a todo item as completed.
  todo-clear    Remove all completed items from a todo list.
  todo-remove   Remove an item from a todo list by name.
  todo-uncheck  Mark a todo item as not completed.
  todos         List todo lists with pending items, optionally filtered by name or entity ID...
  toggle        Toggle an entity.
```

### add-event

```
Usage: hassle add-event [OPTIONS] [CALENDAR...]

  Create a calendar event. CALENDAR identifies the target calendar by name or
  entity ID substring.

Options:
  -s, --summary TEXT      Event title.  [required]
  --start TEXT            Start date/time (YYYY-MM-DD for all-day, YYYY-MM-
                          DDTHH:MM for timed).  [required]
  --end TEXT              End date/time. Defaults to 1h after start (timed) or
                          next day (all-day).
  -d, --description TEXT  Event description.
  -l, --location TEXT     Event location.
  --help                  Show this message and exit.
```

### calendars

```
Usage: hassle calendars [OPTIONS] [NAME...]

  List calendars, optionally filtered by name or entity ID substring.

Options:
  --help  Show this message and exit.
```

### call

```
Usage: hassle call [OPTIONS] SERVICE [ARGS]...

  Call an arbitrary HA service.

  hassle call domain/service [filters] [key=value ...]

  Values are parsed as JSON, so arrays and numbers work:   hassle call
  light/turn_on kitchen brightness=200   hassle call light/turn_on kitchen
  hs_color=[30,100]

Options:
  --help  Show this message and exit.
```

### events

```
Usage: hassle events [OPTIONS] [CALENDAR...]

  List events from one or more calendars (matched by name or entity ID
  substring). Shows next 7 days by default.

Options:
  --start TEXT     Start of range (YYYY-MM-DD or YYYY-MM-DDTHH:MM). Default:
                   now.
  --end TEXT       End of range (YYYY-MM-DD or YYYY-MM-DDTHH:MM). Default: 7
                   days from start.
  --count INTEGER  Max events to show (default: 50).
  --all            Show all events without truncation.
  --help           Show this message and exit.
```

### get

```
Usage: hassle get [OPTIONS] [FILTERS]...

  Get detailed info and recent history for matched entities.

Options:
  --count INTEGER  Max number of entities to show (default: 10).
  --all            Show all matched entities without truncation.
  --help           Show this message and exit.
```

### history

```
Usage: hassle history [OPTIONS] [FILTERS]...

  Show interleaved state history, filtered by entity ID or name substring.

Options:
  --since TEXT     Show history since this time (e.g. 6m, 2h, 1d, or ISO
                   timestamp).
  --count INTEGER  Max number of entries to show (default: 100).
  --all            Show all entries without truncation.
  --help           Show this message and exit.
```

### off

```
Usage: hassle off [OPTIONS] [FILTERS]...

  Turn off an entity.

Options:
  --help  Show this message and exit.
```

### on

```
Usage: hassle on [OPTIONS] [ARGS]...

  Turn on an entity. Accepts key=value params (e.g. brightness=200).

Options:
  --help  Show this message and exit.
```

### services

```
Usage: hassle services [OPTIONS] [TARGET]

  Browse available HA services.

  hassle services                  — list all domains
  hassle services light            — list services in a domain
  hassle services light/turn_on    — show fields for a service

Options:
  --help  Show this message and exit.
```

### set

```
Usage: hassle set [OPTIONS] [ARGS]...

  Set attributes on an entity (e.g. brightness=200 color_temp=370).

Options:
  --help  Show this message and exit.
```

### states

```
Usage: hassle states [OPTIONS] [FILTERS]...

  List entity states, optionally filtered by substring (matches entity ID or
  name).

Options:
  --help  Show this message and exit.
```

### todo

```
Usage: hassle todo [OPTIONS] [LIST...]

  Show items on a todo list. Shows pending items by default.

Options:
  --all   Show completed items too.
  --help  Show this message and exit.
```

### todo-add

```
Usage: hassle todo-add [OPTIONS] [LIST...] ITEM

  Add an item to a todo list.

Options:
  --help  Show this message and exit.
```

### todo-check

```
Usage: hassle todo-check [OPTIONS] [LIST...] ITEM

  Mark a todo item as completed.

Options:
  --help  Show this message and exit.
```

### todo-clear

```
Usage: hassle todo-clear [OPTIONS] [LIST...]

  Remove all completed items from a todo list.

Options:
  --help  Show this message and exit.
```

### todo-remove

```
Usage: hassle todo-remove [OPTIONS] [LIST...] ITEM

  Remove an item from a todo list by name.

Options:
  --help  Show this message and exit.
```

### todo-uncheck

```
Usage: hassle todo-uncheck [OPTIONS] [LIST...] ITEM

  Mark a todo item as not completed.

Options:
  --help  Show this message and exit.
```

### todos

```
Usage: hassle todos [OPTIONS] [NAME...]

  List todo lists with pending items, optionally filtered by name or entity ID substring.

Options:
  --help  Show this message and exit.
```

### toggle

```
Usage: hassle toggle [OPTIONS] [FILTERS]...

  Toggle an entity.

Options:
  --help  Show this message and exit.
```

## Configuration

`hassle` requires the following environment variables:

- `HOMEASSISTANT_URL` — base URL of your Home Assistant instance (e.g. `http://homeassistant.local:8123`)
- `HOMEASSISTANT_KEY` — a [long-lived access token](https://www.home-assistant.io/docs/authentication/#your-account-profile)
