# Dev and build recipes for voxy-linux.

# Install deps + dev extras into .venv
setup:
    uv sync --extra dev

# Run from source
run:
    uv run python -m voxy

# Run test suite
test:
    uv run pytest

# Strict type check
typecheck:
    uv run mypy --strict src/

# Build wheel into dist/
build:
    uv build

# Install built wheel via pipx
install: build
    pipx install --force dist/voxy_linux-*.whl

# Remove build artifacts
clean:
    rm -rf dist/ .venv/
