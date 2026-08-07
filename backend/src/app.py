"""Compatibility entrypoint for ``uvicorn app:app``.

The FastAPI implementation now lives in :mod:`api.app`.
"""

from api.app import *  # noqa: F401,F403
from api.app import app
