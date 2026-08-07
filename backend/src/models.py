"""Compatibility module alias for :mod:`persistence.models`."""

import sys

from persistence import models as _models

sys.modules[__name__] = _models
