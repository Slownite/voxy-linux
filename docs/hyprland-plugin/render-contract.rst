Rendering contract
==================

The plugin draws zero-lag outlines because it injects pass elements at a
very specific point in Hyprland's render loop. Breaking the ordering
below silently breaks the outline.

The contract
------------

In Hyprland's ``src/render/Renderer.cpp``:

.. code-block:: cpp

    // upstream Hyprland, ~Renderer.cpp:1465
    Event::bus()->m_events.render.stage.emit(RENDER_LAST_MOMENT);
    endRender();        // → m_renderPass.render(...)

We:

1. Subscribe to ``Event::bus()->m_events.render.stage`` and react when the
   stage is ``RENDER_LAST_MOMENT``.
2. Append a ``CTexPassElement`` to ``g_pHyprRenderer->m_renderPass`` —
   *not* a direct ``g_pHyprOpenGL->renderRect`` (those get blitted over by
   the subsequent ``endRender()``).
3. Hyprland's ``endRender()`` runs immediately after our handler returns
   and flushes ``m_renderPass.render()``, which draws every queued pass
   element — including ours — in order.

Result: the outline lands in the same frame as the cursor.

Where this breaks
-----------------

If a future Hyprland release moves ``m_renderPass.render()`` to *before*
the ``RENDER_LAST_MOMENT`` emit, our element queues into an already-flushed
pass and never renders. Symptom: plugin loads cleanly, no errors, no
outline. The fix is to subscribe to ``RENDER_PRE_WINDOWS`` (or whichever
new stage runs before flush) and re-test ordering.

Why not just hook ``CHyprOpenGLImpl::renderRect``?
--------------------------------------------------

Considered. Rejected because:

- It's a private internal call; the function signature has churned
  between Hyprland 0.43 → 0.54.
- It would render *inside* every rect call site, including some we don't
  want to paint on top of (e.g. cursor itself).
- The pass-element approach is the documented extension surface for
  custom drawing.
