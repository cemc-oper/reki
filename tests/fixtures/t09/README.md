# T09 frozen GRIB2 execution fixtures

The generator creates 44 small GRIB2 files from the ecCodes `regular_ll_pl_grib2` sample. These are **synthetic software test data** and are generated in a temporary directory during tests; no GRIB2 files belong in Git. They do not represent a CMA, ECMWF, or other operational product. The separate `cedarkit-test-data` project continues to own its frozen ECMWF release assets.

`expected.json` records each file's SHA256, byte length, field identity, grid shape, native unit, and first/last decoded values. The baseline is one 2026-08-30 00Z cycle on a 3×4 regular latitude/longitude grid: 13 leads (0–72h every 6h), two pressure levels (500 and 850 hPa), and three explicitly encoded members (control 0, perturbations 1 and 2). There are 39 member/lead files and 78 expected fields. Level order alternates across files; `scenarios.shuffled.files` reverses the file list to check identity independent of order.

The five files in `cases/` provide:

| Case | Use |
|---|---|
| `duplicate.grib2` | Add to baseline: a second source for lead 24h, 850 hPa, perturbation 1. |
| `missing_replacement.grib2` | Replace `baseline/f048_m2.grib2`: lead 48h, 850 hPa, perturbation 2 is absent. |
| `grid_conflict.grib2` | Add to baseline: the same lead 30h / 500 hPa / perturbation 2 identity on a 3×5 grid. |
| `unit_pair.grib2` | Native `gh` and `z` fields at one time/level/member with `gpm` and `m**2 s**-2`; these are separate native parameters and must not be silently combined or converted. |
| `resource_updated.grib2` | Replace `baseline/f042_m0.grib2` at the same active path: identities stay the same, values increase by 10 and SHA256 changes. |

To generate the files for manual inspection outside the repository, or verify the reference manifest, run from `repo/reki` with the test dependency group:

```bash
uv run --offline --group test python tests/fixtures/t09/generate.py --output-dir /tmp/reki-t09-grib
uv run --offline --group test python tests/fixtures/t09/generate.py --check
uv run --offline --group test pytest tests/readers/grib/test_t09_frozen_fixture.py -q
```

The reference manifest was generated with ecCodes API version **2.48.2**. With that version, `--check` verifies every pinned SHA256 and size. A different ecCodes version still compares the declared field descriptors, while encoder-specific byte hashes are reported as unchecked. The pytest case actually decodes the generated files and checks field values with either version. To intentionally refresh the reference manifest after an encoder upgrade, run the generator with `--output-dir` and `--update-manifest`, then review every changed hash and field value. Manual generation requires an explicit output directory; `files/` and `*.grib2` are ignored as an additional guard.
