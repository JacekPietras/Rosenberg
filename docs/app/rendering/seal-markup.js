export function sealAnnotationMarkup(seals = [], escapeHtml, personRecords = []) {
  return seals.map((seal) => {
    const x = Number(seal?.position?.split?.(',')?.[0]);
    const y = Number(seal?.position?.split?.(',')?.[1]);
    const size = Number(seal?.size);
    const width = Number.isFinite(Number(seal?.width)) ? Math.max(0, Math.min(1, Number(seal.width))) : 0;
    const wideningRotation = Number.isFinite(Number(seal?.wideningRotation)) ? Number(seal.wideningRotation) : 0;
    const rotation = Number.isFinite(Number(seal?.rotation)) ? Number(seal.rotation) : 0;
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(size) || x < 0 || x > 1 || y < 0 || y > 1 || size <= 0 || !String(seal?.person || '').trim()) return '';
    const personLabel = String(seal.person).trim();
    const reference = personLabel.match(/^\[([^\]]+)\]$/);
    const person = reference && personRecords.find((item) => item?.id === reference[1]);
    const personText = escapeHtml(person?.name || personLabel.replace(/^\[|\]$/g, ''));
    return `<span class="seal-marker"${reference ? ' data-person-reference="true"' : ''} data-size="${size}" data-width="${width}" data-widening-rotation="${wideningRotation}" data-rotation="${rotation}" style="left:${x * 100}%;top:${y * 100}%" role="img" aria-label="Seal of ${personText}" title="${personText}"><span class="seal-marker-label">${personText}</span></span>`;
  }).join('');
}
