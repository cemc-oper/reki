"""Sphinx configuration for reki documentation."""

import os
from pathlib import Path


_DOC_CACHE = Path(__file__).resolve().parents[1] / ".cache"
# Executed notebooks must reuse the repository-local cache prepared by
# ``make -C doc data`` and never create user-level test-data or GRIB indexes.
os.environ.setdefault("REKI_TEST_DATA_DIR", str(_DOC_CACHE / "test-data"))
os.environ.setdefault("REKI_INDEX_DIR", str(_DOC_CACHE / "indexes"))

project = "reki"
copyright = "2021-2026, CMA Earth System Modeling And Prediction Centre (CEMC/CMA)"
author = "developers at cemc-oper"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "myst_nb",
]

# Both reStructuredText API pages and MyST Markdown narrative/notebook pages
# are first-class source files.
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "myst-nb",
}

# Existing narrative pages use fenced MyST directives. Add extensions only as
# content needs them so syntax remains a small, reviewable vocabulary.
myst_enable_extensions = ["colon_fence"]

# Execute notebooks as documentation tests. Executed examples use frozen test
# data prepared by ``make data``; environment-specific examples must stay in
# ordinary code blocks or be added to this targeted list with a rationale.
nb_execution_mode = "force"
nb_execution_excludepatterns = []

highlight_language = "python"
pygments_style = "sphinx"
pygments_dark_style = "monokai"

language = "zh_CN"
exclude_patterns = ["_build"]

# Keep API signatures compact while placing type details where prose can
# explain them. Nitpicky mode makes unresolved API references build failures.
autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_type_aliases = {
    "Path": "pathlib.Path",
    "DataArray": "xarray.DataArray",
    "xr.DataArray": "xarray.DataArray",
}
nitpicky = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "xarray": ("https://docs.xarray.dev/en/stable/", None),
}

# These are malformed historical type strings, implementation constants, or
# alias-only references emitted by autodoc. Public symbols remain documented in
# ``development/api``; each expression is exact so new references still fail.
nitpick_ignore_regex = [
    ("py:class", r"(?:Path|DataArray|xr\.DataArray|xr\.Dataset|pd\.DataFrame|FieldQuery|GribField|LazySource|TypeAliasForwardRef|'pathlib\.Path'|'Mapping\[str|Mapping\[str|tuple\[int|reki\.core\.field_list\.FieldList|reki\.core\.field_query\.FieldQuery|reki\.core\.source_spec\.SourceSpec|reki\.readers\.grib\.reader\.GribField|reki\.sources\.LazySource)"),
    ("py:data", r"(?:DEFAULT_DOWNLOAD_DIR|SourceMaker)"),
    ("py:func", r"from_source"),
    ("py:mod", r"reki"),
]

html_theme = "pydata_sphinx_theme"

html_theme_options = {
    "github_url": "https://github.com/cemc-oper/reki",
    "header_links_before_dropdown": 5,
    "navigation_depth": 2,
    "show_nav_level": 2,
    "show_toc_level": 2,
    "navbar_align": "left",
    "navbar_start": ["navbar-logo"],
    "navbar_center": ["navbar-nav"],
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
    "secondary_sidebar_items": ["page-toc", "edit-this-page"],
    "use_edit_page_button": True,
}

html_context = {
    "github_user": "cemc-oper",
    "github_repo": "reki",
    "github_version": "main",
    "doc_path": "doc/source",
}
