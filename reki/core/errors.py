"""Public query errors."""
class QueryError(LookupError):
    def __init__(self, query, source_summary="<unknown source>", match_count=None):
        self.query, self.source_summary, self.match_count = query, source_summary, match_count
        count = "no" if match_count == 0 else ("at least 2" if match_count is None or match_count >= 2 else str(match_count))
        super().__init__(f"{self.__class__.__name__}: {count} fields matched {query!r} in {source_summary}")
class DataNotFoundError(QueryError):
    pass
class MultipleFieldsMatchedError(QueryError):
    pass


class UnsupportedOperationError(NotImplementedError):
    """A reader does not implement a requested optional capability."""

    def __init__(self, reader, operation):
        super().__init__(f"{type(reader).__name__} does not support {operation}()")
        self.reader = type(reader).__name__
        self.operation = operation
