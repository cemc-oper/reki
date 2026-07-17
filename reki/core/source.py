class Source:
    """Base class for all sources.

    A source knows where the data comes from (local file, CMA HPC archive,
    CMADaaS service, memory object, ...). Sources are created through
    ``reki.from_source()`` and are transformed by the ``mutate()`` loop
    into the most concrete source before being parsed by a reader.

    This class follows the design of ``earthkit.data.sources.Source``.
    """

    name = None

    def __init__(self, **kwargs):
        self._kwargs = kwargs

    def mutate(self):
        """Transform this source into a more concrete source.

        Called repeatedly by ``from_source()`` until the returned source
        is identical to the previous one (fixed-point loop). For example,
        ``LocalSource`` mutates into ``FileSource`` once the path is
        resolved. The default implementation returns ``self``, which
        terminates the loop.

        Returns
        -------
        Source
            the mutated source, or ``self`` if no mutation is needed.
        """
        return self

    def mutate_source(self):
        """Hook for a reader to replace the source.

        Gives the reader a chance to ask the source to transform itself
        (e.g. an archive source expanding into a multi source) before
        the reader gives up. Optional; the default implementation
        returns ``None`` which means no replacement.

        Returns
        -------
        Source or None
            a replacement source, or None.
        """
        return None
