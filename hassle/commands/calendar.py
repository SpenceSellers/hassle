import re
import sys
from datetime import datetime, timedelta

import click

from hassle import api
from hassle.cli import cli


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
        dow = start_dt.strftime("%a")
        if (end_dt - start_dt).days <= 1:
            return f"{dow} {s} (all day)"
        return f"{dow} {s} – {e} (all day)"
    s = datetime.fromisoformat(start["dateTime"])
    e = datetime.fromisoformat(end["dateTime"])
    dow = s.strftime("%a")
    if s.date() == e.date():
        return f"{dow} {s.strftime('%Y-%m-%d %H:%M')} – {e.strftime('%H:%M')}"
    return f"{dow} {s.strftime('%Y-%m-%d %H:%M')} – {e.strftime('%Y-%m-%d %H:%M')}"


def _resolve_calendar(filters: list[str]):
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
    calendars = api.get_calendars()
    if name:
        calendars = [
            c for c in calendars
            if any(f.lower() in c.entity_id.lower() or f.lower() in c.name.lower() for f in name)
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
    now = datetime.now().astimezone()

    if start_str:
        d = _parse_event_dt(start_str)
        start_dt = datetime.fromisoformat(d["dateTime"]) if "dateTime" in d else datetime.strptime(d["date"], "%Y-%m-%d").replace(tzinfo=now.tzinfo)
    else:
        start_dt = now

    if end_str:
        d = _parse_event_dt(end_str)
        end_dt = datetime.fromisoformat(d["dateTime"]) if "dateTime" in d else datetime.strptime(d["date"], "%Y-%m-%d").replace(tzinfo=now.tzinfo)
    else:
        end_dt = start_dt + timedelta(days=7)

    calendars = api.get_calendars()
    if calendar:
        calendars = [
            c for c in calendars
            if any(f.lower() in c.entity_id.lower() or f.lower() in c.name.lower() for f in calendar)
        ]
    if not calendars:
        click.echo("No matching calendars found.", err=True)
        return

    all_events = []
    for cal in calendars:
        for ev in api.get_calendar_events(cal.entity_id, start_dt, end_dt):
            all_events.append((cal, ev))

    def _sort_key(item):
        ev = item[1]
        if "dateTime" in ev.start:
            return datetime.fromisoformat(ev.start["dateTime"])
        return datetime.strptime(ev.start["date"], "%Y-%m-%d").replace(tzinfo=now.tzinfo)

    all_events.sort(key=_sort_key)

    total = len(all_events)
    limit = None if show_all else (count or 50)
    displayed = all_events if limit is None else all_events[:limit]

    click.echo(f"Events {start_dt.strftime('%a %Y-%m-%d')} – {end_dt.strftime('%a %Y-%m-%d')}:")
    for cal, ev in displayed:
        time_str = _format_event_time(ev.start, ev.end)
        cal_label = f"  [{cal.name}]" if len(calendars) > 1 else ""
        click.echo(f"{time_str}  {ev.summary}{cal_label}")
        if ev.description:
            click.echo(f"  description: {ev.description}")
        if ev.location:
            click.echo(f"  location: {ev.location}")

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
    click.echo(f"Created event '{summary}' on {cal.name}: {_format_event_time(start, end)}")
