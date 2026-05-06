# Dev and build recipes for voxy-linux.

# Install deps + dev extras into .venv
setup:
    uv sync --extra dev

# Run from source
run:
    uv run python -m voxy

# Wipe config so the next launch triggers the first-run prompt
first_run:
    rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/voxy/config.toml"
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

# Build Arch Linux package (.pkg.tar.zst) into dist/
# Version from latest git tag (YYYY.M.D.N format); bumps N if tag exists for today
build-arch:
    #!/usr/bin/env bash
    set -euo pipefail
    REPO_ROOT=$(git rev-parse --show-toplevel)
    TODAY=$(date +%Y.%-m.%-d)
    LATEST=$(git tag --sort=-version:refname | grep -E '^[0-9]{4}\.' | head -1 || true)
    if [[ "$LATEST" == "$TODAY".* ]]; then
        N=$(echo "$LATEST" | awk -F. '{print $NF}')
        PKGVER="$TODAY.$((N + 1))"
    else
        PKGVER="$TODAY.1"
    fi
    echo "Version: $PKGVER"
    TMPDIR=$(mktemp -d)
    ORIG_VER=$(grep '^version = ' "$REPO_ROOT/pyproject.toml" | head -1 | cut -d'"' -f2)
    trap 'sed -i "s/^version = .*/version = \"$ORIG_VER\"/" "$REPO_ROOT/pyproject.toml"; rm -rf "$TMPDIR"' EXIT
    sed -i "s/^version = .*/version = \"$PKGVER\"/" "$REPO_ROOT/pyproject.toml"
    (cd "$REPO_ROOT" && uv build --wheel)
    WHEEL_NAME="voxy_linux-${PKGVER}-py3-none-any.whl"
    WHEEL_ABS="$REPO_ROOT/dist/$WHEEL_NAME"
    SHA256=$(sha256sum "$WHEEL_ABS" | awk '{print $1}')
    cp "$REPO_ROOT/PKGBUILD" "$TMPDIR/PKGBUILD"
    cp "$WHEEL_ABS" "$TMPDIR/$WHEEL_NAME"
    sed -i \
        -e "s|pkgver=.*|pkgver=$PKGVER|" \
        -e "s|sha256sums=(.*)|sha256sums=(\"$SHA256\")|" \
        "$TMPDIR/PKGBUILD"
    cd "$TMPDIR" && makepkg -f --nodeps --noconfirm 2>&1
    cp "$TMPDIR"/*.pkg.tar.zst "$REPO_ROOT/dist/"
    echo "Arch package: dist/$(ls $TMPDIR/*.pkg.tar.zst | xargs basename)"

# Remove build artifacts
clean:
    rm -rf dist/ build/

# Wipe everything including venv
purge: clean
    rm -rf .venv/
