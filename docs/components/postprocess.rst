postprocess.py
==============

A small rule-based transform applied to every transcript before it
reaches the inserter. Entirely local — no LLM, no network.

Source: ``src/voxy/postprocess.py``.

Pipeline
--------

For each transcript, in order:

1. **Filler strip** *(opt-in)*. If ``strip_fillers = true``, remove the
   words in ``fillers`` (default: ``["uh", "um", "hmm"]``) as whole
   words, case-insensitive.
2. **Punctuation commands** *(default on)*. Apply the ``substitutions``
   table — a phrase → replacement map. Lets you say "comma", "period",
   "new line", "new paragraph" and have them turn into the literal
   characters.
3. **Auto-capitalise** *(default on)*. Capitalise the first letter of
   each sentence after the substitutions.

Config
------

See :doc:`../configuration` for the full TOML schema. The
``substitutions`` table is open-ended — add your own:

.. code-block:: toml

   [post_processing.substitutions]
   "smiley face"  = ":)"
   "shrug"        = "¯\\_(ツ)_/¯"

Substitutions match case-insensitively but the replacement is inserted
verbatim.

Why not an LLM?
---------------

LLM cleanup adds 100-500 ms of latency, needs a model load (or a
network round-trip), and trades determinism for "vibes-correct"
rewriting. voxy's design goal is *predictable* dictation; rule-based
processing fits that better. The hooks are there if someone wants to
prototype an LLM-backed profile, but the default ships rules.
