transcriber.py
==============

``faster-whisper`` wrapper. CTranslate2 backend — 2–4× faster than
``openai-whisper`` on CPU with the same accuracy.

Source: ``src/voxy/transcriber.py``.

Model loading
-------------

Models are downloaded lazily into ``~/.cache/voxy/models/`` on first use
and cached forever. The first-run prompt in ``__main__.py`` lets you
pick a size up-front and pre-fetches it, so you don't see a multi-minute
hang on the first hotkey press.

Auto size selection
-------------------

``model.size = "auto"`` picks based on hardware:

- **GPU available** → ``small``
- **CPU with AVX2 + VNNI** (recent Intel / Zen 4) → ``small``
- **CPU with AVX2** → ``base``
- **older CPU** → ``tiny``

The selected size is logged at startup
(``voxy: auto-selected model size = small``).

Manual override:

.. code-block:: toml

   [model]
   size = "medium"

Valid sizes: ``tiny``, ``base``, ``small``, ``medium``, ``large-v1``,
``large-v2``, ``large-v3``, plus the corresponding ``.en`` variants.

CPU vs CUDA
-----------

``model.device``:

- ``auto`` — use GPU if found, fall back silently to CPU.
- ``cuda`` — require GPU; warn and fall back to CPU if none is present.
- ``cpu`` — always CPU.

On GPU the compute type is chosen automatically:
``int8_float16`` on Turing+, ``float16`` on Pascal+,
``float32`` fallback.

``HF_TOKEN``
------------

If Hugging Face rate-limits the model download on first run, set
``HF_TOKEN`` (or ``huggingface-cli login``) in your environment to
authenticate.
