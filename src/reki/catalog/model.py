"""Immutable configuration facts; public semantics belong to cedarkit_query."""

from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping

from cedarkit_query import QueryError


def freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value


def thaw(value):
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [thaw(v) for v in value]
    return value


@dataclass(frozen=True)
class LoadedResource:
    value: object
    reference: Mapping
    sha256: str
    base_dir: object

    def snapshot(self, role, *, backend=None):
        data = self.value.to_dict()
        return {
            "role": role,
            "id": data["id"],
            "api_version": data["api_version"],
            "version": data["version"],
            "sha256": self.sha256,
            "reference": thaw(self.reference),
            **({"backend": backend} if backend else {}),
        }


@dataclass(frozen=True)
class SourceConfiguration:
    """An I04 construction plan, with no data availability or capability claim."""

    source: Mapping
    scope: object
    execution_defaults: Mapping
    member_roles: Mapping
    cemc_member_roles: bool
    definitions: tuple
    origins: Mapping
    layout: object = None
    member_numbering: Mapping | None = None
    parameters: Mapping | None = None
    mappings: tuple = ()
    product: Mapping | None = None
    fallback_layout: tuple = ()

    def member_role(self, member):
        if type(member) is not int or member < 0:
            raise QueryError(
                "invalid_query", "/member", "non-negative integer required"
            )
        return self.member_roles.get(
            str(member),
            ("control" if member == 0 else "perturbation")
            if self.cemc_member_roles
            else None,
        )

    def report_context(self):
        """Known facts only. Connection config/client never enter public reports."""
        source = {"kind": self.source["kind"]}
        if "dataset" in self.source:
            source["dataset"] = self.source["dataset"]
        if self.product is not None:
            source.update(
                product=self.product["id"], product_version=self.product["version"]
            )
        return {
            **({"dataset": self.source["dataset"]} if "dataset" in self.source else {}),
            "scope": self.scope.to_dict(),
            "source": source,
            "execution_defaults": thaw(self.execution_defaults),
            "member_roles": thaw(self.member_roles),
            "definitions": [thaw(d) for d in self.definitions],
            "origins": thaw(self.origins),
        }
