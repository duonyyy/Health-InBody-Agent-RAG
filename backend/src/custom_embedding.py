"""Compatibility module alias for the relocated :mod:`llm.embedding` module."""

import sys

from llm import embedding as _embedding

sys.modules[__name__] = _embedding
