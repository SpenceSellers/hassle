import re
import sys
from datetime import datetime, timedelta, timezone

import click

from hassle import api
from hassle.cli import cli, matches_filters


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


def _coerce_value(v: str):
    import json
    try:
        return json.loads(v)
    except (json.JSONDecodeError, ValueError):
        return v


def _split_args(args: tuple) -> tuple[list[str], dict]:
    filters = [a for a in args if "=" not in a]
    params = {k: _coerce_value(v) for k, v in (a.split("=", 1) for a in args if "=" in a)}
    return filters, params


def _resolve_one(filters: list[str]):
    entities = api.get_states()
    if filters:
        exact = [e for e in entities if any(f == e.entity_id for f in filters)]
        if len(exact) == 1:
            return exact[0]
        entities = [
            e for e in entities
            if matches_filters(e.entity_id, e.attributes.get("friendly_name", ""), tuple(filters))
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


@cli.command("states")
@click.argument("filters", nargs=-1)
def states(filters):
    """List entity states, optionally filtered by substring (matches entity ID or name)."""
    entities = api.get_states()
    if filters:
        entities = [
            e for e in entities
            if matches_filters(e.entity_id, e.attributes.get("friendly_name", ""), filters)
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
            if matches_filters(e.entity_id, e.attributes.get("friendly_name", ""), filters)
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
    """Call an arbitrary HA service.

    \b
    hassle call domain/service [filters] [key=value ...]

    Values are parsed as JSON, so arrays and numbers work:
      hassle call light/turn_on kitchen brightness=200
      hassle call light/turn_on kitchen hs_color=[30,100]
    """
    if "/" not in service:
        raise click.UsageError("service must be in the form domain/service")
    domain, svc = service.split("/", 1)
    filters, params = _split_args(args)
    entity = _resolve_one(filters)
    api.call_service(domain, svc, entity.entity_id, params)
    click.echo(f"Called {service} on {entity.entity_id}.")


@cli.command("services")
@click.argument("target", required=False)
def services(target):
    """Browse available HA services.

    \b
    hassle services                  — list all domains
    hassle services light            — list services in a domain
    hassle services light/turn_on    — show fields for a service
    """
    all_services = api.get_services()
    domain_map = {entry["domain"]: entry["services"] for entry in all_services}

    if target is None:
        for domain in sorted(domain_map):
            count = len(domain_map[domain])
            click.echo(f"{domain}  ({count} service{'s' if count != 1 else ''})")
        return

    if "/" in target:
        domain, svc_name = target.split("/", 1)
        services_in_domain = domain_map.get(domain)
        if services_in_domain is None:
            raise click.ClickException(f"domain '{domain}' not found")
        svc = services_in_domain.get(svc_name)
        if svc is None:
            raise click.ClickException(f"service '{domain}/{svc_name}' not found")
        desc = svc.get("description") or svc.get("name") or ""
        click.echo(f"{domain}/{svc_name}" + (f": {desc}" if desc else ""))
        fields = svc.get("fields", {})
        if not fields:
            click.echo("  (no fields)")
        for field_name, field in fields.items():
            field_desc = field.get("description") or field.get("name") or ""
            example = field.get("example")
            required = " (required)" if field.get("required") else ""
            example_str = f"  e.g. {example}" if example is not None else ""
            click.echo(f"  {field_name}{required}: {field_desc}{example_str}")
    else:
        domain = target
        services_in_domain = domain_map.get(domain)
        if services_in_domain is None:
            raise click.ClickException(f"domain '{domain}' not found")
        for svc_name, svc in sorted(services_in_domain.items()):
            desc = svc.get("description") or svc.get("name") or ""
            field_count = len(svc.get("fields", {}))
            fields_str = f"  [{field_count} field{'s' if field_count != 1 else ''}]" if field_count else ""
            click.echo(f"{domain}/{svc_name}{fields_str}" + (f": {desc}" if desc else ""))


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
            if matches_filters(e.entity_id, e.attributes.get("friendly_name", ""), filters)
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
