import { sealAnnotationMarkup } from '../rendering/seal-markup.js';
import { escapeHtml } from '../rendering/html.js';
import { positionSealCrop } from './seal-annotations.js';

const SEAL_TYPES = new Set(['contrepalle', 'swans', 'helm', 'full']);

export function setupImageLightbox({ state, repository, rerender }) {
  const $ = (selector) => document.querySelector(selector);
  const lightbox = $('#image-lightbox');
  const image = $('#image-lightbox-image');
  const stage = $('#image-lightbox-stage');
  const annotations = $('#image-lightbox-annotations');
  const preview = $('#image-lightbox-seal-preview');
  const previewCrop = preview?.querySelector('.seal-crop');
  const previewImage = preview?.querySelector('img');
  const previewName = preview?.querySelector('.image-lightbox-seal-preview-name');
  const closeButton = $('#image-lightbox-close');
  if (!lightbox || !image || !stage || !annotations || !closeButton) return;

  const editable = !location.hostname.endsWith('github.io');
  const saveStatus = $('#image-lightbox-save-status');
  let context = null;
  let selectedIndex = null;
  let drag = null;
  let magnifierPoint = null;
  let saveQueue = Promise.resolve();
  const currentSeals = () => context?.node?.seals || [];
  const setStatus = (message, error = false) => { if (saveStatus) { saveStatus.textContent = message; saveStatus.classList.toggle('error', error); } };
  const point = (event) => { const rect = annotations.getBoundingClientRect(); return { x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) }; };
  const updateGeometry = () => {
    if (!image.naturalWidth || !image.naturalHeight) return;
    const scale = Math.min(stage.clientWidth / image.naturalWidth, stage.clientHeight / image.naturalHeight);
    const width = image.naturalWidth * scale; const height = image.naturalHeight * scale;
    annotations.style.left = `${(stage.clientWidth - width) / 2}px`; annotations.style.top = `${(stage.clientHeight - height) / 2}px`;
    annotations.style.width = `${width}px`; annotations.style.height = `${height}px`;
    annotations.querySelectorAll('.seal-marker').forEach((marker) => {
      marker.style.setProperty('--seal-diameter', `${height * Number(marker.dataset.size)}px`);
      marker.style.setProperty('--seal-width', Number(marker.dataset.width) || 0);
      marker.style.setProperty('--seal-widening-rotation', `${Number(marker.dataset.wideningRotation) || 0}deg`);
      marker.style.setProperty('--seal-rotation', `${Number(marker.dataset.rotation) || 0}deg`);
    });
  };
  const updatePreview = () => {
    if (!preview || !previewCrop || !previewImage) return;
    const seal = selectedIndex === null ? null : currentSeals()[selectedIndex];
    const coords = seal ? String(seal.position || '').split(',').map(Number) : magnifierPoint ? [magnifierPoint.x, magnifierPoint.y] : [];
    const [x, y] = coords; const size = seal ? Number(seal.size) : 0.12;
    if (!coords.length || ![x, y, size].every(Number.isFinite) || size <= 0) { preview.hidden = true; return; }
    preview.hidden = false; preview.classList.toggle('is-seal-preview', Boolean(seal)); preview.classList.toggle('is-magnifier', !seal);
    if (previewName) { previewName.hidden = !seal; previewName.value = seal?.person || ''; }
    if (seal) { const a = annotations.getBoundingClientRect(); const b = lightbox.getBoundingClientRect(); preview.style.left = `${a.left + x * a.width - b.left}px`; preview.style.top = `${a.top + y * a.height - b.top}px`; }
    Object.assign(previewCrop.dataset, { sealX: x, sealY: y, sealSize: size, sealWidth: seal?.width || 0, sealWideningRotation: seal?.wideningRotation || 0, sealRotation: seal?.rotation || 0 });
    if (previewImage.src !== image.src) previewImage.src = image.src;
    if (previewImage.naturalWidth) positionSealCrop(previewImage, previewCrop, x, y, size, Number(seal?.width) || 0, Number(seal?.wideningRotation) || 0, Number(seal?.rotation) || 0);
  };
  const updateControls = () => {
    const selected = selectedIndex === null ? null : currentSeals()[selectedIndex];
    const controls = $('#image-lightbox-seal-selected-controls'); const remove = $('#image-lightbox-remove-seal');
    if (controls) controls.hidden = !selected; if (remove) remove.hidden = !selected;
    [['#image-lightbox-seal-width', 'width'], ['#image-lightbox-seal-widening-rotation', 'wideningRotation'], ['#image-lightbox-seal-rotation', 'rotation']].forEach(([selector, key]) => { const input = $(selector); if (input) { input.disabled = !selected; input.value = String(Number(selected?.[key]) || 0); } });
    document.querySelectorAll('input[name="image-lightbox-seal-type"]').forEach((input) => { input.disabled = !selected; input.checked = Boolean(selected && SEAL_TYPES.has(selected.type) && selected.type === input.value); });
  };
  const render = () => {
    let index = 0;
    annotations.innerHTML = sealAnnotationMarkup(currentSeals(), escapeHtml).replace(/class="seal-marker"/g, (match) => `${match} data-seal-index="${index}"${index++ === selectedIndex ? ' data-selected="true"' : ''}`);
    annotations.querySelectorAll('.seal-marker').forEach((marker) => marker.classList.toggle('selected', Number(marker.dataset.sealIndex) === selectedIndex));
    updateGeometry(); updatePreview(); updateControls();
  };
  const save = () => {
    if (!context) return Promise.resolve(true);
    const operation = saveQueue.then(async () => {
      const document = state.documents.get(context.path); const entry = document?.entries?.[Number(context.entryIndex)];
      if (entry) (Array.isArray(entry.img) ? entry.img : [entry.img]).forEach((item) => { if (item && typeof item === 'object' && Array.isArray(item.seals) && !item.seals.length) delete item.seals; });
      try { setStatus('Saving…'); await repository.saveDocument(context.path, document); state.snapshot = ''; return true; }
      catch (error) { setStatus(error.message, true); return false; }
    }); saveQueue = operation.catch(() => {}); return operation;
  };
  const close = async () => { if (context && !await save()) return; lightbox.close(); };
  const startDrag = (event, index, target) => { const seal = currentSeals()[index]; if (!seal) return; selectedIndex = index; const p = point(event); const [x, y] = String(seal.position || '').split(',').map(Number); drag = { index, pointerId: event.pointerId, offsetX: x - p.x, offsetY: y - p.y }; render(); target.setPointerCapture?.(event.pointerId); event.preventDefault(); };
  const moveDrag = (event) => { if (!drag || event.pointerId !== drag.pointerId) return; const seal = currentSeals()[drag.index]; if (!seal) return; const p = point(event); seal.position = `${Math.max(0, Math.min(1, p.x + drag.offsetX)).toFixed(4)},${Math.max(0, Math.min(1, p.y + drag.offsetY)).toFixed(4)}`; render(); };

  if ($('#image-lightbox-editor')) $('#image-lightbox-editor').hidden = !editable;
  $('#content')?.addEventListener('click', (event) => {
    const link = event.target.closest('.image-link'); if (!link) return; event.preventDefault();
    const path = link.dataset.documentPath; const entryIndex = Number(link.dataset.entryIndex); const imageIndex = Number(link.dataset.imageIndex); const entry = path ? state.documents.get(path)?.entries?.[entryIndex] : null;
    let node = entry && (Array.isArray(entry.img) ? entry.img[imageIndex] : entry.img);
    if (node && typeof node !== 'object' && entry) { node = { src: node }; if (Array.isArray(entry.img)) entry.img[imageIndex] = node; else entry.img = node; }
    context = editable && entry && node && typeof node === 'object' ? { path, node, entryIndex, imageIndex } : null; if (context && !Array.isArray(node.seals)) node.seals = [];
    selectedIndex = null; lightbox.classList.toggle('is-editable', Boolean(context)); render();
    image.onerror = () => { const fallback = link.dataset.imageFallback; if (fallback && image.src !== fallback) image.src = fallback; };
    image.src = link.querySelector('img')?.currentSrc || link.dataset.imageSrc; image.alt = link.querySelector('img')?.alt || ''; image.onload = () => { updateGeometry(); updatePreview(); }; lightbox.showModal(); updateGeometry();
  });
  window.addEventListener('resize', () => { updateGeometry(); updatePreview(); }, { passive: true });
  closeButton.addEventListener('click', close);
  previewName?.addEventListener('input', () => { const seal = selectedIndex === null ? null : currentSeals()[selectedIndex]; if (seal) seal.person = previewName.value; });
  [['#image-lightbox-seal-width', 'width'], ['#image-lightbox-seal-widening-rotation', 'wideningRotation'], ['#image-lightbox-seal-rotation', 'rotation']].forEach(([selector, key]) => $(selector)?.addEventListener('input', (event) => { const seal = selectedIndex === null ? null : currentSeals()[selectedIndex]; if (seal) { seal[key] = Number(event.target.value); render(); } }));
  document.querySelectorAll('input[name="image-lightbox-seal-type"]').forEach((input) => input.addEventListener('change', () => { const seal = selectedIndex === null ? null : currentSeals()[selectedIndex]; if (seal && input.checked) seal.type = input.value; }));
  annotations.addEventListener('pointerdown', (event) => { const marker = event.target.closest('.seal-marker'); if (context && marker) startDrag(event, Number(marker.dataset.sealIndex), marker); }); annotations.addEventListener('pointermove', moveDrag); annotations.addEventListener('pointerup', () => { drag = null; }); annotations.addEventListener('pointercancel', () => { drag = null; });
  preview?.addEventListener('pointerdown', (event) => { if (context && selectedIndex !== null && preview.classList.contains('is-seal-preview') && event.target.closest('.seal-crop')) startDrag(event, selectedIndex, preview); }); preview?.addEventListener('pointermove', moveDrag); preview?.addEventListener('pointerup', () => { drag = null; }); preview?.addEventListener('pointercancel', () => { drag = null; });
  stage.addEventListener('click', async (event) => { if (!context) return; const marker = event.target.closest?.('.seal-marker'); if (marker) { magnifierPoint = null; selectedIndex = Number(marker.dataset.sealIndex); render(); return; } const old = selectedIndex; selectedIndex = null; render(); if (old !== null) await save(); });
  stage.addEventListener('pointermove', (event) => { if (!context || selectedIndex !== null) return; const rect = annotations.getBoundingClientRect(); if (!rect.width || event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) { magnifierPoint = null; updatePreview(); return; } magnifierPoint = point(event); updatePreview(); const box = lightbox.getBoundingClientRect(); if (preview) { preview.style.left = `${event.clientX - box.left}px`; preview.style.top = `${event.clientY - box.top}px`; } });
  stage.addEventListener('pointerleave', () => { if (selectedIndex === null) { magnifierPoint = null; updatePreview(); } });
  lightbox.addEventListener('wheel', (event) => { event.preventDefault(); if (!context) return; const marker = event.target.closest('.seal-marker'); const index = marker ? Number(marker.dataset.sealIndex) : selectedIndex; const seal = index === null ? null : currentSeals()[index]; if (seal && index === selectedIndex) { seal.size = Math.max(0.01, Math.min(0.5, Number(seal.size) + (event.deltaY < 0 ? 0.0005 : -0.0005))); render(); } }, { passive: false });
  $('#image-lightbox-add-seal')?.addEventListener('click', () => { if (!context) return; const person = window.prompt('Person shown by this seal:'); if (!person?.trim()) return; currentSeals().push({ person: person.trim(), position: '0.5,0.5', size: 0.08, width: 0, wideningRotation: 0, rotation: 0, type: 'full' }); selectedIndex = currentSeals().length - 1; render(); });
  $('#image-lightbox-remove-seal')?.addEventListener('click', () => { if (selectedIndex !== null) { currentSeals().splice(selectedIndex, 1); selectedIndex = null; render(); } });
  $('#image-lightbox-remove-image')?.addEventListener('click', async () => {
    if (!context || !window.confirm('Remove this image from the document?')) return;
    const document = state.documents.get(context.path); const entry = document?.entries?.[Number(context.entryIndex)];
    if (!entry) return;
    if (Array.isArray(entry.img)) {
      const item = entry.img[Number(context.imageIndex)];
      if (item && typeof item === 'object') item.deleted = 'true'; else entry.img[Number(context.imageIndex)] = { src: item, deleted: 'true' };
    } else if (entry.img && typeof entry.img === 'object') entry.img.deleted = 'true';
    else entry.img = { src: entry.img, deleted: 'true' };
    if (await save()) { lightbox.close(); await rerender?.(); }
  });
  lightbox.addEventListener('click', (event) => { if (event.target === lightbox) close(); }); lightbox.addEventListener('cancel', (event) => { event.preventDefault(); close(); });
  lightbox.addEventListener('close', () => { image.removeAttribute('src'); annotations.replaceChildren(); if (preview) preview.hidden = true; context = null; selectedIndex = null; drag = null; magnifierPoint = null; lightbox.classList.remove('is-editable'); setStatus(''); });
}
