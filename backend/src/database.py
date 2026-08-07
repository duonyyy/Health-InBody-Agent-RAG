"""Compatibility module alias for :mod:`persistence.database`."""

import sys

from persistence import database as _database

sys.modules[__name__] = _database
