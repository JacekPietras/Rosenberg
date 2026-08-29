export function sealAnnotationMarkup(seals = [], escapeHtml) {
  return seals.map((seal) => {
    const x = Number(seal?.position?.split?.(',')?.[0]);
    const y = Number(seal?.position?.split?.(',')?.[1]);
    const size = Number(seal?.size);
    const width = Number.isFinite(Number(seal?.width)) ? Math.max(0, Math.min(1, Number(seal.width))) : 0;
    const wideningRotation = Number.isFinite(Number(seal?.wideningRotation)) ? Number(seal.wideningRotation) : 0;
    const rotation = Number.isFinite(Number(seal?.rotation)) ? Number(seal.rotation) : 0;
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(size) || x < 0 || x > 1 || y < 0 || y > 1 || size <= 0 || !String(seal?.person || '').trim()) return '';
    const person = escapeHtml(seal.person);
    return `<span class="seal-marker" data-size="${size}" data-width="${width}" data-widening-rotation="${wideningRotation}" data-rotation="${rotation}" style="left:${x * 100}%;top:${y * 100}%" role="img" aria-label="Seal of ${person}" title="${person}"><span class="seal-marker-label">${person}</span></span>`;
  }).join('');
}
