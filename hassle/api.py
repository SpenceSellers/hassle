import os
import sys
from datetime import datetime
import click
import httpx

from .models import Calendar, CalendarEvent, EntityState, HistoryEntry, TodoItem


def get_client() -> httpx.Client:
    url = os.environ.get("HOMEASSISTANT_URL", "").rstrip("/")
    key = os.environ.get("HOMEASSISTANT_KEY", "")
    if not url or not key:
        click.echo("Error: HOMEASSISTANT_URL and HOMEASSISTANT_KEY must be set.", err=True)
        sys.exit(1)
    return httpx.Client(
        base_url=f"{url}/api",
        headers={"Authorization": f"Bearer {key}"},
        timeout=10,
    )


def get_states() -> list[EntityState]:
    with get_client() as client:
        resp = client.get("/states")
        resp.raise_for_status()
        return [EntityState(**e) for e in resp.json()]



def get_history(entity_ids: list[str], since: datetime | None = None) -> list[HistoryEntry]:
    params = {"filter_entity_id": ",".join(entity_ids)}
    path = f"/history/period/{since.isoformat()}" if since else "/history/period"
    with get_client() as client:
        resp = client.get(path, params=params)
        resp.raise_for_status()
        entries = []
        for timeline in resp.json():
            entity_id = timeline[0]["entity_id"] if timeline else None
            for e in timeline:
                e.setdefault("entity_id", entity_id)
                e.setdefault("attributes", {})
                entries.append(HistoryEntry(**e))
        return sorted(entries, key=lambda e: e.last_changed, reverse=True)


def get_calendars() -> list[Calendar]:
    with get_client() as client:
        resp = client.get("/calendars")
        resp.raise_for_status()
        return [Calendar(**c) for c in resp.json()]


def get_calendar_events(entity_id: str, start: datetime, end: datetime) -> list[CalendarEvent]:
    with get_client() as client:
        resp = client.get(
            f"/calendars/{entity_id}",
            params={"start": start.isoformat(), "end": end.isoformat()},
        )
        resp.raise_for_status()
        return [CalendarEvent(**e) for e in resp.json()]


def create_calendar_event(entity_id: str, data: dict) -> None:
    """Create a calendar event via the calendar.create_event service."""
    payload: dict = {"entity_id": entity_id, "summary": data["summary"]}
    start, end = data["start"], data["end"]
    if "date" in start:
        payload["start_date"] = start["date"]
        payload["end_date"] = end["date"]
    else:
        dt = datetime.fromisoformat(start["dateTime"])
        payload["start_date_time"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        dt = datetime.fromisoformat(end["dateTime"])
        payload["end_date_time"] = dt.strftime("%Y-%m-%d %H:%M:%S")
    if data.get("description"):
        payload["description"] = data["description"]
    if data.get("location"):
        payload["location"] = data["location"]
    with get_client() as client:
        resp = client.post("/services/calendar/create_event", json=payload)
        resp.raise_for_status()



def get_todo_items(entity_id: str, status: list[str] | None = None) -> list[TodoItem]:
    payload: dict = {"entity_id": entity_id}
    if status:
        payload["status"] = status
    with get_client() as client:
        resp = client.post("/services/todo/get_items?return_response", json=payload)
        resp.raise_for_status()
        items = resp.json()["service_response"][entity_id]["items"]
        return [TodoItem(**item) for item in items]


def add_todo_item(entity_id: str, item: str) -> None:
    with get_client() as client:
        resp = client.post("/services/todo/add_item", json={"entity_id": entity_id, "item": item})
        resp.raise_for_status()


def update_todo_item(entity_id: str, item: str, **kwargs) -> None:
    with get_client() as client:
        resp = client.post("/services/todo/update_item", json={"entity_id": entity_id, "item": item, **kwargs})
        resp.raise_for_status()


def remove_todo_item(entity_id: str, item: str) -> None:
    with get_client() as client:
        resp = client.post("/services/todo/remove_item", json={"entity_id": entity_id, "item": item})
        resp.raise_for_status()


def remove_completed_todo_items(entity_id: str) -> None:
    with get_client() as client:
        resp = client.post("/services/todo/remove_completed_items", json={"entity_id": entity_id})
        resp.raise_for_status()


def get_services() -> list[dict]:
    with get_client() as client:
        resp = client.get("/services")
        resp.raise_for_status()
        return resp.json()


def call_service(domain: str, service: str, entity_id: str, params: dict) -> list[EntityState]:
    with get_client() as client:
        resp = client.post(
            f"/services/{domain}/{service}",
            json={"entity_id": entity_id, **params},
        )
        if not resp.is_success:
            try:
                detail = resp.json().get("message", resp.text)
            except Exception:
                detail = resp.text
            click.echo(f"Error {resp.status_code}: {detail}", err=True)
            sys.exit(1)
        return [EntityState(**e) for e in resp.json()]
