"""Explicit optional reader features, suitable for caller preflight checks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReaderCapabilities:
    metadata: bool = False
    field_list: bool = False
    index: bool = False
    fetch_many: bool = False
