import os
import sys
from datetime import datetime

import click
import httpx

from .models import EntityState, HistoryEntry


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


def call_service(domain: str, service: str, entity_id: str, params: dict) -> list[EntityState]:
    with get_client() as client:
        resp = client.post(
            f"/services/{domain}/{service}",
            json={"entity_id": entity_id, **params},
        )
        if resp.status_code == 404:
            click.echo(f"Service {domain}/{service} not found.", err=True)
            sys.exit(1)
        resp.raise_for_status()
        return [EntityState(**e) for e in resp.json()]
