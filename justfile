import 'justfiles/dev.just'
import 'justfiles/docs.just'
import 'justfiles/stats.just'

# Default recipe: list every available task with its description.
# Triggered when `just` is run with no arguments.
default:
    @just --list
