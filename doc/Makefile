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

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Pre-download the frozen test datasets used by executed notebooks.
# Idempotent (existing files are skipped) and downloads to the default
# cache directory; the same commands run in RTD's pre_build hook.
data:
	reki-test-data download ecmwf_ifs
	reki-test-data download ecmwf_ifs --domain global

# The API check reads supported ``__all__`` declarations and verifies that each
# symbol is both inventoried and rendered on its assigned API reference page.
api-check:
	$(PYTHON) $(API_CHECK) --inventory $(SOURCEDIR)/development/api/public-api-inventory.md --html-root $(BUILDDIR)/html

spelling:
	codespell $(SOURCEDIR)

check: html api-check spelling

.PHONY: help data api-check spelling check Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
