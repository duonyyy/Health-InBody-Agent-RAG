"""Compatibility entrypoint for the Qdrant vector reuse pipeline."""

import sys

from pipelines import reuse_qdrant_vectors as _reuse_qdrant_vectors

sys.modules[__name__] = _reuse_qdrant_vectors

if __name__ == "__main__":
    _reuse_qdrant_vectors.main()
