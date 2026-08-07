"""Compatibility entrypoint for the relocated import pipeline."""

import sys

from pipelines import import_data as _import_data

sys.modules[__name__] = _import_data

if __name__ == "__main__":
    _import_data.main()
