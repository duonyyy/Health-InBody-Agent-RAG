"""Compatibility entrypoint for the missing-vector pipeline."""

import sys

from pipelines import import_missing_vectors as _import_missing_vectors

sys.modules[__name__] = _import_missing_vectors

if __name__ == "__main__":
    _import_missing_vectors.main()
