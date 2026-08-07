"""Compatibility module alias for :mod:`health.legal_tools`."""

import sys

from health import legal_tools as _legal_tools

sys.modules[__name__] = _legal_tools
