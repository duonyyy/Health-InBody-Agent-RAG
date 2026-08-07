"""Compatibility module alias for :mod:`jobs.tasks`."""

import sys

from jobs import tasks as _tasks

sys.modules[__name__] = _tasks
