# GRIB metadata index and exploration

The ecCodes GRIB reader can persist a metadata-only SQLite index. The index
speeds up field discovery; it is neither a values cache nor a download cache.
No command or metadata API described here decodes GRIB values.

## Field discovery

`all()` returns an immutable `FieldList` of lazy `GribField` references in
source-file order. Python positions are zero based; legacy `sel(count=N)`
remains a one-based GRIB message ordinal and ignores the other filters.

```python
from reki import FieldQuery, from_source

reader = from_source("file", "forecast.grib2")
fields = reader.sel(FieldQuery(parameter="t", level_type="pl", level=[850, 500])).all()

assert len(fields) == 2
field = fields[0]             # lazy field reference
data = field.to_xarray()      # values are decoded here
```

`FieldList.first()` returns `None` when empty. `one()` raises
`DataNotFoundError` for zero fields and `MultipleFieldsMatchedError` for more
than one; `one_or_none()` returns `None` only for zero fields. Slicing returns
another `FieldList`, and `FieldList.concat()` retains repeated fields unless
called with `deduplicate=True`.

The following metadata-only methods never materialise an xarray object or
request `values`: `summary()`, `metadata()`, `unique()`, `head()`,
`describe()`, and `ls()`. `metadata()` / `ls()` return a DataFrame; `json()`
returns JSON-safe metadata records. Unknown metadata keys raise `KeyError`.
`where()` accepts only a `FieldQuery` or key/value filters, never Python or SQL
expressions.

`fetch_many()` is experimental. It preserves input order and duplicate
positions, shares one index session when available, and uses no more than one
header pass for an unindexed batch. Its `cardinality` may be `all`, `first`,
`one`, or `one_or_none`.

## Index policy and lifecycle

The default policy is `auto`. It reads a valid index and otherwise attempts
one build before falling back to a direct scan. `off` never reads or writes an
index; `readonly` only reads a valid one; `refresh` replaces the index and is
strict if it cannot do so.

Index root precedence is the explicit `index_dir`, `REKI_INDEX_DIR`, then
`$XDG_CACHE_HOME/reki/indexes` (or `~/.cache/reki/indexes`). The source data
directory is never used by default. Index filenames are hashes of the resolved
absolute source path and schema namespace, so paths are not exposed in the
filename.

Schema v1 is `reki-grib-index/1`. It stores safe header metadata and byte
locations only. Validity includes resolved path, device, inode, file size,
nanosecond mtime, schema/query-rule/key-set versions, supported GRIB editions,
and ecCodes major version. A stale, corrupt, unsupported, unwritable, or
lock-timed-out index falls back to direct scanning for `auto` and `readonly`.
`refresh` reports its failure without replacing a previous valid index.

Builders use a per-index POSIX advisory lock, write a uniquely named temporary
SQLite file in the final index directory, validate it, then publish with atomic
replacement. A builder checks the source fingerprint before and after scanning
and discards a changing source. These recovery paths never modify the source
GRIB file.

## CLI

```bash
reki inspect forecast.grib2 --json
reki ls forecast.grib2 --keys parameter,level_type,level,step --json
reki query forecast.grib2 --parameter t --level-type pl --level 850 --json
```

All three commands accept mutually exclusive `--no-index`,
`--read-only-index`, and `--refresh-index`, plus `--index-dir`. `--limit` and
`--offset` bound output. JSON is written only to stdout; `--verbose` writes
index diagnostics to stderr. Zero matches is a successful query with an empty
result; invalid options or keys and strict refresh failures exit with code 2.

## Reader capability matrix

| reader | metadata exploration | FieldList | persistent index | fetch_many |
| --- | --- | --- | --- | --- |
| GRIB / ecCodes | yes | yes | yes | experimental |
| GRIB / cfgrib | no | no | no | no |
| NetCDF | summary / metadata where supported | no | no | no |
| GrADS | summary / metadata where supported | no | no | no |
| unknown | no | no | no | no |

Callers can inspect the frozen `reader.capabilities` record before relying on
an optional feature. Unsupported operations raise `UnsupportedOperationError`.
