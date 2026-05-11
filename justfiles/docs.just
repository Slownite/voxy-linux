# Developer documentation (Sphinx + shibuya theme). See docs/conf.py.

# Build the docs to docs/_build/html.
docs-build:
    uv run --extra docs sphinx-build -b html docs docs/_build/html
    @echo "✅ docs/_build/html"

# Build + open in default browser.
docs: docs-build
    xdg-open docs/_build/html/index.html

# Live-reload server on http://localhost:8080 — rebuilds on file change.
docs-serve:
    uv run --extra docs sphinx-autobuild docs docs/_build/html \
        --open-browser --port 8080 \
        --ignore "docs/_build/*"

# Strict build: fail on any warning. Use in CI to keep docs clean.
docs-strict:
    uv run --extra docs sphinx-build -W -b html docs docs/_build/html

# Remove generated docs.
docs-clean:
    rm -rf docs/_build
