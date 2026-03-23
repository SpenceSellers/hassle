import click


@click.group(context_settings={"max_content_width": 9999})
def cli():
    """hassle — a Home Assistant CLI."""


def matches_filters(entity_id: str, friendly_name: str, filters: tuple) -> bool:
    return any(
        f.lower() in entity_id.lower() or f.lower() in friendly_name.lower()
        for f in filters
    )
