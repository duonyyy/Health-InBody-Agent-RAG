"""Naming rules shared by Qdrant administration commands."""

import argparse
import re


COLLECTION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,254}$")


def validate_collection_name(value: str) -> str:
    """Validate a Qdrant collection or alias name for CLI use."""
    if not COLLECTION_NAME_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "Collection name must be 3-255 characters using letters, numbers, "
            "dot, underscore, or hyphen"
        )
    return value
