from hassle.cli import cli
from hassle.commands import calendar, entities, todo  # noqa: F401 — registers commands


def main():
    cli()
