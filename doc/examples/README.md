# Documentation examples

Each public `*.py` file in this directory is an E1/E2 standalone example. It must use only
public reki imports, assert its teaching contract, print deterministic JSON, and have a matching
`<name>.expected.json` file. `make -C doc examples-check` runs every example in an isolated
temporary working directory and index directory after `make -C doc data` has prepared frozen
assets.

Use `_helpers.py` for frozen asset paths and temporary indexes. Tutorial pages that show a
multi-line program should include the corresponding file from this directory, so displayed and
executed code have one source of truth.
