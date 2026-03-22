import re
import sys
from datetime import date, datetime, timedelta, timezone

import click

from . import api


_RELATIVE_RE = re.compile(r"^(\d+)(s|m|h|d)$")
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _parse_since(value: str) -> datetime:
    m = _RELATIVE_RE.match(value)
    if m:
        seconds = int(m.group(1)) * _UNITS[m.group(2)]
        return datetime.now(timezone.utc) - timedelta(seconds=seconds)
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise click.BadParameter(f"cannot parse '{value}' — use e.g. '6m', '2h', '1d', or an ISO timestamp")


def _time_ago(dt: datetime) -> str:
    seconds = int((datetime.now(timezone.utc) - dt).total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


@click.group(context_settings={"max_content_width": 9999})
def cli():
    """hassle — a Home Assistant CLI."""


@cli.command("states")
@click.argument("filters", nargs=-1)
def states(filters):
    """List entity states, optionally filtered by substring (matches entity ID or name)."""
    entities = api.get_states()

    if filters:
        entities = [
            e for e in entities
            if _matches_filters(e.entity_id, e.attributes.get("friendly_name", ""), filters)
        ]

    for e in entities:
        name = e.attributes.get("friendly_name", "")
        label = f"  ({name})" if name else ""
        click.echo(f"{e.entity_id}{label}: {e.state}")


@cli.command("get")
@click.argument("filters", nargs=-1)
@click.option("--count", default=None, type=int, help="Max number of entities to show (default: 10).")
@click.option("--all", "show_all", is_flag=True, default=False, help="Show all matched entities without truncation.")
def get(filters, count, show_all):
    """Get detailed info and recent history for matched entities."""
    entities = api.get_states()

    if filters:
        entities = [
            e for e in entities
            if _matches_filters(e.entity_id, e.attributes.get("friendly_name", ""), filters)
        ]

    if not entities:
        click.echo("No matching entities found.", err=True)
        return

    total = len(entities)
    limit = None if show_all else (count or 10)
    if limit is not None:
        entities = entities[:limit]

    all_entries = api.get_history([e.entity_id for e in entities])

    history_map: dict[str, list] = {}
    for entry in all_entries:
        history_map.setdefault(entry.entity_id, []).append(entry)

    for i, e in enumerate(entities):
        if i > 0:
            click.echo()
        name = e.attributes.get("friendly_name", "")
        label = f" ({name})" if name else ""
        click.echo(f"{e.entity_id}{label}: {e.state}")
        for key, val in e.attributes.items():
            if key == "friendly_name":
                continue
            click.echo(f"  {key}: {val}")
        all_entity_entries = history_map.get(e.entity_id, [])
        entries = all_entity_entries[:20]
        if entries:
            click.echo("  history:")
            for entry in entries:
                ts = entry.last_changed.strftime("%Y-%m-%d %H:%M:%S")
                ago = _time_ago(entry.last_changed)
                click.echo(f"    {ts} ({ago}): {entry.state}")
            if len(all_entity_entries) > 20:
                extra = len(all_entity_entries) - 20
                click.echo(
                    f"  ({extra} more history entries — run: hassle history {e.entity_id})",
                    err=True,
                )

    if limit is not None and total > limit:
        truncated = total - limit
        click.echo(
            f"{truncated} entities truncated; {total} entities total. "
            f"use --count <int> to see more. use --all to see all.",
            err=True,
        )


def _matches_filters(entity_id: str, friendly_name: str, filters: tuple[str, ...]) -> bool:
    return any(
        f.lower() in entity_id.lower() or f.lower() in friendly_name.lower()
        for f in filters
    )


def _split_args(args: tuple[str, ...]) -> tuple[list[str], dict[str, str]]:
    """Split positional args into filter terms and key=value params."""
    filters = [a for a in args if "=" not in a]
    params = dict(a.split("=", 1) for a in args if "=" in a)
    return filters, params


def _resolve_one(filters: list[str]):
    """Resolve filters to exactly one entity, or exit with an error."""
    entities = api.get_states()
    if filters:
        exact = [e for e in entities if any(f == e.entity_id for f in filters)]
        if len(exact) == 1:
            return exact[0]
        entities = [
            e for e in entities
            if _matches_filters(e.entity_id, e.attributes.get("friendly_name", ""), tuple(filters))
        ]
    if not entities:
        click.echo("Error: no matching entities found.", err=True)
        sys.exit(1)
    if len(entities) > 1:
        click.echo(f"Error: filter matched {len(entities)} entities — be more specific:", err=True)
        for e in entities[:100]:
            name = e.attributes.get("friendly_name", "")
            label = f"  ({name})" if name else ""
            click.echo(f"  {e.entity_id}{label}", err=True)
        if len(entities) > 100:
            click.echo(f"  ... and {len(entities) - 100} more", err=True)
        sys.exit(1)
    return entities[0]


def _infer_set_service(domain: str, params: dict) -> str:
    match domain:
        case "light":
            return "turn_on"
        case "climate":
            if "temperature" in params: return "set_temperature"
            if "hvac_mode" in params: return "set_hvac_mode"
            if "preset_mode" in params: return "set_preset_mode"
            if "humidity" in params: return "set_humidity"
        case "cover":
            if "position" in params: return "set_cover_position"
            if "tilt_position" in params: return "set_cover_tilt_position"
        case "fan":
            if "percentage" in params: return "set_percentage"
            if "direction" in params: return "set_direction"
            if "preset_mode" in params: return "set_preset_mode"
        case "input_number" | "number":
            return "set_value"
        case "input_select" | "select":
            return "select_option"
        case "media_player":
            if "volume_level" in params: return "volume_set"
            if "source" in params: return "select_source"
            if "sound_mode" in params: return "select_sound_mode"
    param_list = " ".join(f"{k}={v}" for k, v in params.items())
    raise click.ClickException(
        f"don't know which service to call for domain '{domain}' with params {list(params.keys())}.\n"
        f"use: hassle call {domain}/<service> {param_list}"
    )


@cli.command("on")
@click.argument("args", nargs=-1)
def turn_on(args):
    """Turn on an entity. Accepts key=value params (e.g. brightness=200)."""
    filters, params = _split_args(args)
    entity = _resolve_one(filters)
    api.call_service("homeassistant", "turn_on", entity.entity_id, params)
    click.echo(f"Turned on {entity.entity_id}.")


@cli.command("off")
@click.argument("filters", nargs=-1)
def turn_off(filters):
    """Turn off an entity."""
    entity = _resolve_one(list(filters))
    api.call_service("homeassistant", "turn_off", entity.entity_id, {})
    click.echo(f"Turned off {entity.entity_id}.")


@cli.command("toggle")
@click.argument("filters", nargs=-1)
def toggle(filters):
    """Toggle an entity."""
    entity = _resolve_one(list(filters))
    states = api.call_service("homeassistant", "toggle", entity.entity_id, {})
    new_state = next((s.state for s in states if s.entity_id == entity.entity_id), None)
    suffix = f" → {new_state}" if new_state else ""
    click.echo(f"Toggled {entity.entity_id}{suffix}.")


@cli.command("set")
@click.argument("args", nargs=-1)
def set_attr(args):
    """Set attributes on an entity (e.g. brightness=200 color_temp=370)."""
    filters, params = _split_args(args)
    if not params:
        raise click.UsageError("provide at least one key=value param")
    entity = _resolve_one(filters)
    domain = entity.entity_id.split(".")[0]
    service = _infer_set_service(domain, params)
    api.call_service(domain, service, entity.entity_id, params)
    click.echo(f"Set {entity.entity_id}: {', '.join(f'{k}={v}' for k, v in params.items())}.")


@cli.command("call")
@click.argument("service")
@click.argument("args", nargs=-1)
def call(service, args):
    """Call an arbitrary HA service: hassle call domain/service [filters] [key=value ...]"""
    if "/" not in service:
        raise click.UsageError("service must be in the form domain/service")
    domain, svc = service.split("/", 1)
    filters, params = _split_args(args)
    entity = _resolve_one(filters)
    api.call_service(domain, svc, entity.entity_id, params)
    click.echo(f"Called {service} on {entity.entity_id}.")


@cli.command("history")
@click.argument("filters", nargs=-1)
@click.option("--since", default=None, help="Show history since this time (e.g. 6m, 2h, 1d, or ISO timestamp).")
@click.option("--count", default=None, type=int, help="Max number of entries to show (default: 100).")
@click.option("--all", "show_all", is_flag=True, default=False, help="Show all entries without truncation.")
def history(filters, since, count, show_all):
    """Show interleaved state history, filtered by entity ID or name substring."""
    entities = api.get_states()

    if filters:
        entities = [
            e for e in entities
            if _matches_filters(e.entity_id, e.attributes.get("friendly_name", ""), filters)
        ]

    if not entities:
        click.echo("No matching entities found.", err=True)
        return

    since_dt = _parse_since(since) if since else None
    entries = api.get_history([e.entity_id for e in entities], since=since_dt)

    name_map = {e.entity_id: e.attributes.get("friendly_name", "") for e in entities}

    limit = None if show_all else (count or 100)
    total = len(entries)
    displayed = entries if limit is None else entries[:limit]

    for entry in displayed:
        name = name_map.get(entry.entity_id, entry.attributes.get("friendly_name", ""))
        label = f"  ({name})" if name else ""
        ts = entry.last_changed.strftime("%Y-%m-%d %H:%M:%S")
        ago = _time_ago(entry.last_changed)
        click.echo(f"{ts} ({ago})  {entry.entity_id}{label}: {entry.state}")

    if limit is not None and total > limit:
        truncated = total - limit
        click.echo(
            f"{truncated} records truncated; {total} records total. "
            f"use --count <int> to see more. use --all to see all.",
            err=True,
        )




def _parse_event_dt(value: str) -> dict:
    """Parse a date or datetime string into a HA calendar start/end dict."""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return {"date": value}
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            local_tz = datetime.now().astimezone().tzinfo
            return {"dateTime": dt.replace(tzinfo=local_tz).isoformat()}
        except ValueError:
            continue
    raise click.BadParameter(f"cannot parse '{value}' — use YYYY-MM-DD or YYYY-MM-DDTHH:MM")


def _format_event_time(start: dict, end: dict) -> str:
    if "date" in start:
        s = start["date"]
        e = end["date"]
        end_dt = datetime.strptime(e, "%Y-%m-%d").date()
        start_dt = datetime.strptime(s, "%Y-%m-%d").date()
        if (end_dt - start_dt).days <= 1:
            return f"{s} (all day)"
        return f"{s} – {e} (all day)"
    s = datetime.fromisoformat(start["dateTime"])
    e = datetime.fromisoformat(end["dateTime"])
    if s.date() == e.date():
        return f"{s.strftime('%Y-%m-%d %H:%M')} – {e.strftime('%H:%M')}"
    return f"{s.strftime('%Y-%m-%d %H:%M')} – {e.strftime('%Y-%m-%d %H:%M')}"


def _resolve_calendar(filters: list[str]):
    """Resolve filters to exactly one calendar, or exit with an error."""
    calendars = api.get_calendars()
    if filters:
        exact = [c for c in calendars if any(f == c.entity_id for f in filters)]
        if len(exact) == 1:
            return exact[0]
        calendars = [
            c for c in calendars
            if any(f.lower() in c.entity_id.lower() or f.lower() in c.name.lower() for f in filters)
        ]
    if not calendars:
        click.echo("Error: no matching calendars found.", err=True)
        sys.exit(1)
    if len(calendars) > 1:
        click.echo(f"Error: filter matched {len(calendars)} calendars — be more specific:", err=True)
        for c in calendars:
            click.echo(f"  {c.entity_id} ({c.name})", err=True)
        sys.exit(1)
    return calendars[0]


@cli.command("calendars")
@click.argument("name", metavar="[NAME...]", nargs=-1)
def list_calendars(name):
    """List calendars, optionally filtered by name or entity ID substring."""
    filters = name
    calendars = api.get_calendars()
    if filters:
        calendars = [
            c for c in calendars
            if any(f.lower() in c.entity_id.lower() or f.lower() in c.name.lower() for f in filters)
        ]
    for c in calendars:
        click.echo(f"{c.entity_id}: {c.name}")


@cli.command("events")
@click.argument("calendar", metavar="[CALENDAR...]", nargs=-1)
@click.option("--start", "start_str", default=None, help="Start of range (YYYY-MM-DD or YYYY-MM-DDTHH:MM). Default: now.")
@click.option("--end", "end_str", default=None, help="End of range (YYYY-MM-DD or YYYY-MM-DDTHH:MM). Default: 7 days from start.")
@click.option("--count", default=None, type=int, help="Max events to show (default: 50).")
@click.option("--all", "show_all", is_flag=True, default=False, help="Show all events without truncation.")
def list_events(calendar, start_str, end_str, count, show_all):
    """List events from one or more calendars (matched by name or entity ID substring). Shows next 7 days by default."""
    filters = calendar
    now = datetime.now().astimezone()
    if start_str:
        d = _parse_event_dt(start_str)
        if "dateTime" in d:
            start_dt = datetime.fromisoformat(d["dateTime"])
        else:
            start_dt = datetime.strptime(d["date"], "%Y-%m-%d").replace(tzinfo=now.tzinfo)
    else:
        start_dt = now

    if end_str:
        d = _parse_event_dt(end_str)
        if "dateTime" in d:
            end_dt = datetime.fromisoformat(d["dateTime"])
        else:
            end_dt = datetime.strptime(d["date"], "%Y-%m-%d").replace(tzinfo=now.tzinfo)
    else:
        end_dt = start_dt + timedelta(days=7)

    calendars = api.get_calendars()
    if filters:
        calendars = [
            c for c in calendars
            if any(f.lower() in c.entity_id.lower() or f.lower() in c.name.lower() for f in filters)
        ]
    if not calendars:
        click.echo("No matching calendars found.", err=True)
        return

    all_events = []
    for cal in calendars:
        for ev in api.get_calendar_events(cal.entity_id, start_dt, end_dt):
            all_events.append((cal, ev))

    # Sort by start time
    def _sort_key(item):
        ev = item[1]
        if "dateTime" in ev.start:
            return datetime.fromisoformat(ev.start["dateTime"])
        return datetime.strptime(ev.start["date"], "%Y-%m-%d").replace(tzinfo=now.tzinfo)

    all_events.sort(key=_sort_key)

    total = len(all_events)
    limit = None if show_all else (count or 50)
    displayed = all_events if limit is None else all_events[:limit]

    for cal, ev in displayed:
        time_str = _format_event_time(ev.start, ev.end)
        cal_label = f"  [{cal.name}]" if len(calendars) > 1 else ""
        click.echo(f"{time_str}  {ev.summary}{cal_label}")
        if ev.description:
            click.echo(f"  description: {ev.description}")
        if ev.location:
            click.echo(f"  location: {ev.location}")
        if ev.uid:
            click.echo(f"  uid: {ev.uid}")

    if limit is not None and total > limit:
        truncated = total - limit
        click.echo(
            f"{truncated} events truncated; {total} total. use --count <int> or --all to see more.",
            err=True,
        )


@cli.command("add-event")
@click.argument("calendar", metavar="[CALENDAR...]", nargs=-1)
@click.option("--summary", "-s", required=True, help="Event title.")
@click.option("--start", "start_str", required=True, help="Start date/time (YYYY-MM-DD for all-day, YYYY-MM-DDTHH:MM for timed).")
@click.option("--end", "end_str", default=None, help="End date/time. Defaults to 1h after start (timed) or next day (all-day).")
@click.option("--description", "-d", default=None, help="Event description.")
@click.option("--location", "-l", default=None, help="Event location.")
def add_event(calendar, summary, start_str, end_str, description, location):
    """Create a calendar event. CALENDAR identifies the target calendar by name or entity ID substring."""
    cal = _resolve_calendar(list(calendar))
    start = _parse_event_dt(start_str)

    if end_str:
        end = _parse_event_dt(end_str)
    elif "date" in start:
        next_day = (datetime.strptime(start["date"], "%Y-%m-%d") + timedelta(days=1)).date()
        end = {"date": next_day.isoformat()}
    else:
        end_dt = datetime.fromisoformat(start["dateTime"]) + timedelta(hours=1)
        end = {"dateTime": end_dt.isoformat()}

    data: dict = {"summary": summary, "start": start, "end": end}
    if description:
        data["description"] = description
    if location:
        data["location"] = location

    api.create_calendar_event(cal.entity_id, data)
    time_str = _format_event_time(start, end)
    click.echo(f"Created event '{summary}' on {cal.name}: {time_str}")



def main():
    cli()
