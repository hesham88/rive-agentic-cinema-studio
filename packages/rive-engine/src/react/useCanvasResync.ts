import { useEffect } from 'react';

/**
 * Keep a Rive canvas's drawing buffer in step with its CSS box.
 *
 * The bug this exists for
 * -----------------------
 * A Rive canvas has two sizes: the CSS box the browser lays out, and the
 * `width`/`height` attributes that size the WebGL drawing buffer. The runtime
 * is supposed to keep them in step, and when it does not, the canvas is left at
 * the HTML default of 300x150 and draws nothing.
 *
 * It happened here on every canvas on the landing page — fourteen of them, all
 * with live WebGL contexts, all drawing into a buffer nothing could see. The
 * failure is silent and it does not look like a layout bug: the `.riv` loads,
 * the state machine advances, inputs respond, and the only missing thing is
 * pixels. It read as "the widgets are broken" for a long time before anyone
 * measured a canvas.
 *
 * The root cause is an ordering problem the runtime cannot win on its own. It
 * sizes the buffer from the element's measured box, and on first paint an
 * unsized canvas measures zero, so it allocates zero and writes `width: 0px`
 * inline. Giving the element a CSS size afterwards does not help by itself:
 * dispatching a resize event was tried and the buffer stayed at 300x150.
 *
 * So the buffer is resynced explicitly. `resizeDrawingSurfaceToCanvas` is the
 * runtime's own API for exactly this, and calling it once after load plus on
 * every subsequent resize is what keeps a canvas correct through breakpoint
 * changes, device-pixel-ratio changes and a monitor being dragged between
 * displays.
 *
 * Paired with the `canvas` rule in `globals.css`, which supplies the CSS box
 * this reads. Both halves are needed: the rule gives the element a size, and
 * this turns that size into a buffer.
 */
export function useCanvasResync(rive: { resizeDrawingSurfaceToCanvas?: () => void } | null) {
  useEffect(() => {
    if (!rive?.resizeDrawingSurfaceToCanvas) return;

    const sync = () => rive.resizeDrawingSurfaceToCanvas?.();

    // Once now, and again after a frame. The first call runs before the
    // browser has necessarily settled layout for a canvas that just received
    // its CSS size, and a buffer sized from a stale box is the bug repeating
    // itself one tick later.
    sync();
    const raf = requestAnimationFrame(sync);

    window.addEventListener('resize', sync);
    // Catches a window dragged to a display with a different pixel ratio,
    // which changes the required buffer size without changing the CSS box.
    const dpr = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
    dpr.addEventListener?.('change', sync);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', sync);
      dpr.removeEventListener?.('change', sync);
    };
  }, [rive]);
}
