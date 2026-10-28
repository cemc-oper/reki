"""Internal adapter for the actual nuwe RetGridArray2D client boundary.

No production interface/product is registered here. Offline tests inject HTTP
responses into the real client and exercise its native protobuf decoder. The
explicit single-field contract remains responsible for identity/completeness.
"""

from dataclasses import dataclass

from cedarkit_query import QueryError, SourceError
from reki.catalog.model import freeze
from .common import metadata_error
from .nuwe_wire import profile_for, validate_parameters


@dataclass(frozen=True)
class NuweInvocation:
    """Bind the exact raw return object to this invocation, not DataArray attrs."""

    interface_id: str
    method: str
    parameters: object
    response: object

    def __post_init__(self):
        object.__setattr__(self, "parameters", freeze(self.parameters))


class NuweGridTransport:
    """Adapt an explicitly supplied client; its HTTP session stays caller-owned."""

    def __init__(self, client, contract):
        from importlib.metadata import version
        from nuwe_cmadaas.music.client import CMADaaSClient

        if not isinstance(client, CMADaaSClient):
            raise QueryError(
                "invalid_config", "/source", "expected a nuwe CMADaaSClient"
            )
        if contract.method != "callAPI_to_gridArray2D":
            raise QueryError(
                "unsupported",
                "/source/interface_contract",
                "this adapter only implements callAPI_to_gridArray2D",
                {"reason": "translation_unavailable"},
            )
        self.profile = profile_for(contract)
        self.client, self.contract, self._closed = client, contract, False
        self.retrieval_check = freeze(
            {
                "status": "pending",
                "message": "Raw grid structure is known; product-level identity, full retrieval and snapshot evidence remain unverified",
            }
        )
        self.origin = "nuwe-cmadaas@" + version("nuwe-cmadaas")

    def validate_parameters(self, parameters):
        from .cmadaas import validate_call_parameters

        validate_call_parameters(parameters)
        validate_parameters(self.profile, parameters)

    def close(self):
        # CMADaaSClient creates no owned Session and has no close operation.
        # Never close a caller's injected HTTP transport/session.
        self._closed = True

    def request(self, interface, method, parameters):
        from nuwe_cmadaas.music.data import GridArray2D
        from nuwe_cmadaas.music import errors

        if self._closed:
            raise SourceError("io_error", "", "service transport is closed")
        if (interface, method) != (self.contract.interface_id, self.contract.method):
            raise QueryError(
                "invalid_config",
                "/source/interface_contract",
                "invocation differs from its exact contract",
            )
        self.validate_parameters(parameters)
        snapshot = dict(parameters)
        actual = dict(snapshot)
        raw = self.client.callAPI_to_gridArray2D(interface, actual)
        if actual != snapshot:
            metadata_error(
                "inconsistent_native_metadata",
                "client mutated the actual business request",
            )
        if not isinstance(raw, GridArray2D):
            metadata_error(
                "unsupported_native_encoding",
                "client did not return its contracted raw grid object",
            )
        try:
            raw.raise_for_error()
        except errors.CMADaaSAuthenticationError as exc:
            raise SourceError(
                "authentication_failed", "", "service authentication failed"
            ) from exc
        except errors.CMADaaSDecodeError as exc:
            raise SourceError(
                "decode_failed", "", "service protobuf/grid decoding failed"
            ) from exc
        except errors.CMADaaSTransportError as exc:
            import requests

            code = "timeout" if isinstance(exc.cause, requests.Timeout) else "io_error"
            raise SourceError(code, "", "service transport access failed") from exc
        except errors.CMADaaSRequestError as exc:
            raise SourceError(
                "service_error", "", "service rejected the request"
            ) from exc
        if raw.lat_count <= 0 or raw.lon_count <= 0:
            metadata_error(
                "missing_native_metadata",
                "empty raw grid has no contracted field identity; absence needs a separate proven path",
            )
        try:
            array = raw.to_xarray()
        except ValueError as exc:
            raise SourceError(
                "decode_failed", "", "service grid structure is inconsistent"
            ) from exc
        # Client metadata/attrs include copied request values, not native facts.
        # Only response-derived unit and coordinates survive in the value array.
        array.attrs = {"units": raw.units}
        invocation = NuweInvocation(interface, method, snapshot, raw)
        return {
            "response_kind": "RetGridArray2D",
            "record_count": 1,
            "metadata": {},
            "data": array,
            "unit": raw.units,
            "raw_response": raw,
            "invocation": invocation,
        }
