// Keep a linked entry in place while lazy images change the document layout.
// The caller must clean up before replacing the rendered screen.
export function keepEntryInView(target, content) {
  const win = target.ownerDocument.defaultView;
  let frame = null;
  let active = true;
  target.scrollIntoView({ block: 'start', behavior: 'instant' });
  const top = target.getBoundingClientRect().top;

  const update = () => {
    frame = null;
    if (!active) return;
    if (!target.isConnected) { cleanup(); return; }
    const shift = target.getBoundingClientRect().top - top;
    if (Math.abs(shift) > 0.5) win.scrollBy({ top: shift, behavior: 'instant' });
  };
  const schedule = () => {
    if (active && frame === null) frame = win.requestAnimationFrame(update);
  };
  const onKey = (event) => {
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown', 'Home', 'End', ' ', 'Tab'].includes(event.key)) cleanup();
  };
  const observer = win.ResizeObserver ? new win.ResizeObserver(schedule) : null;
  function cleanup() {
    active = false;
    observer?.disconnect();
    if (frame !== null) win.cancelAnimationFrame(frame);
    frame = null;
    content.removeEventListener('load', schedule, true);
    content.removeEventListener('error', schedule, true);
    win.removeEventListener('wheel', cleanup, true);
    win.removeEventListener('touchstart', cleanup, true);
    win.removeEventListener('pointerdown', cleanup, true);
    win.removeEventListener('keydown', onKey, true);
    win.removeEventListener('hashchange', cleanup);
    win.removeEventListener('popstate', cleanup);
  }
  observer?.observe(content);
  content.addEventListener('load', schedule, true);
  content.addEventListener('error', schedule, true);
  win.addEventListener('wheel', cleanup, { capture: true, passive: true });
  win.addEventListener('touchstart', cleanup, { capture: true, passive: true });
  win.addEventListener('pointerdown', cleanup, { capture: true, passive: true });
  win.addEventListener('keydown', onKey, true);
  win.addEventListener('hashchange', cleanup);
  win.addEventListener('popstate', cleanup);
  return cleanup;
}
