"""Safe error codes for retrieval dependencies."""


class RetrievalDependencyError(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)
