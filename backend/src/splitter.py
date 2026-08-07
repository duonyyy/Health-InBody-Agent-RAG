"""Compatibility module alias for :mod:`rag.splitter`."""

import sys

from rag import splitter as _splitter

sys.modules[__name__] = _splitter
