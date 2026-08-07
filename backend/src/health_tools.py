"""Compatibility module alias for :mod:`health.tools`."""

import sys

from health import tools as _tools

sys.modules[__name__] = _tools
