import sys

import click

from hassle import api
from hassle.cli import cli, matches_filters


def _resolve_todo_list(filters: list[str]):
    entities = [e for e in api.get_states() if e.entity_id.startswith("todo.")]
    if filters:
        exact = [e for e in entities if any(f == e.entity_id for f in filters)]
        if len(exact) == 1:
            return exact[0]
        entities = [
            e for e in entities
            if matches_filters(e.entity_id, e.attributes.get("friendly_name", ""), tuple(filters))
        ]
    if not entities:
        click.echo("Error: no matching todo lists found.", err=True)
        sys.exit(1)
    if len(entities) > 1:
        click.echo(f"Error: filter matched {len(entities)} todo lists — be more specific:", err=True)
        for e in entities:
            name = e.attributes.get("friendly_name", "")
            click.echo(f"  {e.entity_id} ({name})", err=True)
        sys.exit(1)
    return entities[0]


@cli.command("todos")
@click.argument("name", metavar="[NAME...]", nargs=-1)
def list_todos(name):
    """List todo lists with pending items, optionally filtered by name or entity ID substring."""
    entities = [e for e in api.get_states() if e.entity_id.startswith("todo.")]
    if name:
        entities = [
            e for e in entities
            if matches_filters(e.entity_id, e.attributes.get("friendly_name", ""), name)
        ]
    for e in entities:
        friendly = e.attributes.get("friendly_name", "")
        count = e.attributes.get("items_not_completed", "")
        suffix = f"  ({count} pending)" if count != "" else ""
        click.echo(f"{e.entity_id}: {friendly}{suffix}")
        for item in api.get_todo_items(e.entity_id, status=["needs_action"]):
            click.echo(f"  {item.summary}")


@cli.command("todo")
@click.argument("list_name", metavar="[LIST...]", nargs=-1)
@click.option("--all", "show_all", is_flag=True, default=False, help="Show completed items too.")
def show_todo(list_name, show_all):
    """Show items on a todo list. Shows pending items by default."""
    entity = _resolve_todo_list(list(list_name))
    status = ["needs_action", "completed"] if show_all else ["needs_action"]
    items = api.get_todo_items(entity.entity_id, status=status)
    friendly = entity.attributes.get("friendly_name", entity.entity_id)
    pending = [i for i in items if i.status == "needs_action"]
    done = [i for i in items if i.status == "completed"]
    header = f"{friendly} — {len(pending)} pending"
    if show_all and done:
        header += f", {len(done)} completed"
    click.echo(header + ":")
    for item in pending:
        click.echo(f"  {item.summary}")
    if show_all and done:
        click.echo("  completed:")
        for item in done:
            click.echo(f"    {item.summary}")


@cli.command("todo-add")
@click.argument("list_name", metavar="[LIST...]", nargs=-1)
@click.argument("item")
def todo_add(list_name, item):
    """Add an item to a todo list."""
    entity = _resolve_todo_list(list(list_name))
    api.add_todo_item(entity.entity_id, item)
    click.echo(f"Added '{item}' to {entity.attributes.get('friendly_name', entity.entity_id)}.")


@cli.command("todo-check")
@click.argument("list_name", metavar="[LIST...]", nargs=-1)
@click.argument("item")
def todo_check(list_name, item):
    """Mark a todo item as completed."""
    entity = _resolve_todo_list(list(list_name))
    api.update_todo_item(entity.entity_id, item, status="completed")
    click.echo(f"Checked off '{item}' on {entity.attributes.get('friendly_name', entity.entity_id)}.")


@cli.command("todo-uncheck")
@click.argument("list_name", metavar="[LIST...]", nargs=-1)
@click.argument("item")
def todo_uncheck(list_name, item):
    """Mark a todo item as not completed."""
    entity = _resolve_todo_list(list(list_name))
    api.update_todo_item(entity.entity_id, item, status="needs_action")
    click.echo(f"Unchecked '{item}' on {entity.attributes.get('friendly_name', entity.entity_id)}.")


@cli.command("todo-remove")
@click.argument("list_name", metavar="[LIST...]", nargs=-1)
@click.argument("item")
def todo_remove(list_name, item):
    """Remove an item from a todo list by name."""
    entity = _resolve_todo_list(list(list_name))
    api.remove_todo_item(entity.entity_id, item)
    click.echo(f"Removed '{item}' from {entity.attributes.get('friendly_name', entity.entity_id)}.")


@cli.command("todo-clear")
@click.argument("list_name", metavar="[LIST...]", nargs=-1)
def todo_clear(list_name):
    """Remove all completed items from a todo list."""
    entity = _resolve_todo_list(list(list_name))
    api.remove_completed_todo_items(entity.entity_id)
    click.echo(f"Cleared completed items from {entity.attributes.get('friendly_name', entity.entity_id)}.")
