import os
import sys

import click
import httpx

from .models import EntityState


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


def get_state(entity_id: str) -> EntityState:
    with get_client() as client:
        resp = client.get(f"/states/{entity_id}")
        if resp.status_code == 404:
            click.echo(f"Entity not found: {entity_id}", err=True)
            sys.exit(1)
        resp.raise_for_status()
        return EntityState(**resp.json())


def toggle(entity_id: str) -> None:
    domain = entity_id.split(".")[0]
    with get_client() as client:
        resp = client.post(
            f"/services/{domain}/toggle",
            json={"entity_id": entity_id},
        )
        if resp.status_code == 404:
            click.echo(f"Service {domain}/toggle not found.", err=True)
            sys.exit(1)
        resp.raise_for_status()
