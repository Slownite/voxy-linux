# Repo stats recipes — pure Python (src/voxy + tests/)
# Invoked as `just --justfile stats.just <recipe>`.

# Resolve scope name to grep -E path filter. Empty scope => ".*" (match all).
_scope_filter scope:
    #!/usr/bin/env bash
    case "{{ scope }}" in
        "")     echo ".*" ;;
        src)    echo "^src/" ;;
        tests)  echo "^tests/" ;;
        *) echo "unknown scope: {{ scope }}" >&2; exit 2 ;;
    esac

# Count lines of Python source code. Optional: scope=src|tests to restrict.
count_lines scope="":
    #!/usr/bin/env bash
    set -e
    filter=$(just --justfile stats.just _scope_filter "{{ scope }}")
    n=$(git ls-files -z '*.py' | tr '\0' '\n' | grep -E "$filter" | tr '\n' '\0' | xargs -0 wc -l 2>/dev/null | tail -1 | awk '{print ($1+0)}')
    printf "%-6s %8d\n" ".py" "$n"
    echo "------------------"
    printf "%-6s %8d\n" "total" "$n"

# Top N source files by line count descending. Optional scope filter.
top_files n="20" scope="":
    #!/usr/bin/env bash
    set -e
    filter=$(just --justfile stats.just _scope_filter "{{ scope }}")
    git ls-files -z '*.py' \
        | tr '\0' '\n' \
        | grep -E "$filter" \
        | tr '\n' '\0' \
        | xargs -0 wc -l 2>/dev/null \
        | grep -v ' total$' \
        | sort -rn \
        | head -n {{ n }}

# Module surface: list all public modules and entry points.
modules:
    #!/usr/bin/env bash
    set -e
    echo "=== Package modules (src/voxy/) ==="
    git ls-files 'src/voxy/*.py' | grep -v __pycache__ | sort | while read -r f; do
        lines=$(wc -l < "$f")
        printf "%-40s %5d lines\n" "$f" "$lines"
    done
    echo ""
    echo "=== Test modules (tests/) ==="
    git ls-files 'tests/test_*.py' | sort | while read -r f; do
        lines=$(wc -l < "$f")
        printf "%-40s %5d lines\n" "$f" "$lines"
    done

# Test-to-source ratio.
test_ratio:
    #!/usr/bin/env bash
    set -e
    printf "%-12s %10s %10s %8s\n" "subsys" "src_loc" "test_loc" "ratio"
    echo "----------------------------------------------"
    src=$(git ls-files -z 'src/voxy/*.py' | tr '\0' '\n' | grep -v __pycache__ | tr '\n' '\0' | xargs -0 wc -l 2>/dev/null | tail -1 | awk '{print ($1+0)}')
    tst=$(git ls-files -z 'tests/test_*.py' | tr '\0' '\n' | tr '\n' '\0' | xargs -0 wc -l 2>/dev/null | tail -1 | awk '{print ($1+0)}')
    if [ "$src" -gt 0 ]; then
        ratio=$(awk -v s="$src" -v t="$tst" 'BEGIN {printf "%.2f", t/s}')
    else
        ratio="n/a"
    fi
    printf "%-12s %10d %10d %8s\n" "voxy" "$src" "$tst" "$ratio"

# TODO/FIXME/XXX/HACK markers.
todos:
    #!/usr/bin/env bash
    set -e
    pattern='TODO|FIXME|XXX|HACK'
    counts_out=$(git ls-files -z '*.py' \
        | tr '\0' '\n' \
        | tr '\n' '\0' \
        | xargs -0 grep -cE "$pattern" 2>/dev/null \
        | awk -F: '$2>0' || true)
    declare -A counts
    for sub in src tests other; do counts[$sub]=0; done
    while IFS=: read -r f hits; do
        [ -z "$f" ] && continue
        case "$f" in
            src/*)   counts[src]=$((counts[src]+hits)) ;;
            tests/*) counts[tests]=$((counts[tests]+hits)) ;;
            *)       counts[other]=$((counts[other]+hits)) ;;
        esac
    done <<< "$counts_out"
    total=0
    printf "%-10s %6s\n" "subsys" "count"
    echo "-----------------"
    for sub in src tests other; do
        printf "%-10s %6d\n" "$sub" "${counts[$sub]}"
        total=$((total + counts[$sub]))
    done
    echo "-----------------"
    printf "%-10s %6d\n" "total" "$total"
    if [ -n "$counts_out" ]; then
        echo ""
        echo "=== Top 10 files by marker count ==="
        printf '%s\n' "$counts_out" | sort -t: -k2 -rn | head -10
    fi

# Top N files by commit count (churn hotspots). Optional since="30 days ago".
churn n="20" since="":
    #!/usr/bin/env bash
    set -e
    args=()
    if [ -n "{{ since }}" ]; then
        args+=(--since="{{ since }}")
    fi
    git log "${args[@]}" --format= --name-only \
        | grep -E '\.py$' \
        | sort | uniq -c | sort -rn | head -n {{ n }}

# Dependency counts from pyproject.toml.
deps:
    #!/usr/bin/env bash
    set -e
    echo "=== Python ==="
    if [ -f pyproject.toml ]; then
        direct=$(awk '/^\[project\]/{in_proj=1} in_proj && /^dependencies = \[/,/^\]/{print}' pyproject.toml | grep -cE '^\s*"' || true)
        dev=$(awk '/^\[project\.optional-dependencies\]/{in_dev=1} in_dev && /^dev = \[/,/^\]/{print}' pyproject.toml | grep -cE '^\s*"' || true)
        printf "%-18s %6d\n" "direct deps" "$direct"
        printf "%-18s %6d\n" "dev deps" "$dev"
    fi
