import 'justfiles/dev.just'
import 'justfiles/docs.just'
import 'justfiles/stats.just'

# Default recipe: list every available task with its description.
# Triggered when `just` is run with no arguments.
default:
    @just --list

# Install shell tab-completion for `just` itself. Detects the current
# shell from $SHELL and writes the completion script to the canonical
# user-local location. Re-open the shell (or `source` its rc) to
# activate. Supports bash, zsh, fish, elvish, powershell, nushell.
install-completions shell=`basename "${SHELL:-bash}"`:
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{shell}}" in
        bash)
            dst="${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions/just"
            ;;
        zsh)
            dst="${XDG_DATA_HOME:-$HOME/.local/share}/zsh/site-functions/_just"
            ;;
        fish)
            dst="${XDG_CONFIG_HOME:-$HOME/.config}/fish/completions/just.fish"
            ;;
        elvish|powershell|nushell)
            dst="${XDG_DATA_HOME:-$HOME/.local/share}/just/completions.{{shell}}"
            ;;
        *)
            echo "unsupported shell: {{shell}}" >&2
            echo "pass one of: bash | zsh | fish | elvish | powershell | nushell" >&2
            exit 2
            ;;
    esac
    mkdir -p "$(dirname "$dst")"
    just --completions {{shell}} > "$dst"
    echo "installed: $dst"
    case "{{shell}}" in
        bash) echo "→ open a new shell, or: source $dst" ;;
        zsh)  echo "→ ensure fpath includes $(dirname "$dst") in ~/.zshrc, then: compinit" ;;
        fish) echo "→ pick up automatically on next prompt" ;;
    esac
