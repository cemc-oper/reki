# Native Request CLI

Use `reki request explain request.json` to inspect a declaration without reading its fields, `reki request list request.json` to scan the original source, and `reki request read request.json output.nc` to write the selected fields on a compatible grid. The input is a native Request JSON or YAML document.

Successful requests exit with status 0 and write the explanation or report to stdout. A public Request, query, source, or output I/O error exits with status 1 and emits a `cedarkit.error/v1` JSON object on the final stderr line. Read that line if the backend also emits diagnostics. The object includes `code`, `path`, `message`, and `context`. A completeness error includes its full `report`. Failed requests leave stdout empty. Click usage errors, such as missing arguments or unknown options, keep their usage diagnostic and exit status 2.

`reki request read` stages the NetCDF file beside the destination and replaces the destination only after the write succeeds. Output I/O errors use the JSON Pointer `/output`.

`reki inspect`, `reki ls` and `reki query` also expose file metadata for local exploration.
