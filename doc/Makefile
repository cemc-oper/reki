# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = source
BUILDDIR      = build
PYTHON        ?= python
API_CHECK     = ../scripts/check_public_api_docs.py
DOC_CACHE_DIR = $(CURDIR)/.cache
DOC_DATA_DIR  = $(DOC_CACHE_DIR)/test-data
DOC_INDEX_DIR = $(DOC_CACHE_DIR)/indexes
DOC_DATA_CHECK = ../scripts/check_documentation_data.py

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Pre-download frozen assets into a repository-local, ignored cache. Never
# populate the user-level test-data or GRIB index directories during docs jobs.
data:
	mkdir -p "$(DOC_DATA_DIR)" "$(DOC_INDEX_DIR)"
	REKI_INDEX_DIR="$(DOC_INDEX_DIR)" reki-test-data download ecmwf_ifs --output "$(DOC_DATA_DIR)"
	REKI_INDEX_DIR="$(DOC_INDEX_DIR)" reki-test-data download ecmwf_ifs --variant time --output "$(DOC_DATA_DIR)"
	REKI_INDEX_DIR="$(DOC_INDEX_DIR)" reki-test-data download ecmwf_ifs --variant ensemble --output "$(DOC_DATA_DIR)"
	REKI_INDEX_DIR="$(DOC_INDEX_DIR)" reki-test-data download ecmwf_ifs --variant layers --output "$(DOC_DATA_DIR)"
	REKI_INDEX_DIR="$(DOC_INDEX_DIR)" reki-test-data download ecmwf_ifs --variant global --output "$(DOC_DATA_DIR)"

data-check:
	REKI_INDEX_DIR="$(DOC_INDEX_DIR)" $(PYTHON) "$(DOC_DATA_CHECK)" --cache-dir "$(DOC_DATA_DIR)" --index-dir "$(DOC_INDEX_DIR)" --doc-dir "$(CURDIR)"

# The API check reads supported ``__all__`` declarations and verifies that each
# symbol is both inventoried and rendered on its assigned API reference page.
api-check:
	$(PYTHON) $(API_CHECK) --inventory $(SOURCEDIR)/development/api/public-api-inventory.md --html-root $(BUILDDIR)/html

spelling:
	codespell $(SOURCEDIR)

check: data data-check html api-check spelling

.PHONY: help data data-check api-check spelling check Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
