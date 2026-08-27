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
