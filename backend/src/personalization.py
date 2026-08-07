"""Compatibility module alias for :mod:`persistence.personalization`."""

import sys

from persistence import personalization as _personalization

sys.modules[__name__] = _personalization
