"""CMADaaS MUSIC remote source, backed by ``nuwe-cmadaas``.

Two modes are supported (mutually exclusive):

- **low-level**: ``interface_id`` + ``params`` + ``return_type``, mapping
  directly onto ``CMADaaSClient.callAPI_to_*`` methods;
- **high-level**: ``kind`` naming a semantic function of
  ``nuwe_cmadaas.model`` / ``nuwe_cmadaas.obs`` (e.g. ``"model_grid"``).

Error semantics: the low-level client does not raise on request errors
(the error is embedded in ``response.request.error_code``), and the
high-level functions return a ``MusicError`` object instead of raising.
Both are unified here into :class:`CMADAASError`.

Note: this source is the *remote* MUSIC retrieval path. Reading CMADaaS
data from a mounted disk on CMA HPC is a different path: use the
``local`` source with ``data_class="cmadaas"`` configs instead.
"""

from importlib import import_module
from pathlib import Path

from reki.core import Source
from reki.sources import get_source


class CMADAASError(Exception):
    """A CMADaaS MUSIC request failed.

    Carries the MUSIC ``error_code`` (0 means success; local exceptions
    are mapped to -10001 by nuwe-cmadaas) and the error message.
    """

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"CMADaaS error {code}: {message}")


#: low-level return_types delivered as in-memory objects (cmadaas reader).
MEMORY_RETURN_TYPES = ("gridArray2D", "gridScalar2D", "gridVector2D", "array2D")
#: return_types answered with a URL to download.
URL_RETURN_TYPES = ("fileList",)
#: return_types already saved to local files by the client.
FILE_RETURN_TYPES = ("saveAsFile", "downFile")
#: known return_types that are not wrapped.
UNSUPPORTED_RETURN_TYPES = ("serializedStr", "dataBlock")

#: high-level kind -> (module, function) in nuwe_cmadaas.
HIGH_LEVEL_KINDS = {
    "model_grid": ("nuwe_cmadaas.model", "retrieve_model_grid"),
    "model_point": ("nuwe_cmadaas.model", "retrieve_model_point"),
    "model_file": ("nuwe_cmadaas.model", "download_model_file"),
    "obs_station": ("nuwe_cmadaas.obs", "retrieve_obs_station"),
    "obs_grid": ("nuwe_cmadaas.obs", "retrieve_obs_grid"),
    "obs_upper_air": ("nuwe_cmadaas.obs", "retrieve_obs_upper_air"),
    "obs_file": ("nuwe_cmadaas.obs", "download_obs_file"),
}


def _import_module(name: str):
    """Import a nuwe_cmadaas submodule, with a helpful error if missing."""
    try:
        return import_module(name)
    except ImportError as e:
        raise ImportError(
            f"CMADaaS support requires nuwe-cmadaas "
            f"(pip install reki[cmadaas]): {e}"
        ) from e


def _check_error(response) -> None:
    """Raise CMADAASError if the response carries a non-zero error code."""
    request = getattr(response, "request", None)
    if request is not None and request.error_code != 0:
        raise CMADAASError(code=request.error_code, message=request.error_message)


class CmadaasSource(Source):
    """Retrieve data from the CMADaaS MUSIC service.

    Parameters
    ----------
    interface_id
        MUSIC interface id, e.g. ``"getNafpEleGrid"`` (low-level mode).
    params
        request parameters dict for the interface (low-level mode).
    kind
        high-level semantic function name, one of
        ``"model_grid"`` / ``"model_point"`` / ``"model_file"`` /
        ``"obs_station"`` / ``"obs_grid"`` / ``"obs_upper_air"`` /
        ``"obs_file"``. Exactly one of ``interface_id`` and ``kind``
        must be given.
    config
        CMADaaS config (dict or file path), forwarded to nuwe-cmadaas.
    client
        an existing ``CMADaaSClient``; when given, ``config`` is ignored.
    return_type
        low-level mode only: which ``callAPI_to_*`` method to call,
        e.g. ``"gridArray2D"`` (default), ``"array2D"``, ``"fileList"``,
        ``"saveAsFile"``, ``"downFile"``.
    **kwargs
        high-level mode: forwarded to the retrieve function (e.g.
        ``data_code`` / ``parameter`` / ``start_time`` / ``level``).
    """

    def __init__(
            self,
            interface_id: str = None,
            params: dict = None,
            *,
            kind: str = None,
            config=None,
            client=None,
            return_type: str = "gridArray2D",
            **kwargs,
    ):
        super().__init__(**kwargs)
        if (interface_id is None) == (kind is None):
            raise ValueError(
                "exactly one of 'interface_id' (low-level mode) and "
                "'kind' (high-level mode) must be given"
            )
        self.interface_id = interface_id
        self.params = params
        self.kind = kind
        self.return_type = return_type
        self._config = config
        self._client = client

    def mutate(self):
        if self.kind is not None:
            return self._mutate_high_level()
        return self._mutate_low_level()

    def _mutate_low_level(self) -> Source:
        if self.return_type in UNSUPPORTED_RETURN_TYPES:
            raise NotImplementedError(
                f"CMADaaS return_type {self.return_type!r} is not supported"
            )
        known = MEMORY_RETURN_TYPES + URL_RETURN_TYPES + FILE_RETURN_TYPES
        if self.return_type not in known:
            raise ValueError(
                f"unknown CMADaaS return_type: {self.return_type!r}"
            )

        music = _import_module("nuwe_cmadaas.music")
        client = music.get_or_create_client(self._config, self._client)
        api = getattr(client, f"callAPI_to_{self.return_type}")
        response = api(self.interface_id, self.params)
        _check_error(response)

        if self.return_type in MEMORY_RETURN_TYPES:
            return get_source("memory", response, reader="cmadaas")
        if self.return_type in URL_RETURN_TYPES:
            file_url = response.files_info[0].file_url
            return get_source("url", file_url)
        # FILE_RETURN_TYPES: already saved to disk by the client
        file_path = response.files_info[0].save_path
        return get_source("file", file_path)

    def _mutate_high_level(self) -> Source:
        if self.kind not in HIGH_LEVEL_KINDS:
            raise ValueError(
                f"unknown CMADaaS kind: {self.kind!r}, "
                f"expected one of {sorted(HIGH_LEVEL_KINDS)}"
            )
        module_name, func_name = HIGH_LEVEL_KINDS[self.kind]
        module = _import_module(module_name)
        music = _import_module("nuwe_cmadaas.music")

        retrieve = getattr(module, func_name)
        result = retrieve(config=self._config, client=self._client, **self._kwargs)

        # high-level functions signal errors by returning MusicError
        if isinstance(result, music.MusicError):
            raise CMADAASError(code=result.code, message=result.message)

        if isinstance(result, (str, Path)):
            return get_source("file", result)
        if isinstance(result, (list, tuple)):
            if len(result) == 1:
                return get_source("file", result[0])
            raise NotImplementedError(
                f"CMADaaS kind {self.kind!r} returned {len(result)} files; "
                f"multi-file sources are not supported yet"
            )
        return get_source("memory", result)

    def __repr__(self):
        if self.kind is not None:
            return f"CmadaasSource(kind={self.kind!r})"
        return f"CmadaasSource({self.interface_id!r})"


source = CmadaasSource
