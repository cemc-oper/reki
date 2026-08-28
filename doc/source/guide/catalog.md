# Dataset catalog

Dataset catalogs bind a stable logical dataset ID to a serializable
`SourceSpec`. Loading or resolving a catalog never opens a source, scans a
directory, or makes a network request.

```python
import reki

catalog = reki.load_catalog()
source_spec = catalog.resolve("my_dataset").source
```

A catalog document is strict YAML (or JSON):

```yaml
api_version: reki.catalog/v1
datasets:
  - id: my_dataset
    aliases: [MY-DATASET]
    source:
      name: local
      args: [my_dataset/grib2/orig]
      kwargs: {data_class: od}
```

The precedence order is explicit catalog/call input, user catalog, installed
`reki.catalogs` plugins, then the built-in catalog. A higher layer replaces an
entire record, not individual fields. The user file is
`$XDG_CONFIG_HOME/reki/catalog.yaml` (or `~/.config/reki/catalog.yaml`); set
`REKI_CATALOG_PATH` to use another file. Use `user=False` or `plugins=False`
when a reproducible diagnostic must exclude those layers.

```console
reki catalog list --no-user --no-plugins
reki catalog show my_dataset
reki catalog resolve MY-DATASET
```

CLI output redacts sensitive source kwargs. It reports the winning layer and
any record it replaced, but never constructs the source.

The builtin catalog includes the operational local bindings for CMA-GFS,
CMA-MESO-3KM, CMA-MESO-1KM, CMA-TYM, CMA-GEPS and CMA-REPS. Historical
``CMA-MESO`` resolves to ``cma_meso_3km``; use ``CMA-MESO-1KM`` to select the
one-kilometre dataset explicitly.

For a task-provided directory and filename, use the ``file-pattern`` source.
It accepts only ``{start_time_label}``, ``{forecast_hour}``, and
``{forecast_hour_label}`` substitutions; expressions and filesystem checks
are deliberately not performed during rendering.
