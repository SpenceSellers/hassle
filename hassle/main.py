import click

from . import api


@click.group()
def cli():
    """hassle — a Home Assistant CLI."""


@cli.command("states")
@click.argument("filter", required=False)
def states(filter):
    """List entity states, optionally filtered by entity_id prefix."""
    entities = api.get_states()

    if filter:
        entities = [e for e in entities if e.entity_id.startswith(filter)]

    for e in entities:
        name = e.attributes.get("friendly_name", "")
        label = f"  ({name})" if name else ""
        click.echo(f"{e.entity_id}{label}: {e.state}")


@cli.command("get")
@click.argument("entity_id")
def get_state(entity_id):
    """Get the state of a single entity."""
    entity = api.get_state(entity_id)
    name = entity.attributes.get("friendly_name", "")
    label = f"  ({name})" if name else ""
    click.echo(f"{entity.entity_id}{label}: {entity.state}")


@cli.command("toggle")
@click.argument("entity_id")
def toggle(entity_id):
    """Toggle an entity (light, switch, etc.)."""
    api.toggle(entity_id)
    click.echo(f"Toggled {entity_id}.")


def main():
    cli()
