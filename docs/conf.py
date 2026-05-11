# Sphinx configuration for voxy-linux developer docs.
#
# Build:   uv run sphinx-build -b html docs docs/_build/html
# Serve:   uv run sphinx-autobuild docs docs/_build/html --port 8080
# Both are exposed via `just docs` / `just docs-serve` recipes.

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

project = "voxy-linux"
author = "Dmitry Petukhov"
copyright = "2026, voxy-linux contributors"

try:
    release = _pkg_version("voxy-linux")
except PackageNotFoundError:
    release = "dev"
version = release

extensions = [
    "sphinxcontrib.mermaid",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinx_tabs.tabs",
    "sphinx_togglebutton",
    "myst_parser",
]

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md":  "markdown",
}

myst_enable_extensions = ["html_image", "colon_fence"]
myst_allow_raw_html = True

language = "en"

# -- HTML output -------------------------------------------------------------

html_theme = "shibuya"
html_static_path = ["_static"]
html_css_files = ["voxy.css"]
html_title = "voxy-linux developer docs"

html_theme_options = {
    "accent_color": "iris",
    "github_url": "https://github.com/samanddima/voxy-linux",
}
