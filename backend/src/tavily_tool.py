"""Compatibility module alias for :mod:`integrations.tavily`."""

import sys

from integrations import tavily as _tavily

sys.modules[__name__] = _tavily
