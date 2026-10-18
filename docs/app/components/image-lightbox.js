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
  const regionOverlay = $('#image-lightbox-region-overlay');
  const regionBox = regionOverlay?.querySelector('.image-lightbox-region-box');
  const preview = $('#image-lightbox-seal-preview');
  const previewCrop = preview?.querySelector('.seal-crop');
  const previewImage = preview?.querySelector('img');
  const previewName = preview?.querySelector('.image-lightbox-seal-preview-name');
  const regionButton = $('#image-lightbox-add-region');
  const removeRegionButton = $('#image-lightbox-remove-region');
  const collectionNavigation = $('#image-lightbox-collection-navigation');
  const collectionPrevious = $('#image-lightbox-collection-previous');
  const collectionNext = $('#image-lightbox-collection-next');
  const collectionPosition = $('#image-lightbox-collection-position');
  const closeButton = $('#image-lightbox-close');
  if (!lightbox || !image || !stage || !annotations || !closeButton) return;

  const editable = !location.hostname.endsWith('github.io');
  const saveStatus = $('#image-lightbox-save-status');
  const removeConfirmation = document.createElement('dialog');
  removeConfirmation.className = 'image-remove-confirmation';
  removeConfirmation.setAttribute('aria-labelledby', 'image-remove-confirmation-title');
  removeConfirmation.innerHTML = '<form method="dialog"><p id="image-remove-confirmation-title">Remove this image from the document?</p><div><button value="cancel">Cancel</button><button value="confirm">Remove image</button></div></form>';
  document.body.append(removeConfirmation);
  const confirmImageRemoval = () => {
    if (typeof removeConfirmation.showModal !== 'function') return Promise.resolve(window.confirm('Remove this image from the document?'));
    return new Promise((resolve) => {
      removeConfirmation.addEventListener('close', () => resolve(removeConfirmation.returnValue === 'confirm'), { once: true });
      removeConfirmation.showModal();
    });
  };
  let context = null;
  let collectionLinks = null;
  let visibleRegions = [];
  let selectedIndex = null;
  let selectedRegionIndex = null;
  let drag = null;
  let regionDrag = null;
  let regionMode = false;
  let ignoreFocusClick = false;
  let magnifierPoint = null;
  let magnifierDismissed = false;
  const MAGNIFIER_SIZE = 0.12;
  const MAGNIFIER_SIZE_STEP = 0.01;
  let magnifierSize = MAGNIFIER_SIZE;
  let saveQueue = Promise.resolve();
  const driveFileId = (value) => {
    try {
      const url = new URL(String(value || ''), location.href);
      if (url.hostname === 'drive.google.com') return url.searchParams.get('id') || '';
      if (url.hostname.endsWith('googleusercontent.com')) return url.pathname.match(/\/d\/([^/=]+)/)?.[1] || '';
    } catch {}
    return '';
  };
  const currentSeals = () => context?.node?.seals || [];
  const currentRegions = () => context?.node?.regions || context?.entry?.regions || visibleRegions;
  const magnifierMaximumSize = () => {
    const imageHeight = annotations.clientHeight;
    const previewHeight = previewCrop?.clientHeight;
    return imageHeight && previewHeight ? Math.max(0.03, Math.min(0.5, previewHeight / imageHeight)) : MAGNIFIER_SIZE;
  };
  const setStatus = (message, error = false) => { if (saveStatus) { saveStatus.textContent = message; saveStatus.classList.toggle('error', error); } };
  const point = (event) => { const rect = annotations.getBoundingClientRect(); return { x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) }; };
  const updateGeometry = () => {
    if (!image.naturalWidth || !image.naturalHeight) return;
    const scale = Math.min(stage.clientWidth / image.naturalWidth, stage.clientHeight / image.naturalHeight);
    const width = image.naturalWidth * scale; const height = image.naturalHeight * scale;
    annotations.style.left = `${(stage.clientWidth - width) / 2}px`; annotations.style.top = `${(stage.clientHeight - height) / 2}px`;
    annotations.style.width = `${width}px`; annotations.style.height = `${height}px`;
    if (regionOverlay) {
      Object.assign(regionOverlay.style, { left: annotations.style.left, top: annotations.style.top, width: `${width}px`, height: `${height}px` });
    }
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
    const [x, y] = coords; const size = seal ? Number(seal.size) : magnifierSize;
    if (!coords.length || ![x, y, size].every(Number.isFinite) || size <= 0 || (!seal && magnifierDismissed)) { preview.hidden = true; return; }
    if (!seal && magnifierSize >= magnifierMaximumSize() - 0.0001) { preview.hidden = true; return; }
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
    const removeImage = $('#image-lightbox-remove-image'); if (removeImage) removeImage.hidden = Boolean(context?.entryImage);
    [['#image-lightbox-seal-width', 'width'], ['#image-lightbox-seal-widening-rotation', 'wideningRotation'], ['#image-lightbox-seal-rotation', 'rotation']].forEach(([selector, key]) => { const input = $(selector); if (input) { input.disabled = !selected; input.value = String(Number(selected?.[key]) || 0); } });
    document.querySelectorAll('input[name="image-lightbox-seal-type"]').forEach((input) => { input.disabled = !selected; input.checked = Boolean(selected && SEAL_TYPES.has(selected.type) && selected.type === input.value); });
    if (collectionNavigation) collectionNavigation.hidden = !collectionLinks || collectionLinks.links.length < 2;
    if (collectionPosition) collectionPosition.textContent = collectionLinks ? `${collectionLinks.index + 1} / ${collectionLinks.links.length}` : '';
  };
  const updateFocusOverlay = () => {
    regionOverlay?.classList.toggle('is-visible', regionMode);
    regionOverlay?.classList.toggle('is-editing', regionMode);
    regionButton?.setAttribute('aria-pressed', String(regionMode));
  };
  const render = () => {
    let index = 0;
    const seals = sealAnnotationMarkup(currentSeals(), escapeHtml).replace(/class="seal-marker"/g, (match) => `${match} data-seal-index="${index}"${index++ === selectedIndex ? ' data-selected="true"' : ''}`);
    const regions = currentRegions().map((region, regionIndex) => {
      const x = Number(region.x), y = Number(region.y), width = Number(region.width), height = Number(region.height);
      if (!region.name || ![x, y, width, height].every(Number.isFinite)) return '';
      return `<span class="image-region image-lightbox-region${regionIndex === selectedRegionIndex ? ' selected' : ''}" data-region-index="${regionIndex}" style="left:${x * 100}%;top:${y * 100}%;width:${width * 100}%;height:${height * 100}%"><span>${escapeHtml(region.name)}</span></span>`;
    }).join('');
    annotations.innerHTML = seals + regions;
    annotations.querySelectorAll('.seal-marker').forEach((marker) => marker.classList.toggle('selected', Number(marker.dataset.sealIndex) === selectedIndex));
    if (removeRegionButton) removeRegionButton.hidden = !context || selectedRegionIndex === null || !currentRegions()[selectedRegionIndex];
    updateGeometry(); updateFocusOverlay(); updatePreview(); updateControls();
  };
  const save = () => {
    if (!context) { setStatus('Image annotations cannot be saved here.', true); return Promise.resolve(false); }
    const operation = saveQueue.then(async () => {
      const document = state.documents.get(context.path); const entry = document?.entries?.[Number(context.entryIndex)];
      if (entry) (Array.isArray(entry.img) ? entry.img : [entry.img]).forEach((item) => { if (item && typeof item === 'object' && Array.isArray(item.seals) && !item.seals.length) delete item.seals; });
      try { setStatus('Saving…'); await repository.saveDocument(context.path, document); state.snapshot = ''; setStatus(''); return true; }
      catch (error) {
        console.error(`Failed to save image annotations in ${context.path}`, error);
        setStatus(error?.message || String(error), true);
        return false;
      }
    }); saveQueue = operation.catch(() => {}); return operation;
  };
  const close = async () => { if (context && !await save()) return; lightbox.close(); await rerender?.(); };
  const startDrag = (event, index, target) => { const seal = currentSeals()[index]; if (!seal) return; const [x, y] = String(seal.position || '').split(',').map(Number); magnifierPoint = { x, y }; magnifierDismissed = false; selectedIndex = index; const p = point(event); drag = { index, pointerId: event.pointerId, offsetX: x - p.x, offsetY: y - p.y }; render(); target.setPointerCapture?.(event.pointerId); event.preventDefault(); };
  const moveDrag = (event) => { if (!drag || event.pointerId !== drag.pointerId) return; const seal = currentSeals()[drag.index]; if (!seal) return; const p = point(event); seal.position = `${Math.max(0, Math.min(1, p.x + drag.offsetX)).toFixed(4)},${Math.max(0, Math.min(1, p.y + drag.offsetY)).toFixed(4)}`; render(); };
  const regionPoint = (event) => {
    const rect = regionOverlay.getBoundingClientRect();
    return { x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) };
  };
  const drawRegion = (start, end) => {
    const minimum = 0.015;
    let x = Math.min(start.x, end.x), y = Math.min(start.y, end.y);
    let width = Math.abs(end.x - start.x), height = Math.abs(end.y - start.y);
    if (width < minimum) { width = minimum; x = Math.max(0, Math.min(1 - minimum, (start.x + end.x) / 2 - minimum / 2)); }
    if (height < minimum) { height = minimum; y = Math.max(0, Math.min(1 - minimum, (start.y + end.y) / 2 - minimum / 2)); }
    const box = regionBox;
    if (box) Object.assign(box.style, { left: `${x * 100}%`, top: `${y * 100}%`, width: `${width * 100}%`, height: `${height * 100}%` });
    return { x: Number(x.toFixed(4)), y: Number(y.toFixed(4)), width: Number(width.toFixed(4)), height: Number(height.toFixed(4)) };
  };
  if ($('#image-lightbox-editor')) $('#image-lightbox-editor').hidden = !editable;
  const openImageLink = (link) => {
    const path = link.dataset.documentPath; const entryIndex = Number(link.dataset.entryIndex); const imageIndex = Number(link.dataset.imageIndex); const entry = path ? state.documents.get(path)?.entries?.[entryIndex] : null;
    let node = entry && (Array.isArray(entry.img) ? entry.img[imageIndex] : entry.img);
    visibleRegions = node && typeof node === 'object' ? node.regions || [] : entry?.regions || [];
    if (node && typeof node !== 'object' && entry) { node = { src: node }; if (Array.isArray(entry.img)) entry.img[imageIndex] = node; else entry.img = node; }
    context = editable && entry && !node && entry.url
      ? { path, entry, entryIndex, imageIndex, entryImage: true }
      : editable && entry && node && typeof node === 'object' ? { path, node, entry, entryIndex, imageIndex } : null;
    if (context?.node && !Array.isArray(context.node.seals)) context.node.seals = [];
    selectedIndex = null; selectedRegionIndex = null; regionMode = false; lightbox.classList.toggle('is-editable', Boolean(context)); render();
    const item = entry && Array.isArray(entry.img) ? entry.img[imageIndex] : null;
    const directSource = collectionLinks?.entry === entry ? (typeof item === 'string' ? item : item?.src) : '';
    const sources = [...new Set([directSource, link.dataset.imageSrc, link.dataset.imageFallback, link.querySelector('img')?.currentSrc].filter(Boolean))];
    let sourceIndex = 0;
    image.onerror = () => { sourceIndex += 1; if (sourceIndex < sources.length) image.src = sources[sourceIndex]; };
    image.onload = () => { updateGeometry(); updatePreview(); };
    image.referrerPolicy = 'no-referrer';
    image.alt = link.querySelector('img')?.alt || (typeof item === 'object' ? item?.name : '') || '';
    if (typeof lightbox.showModal === 'function') {
      if (!lightbox.open) lightbox.showModal();
    } else {
      lightbox.setAttribute('open', '');
    }
    image.src = sources[sourceIndex] || '';
    updateGeometry();
  };
  $('#content')?.addEventListener('click', (event) => {
    const coverButton = event.target?.closest?.('[data-open-collection-cover]');
    if (coverButton) {
      event.preventDefault();
      const entryIndex = Number(coverButton.dataset.openCollectionCover);
      const entry = state.documents.get(state.manifest.images)?.entries?.[entryIndex];
      const links = [...coverButton.parentElement.querySelectorAll('.model-collection-cover-images .image-link')];
      if (!entry || !links.length) return;
      const currentCover = entry.coverImage || entry.preview;
      const currentDriveId = driveFileId(currentCover);
      const matchingLink = links.findIndex((link) => {
        const source = link.dataset.imageSrc;
        return currentDriveId ? driveFileId(source) === currentDriveId : source === currentCover;
      });
      const index = matchingLink >= 0 ? matchingLink : 0;
      collectionLinks = { entry, entryIndex, links, index };
      openImageLink(links[index]);
      return;
    }
    const link = event.target?.closest?.('.image-link'); if (!link) return; event.preventDefault();
    collectionLinks = null;
    openImageLink(link);
  });
  const moveCollectionCover = async (step) => {
    if (!collectionLinks) return;
    const nextIndex = (collectionLinks.index + step + collectionLinks.links.length) % collectionLinks.links.length;
    const link = collectionLinks.links[nextIndex];
    const source = link.dataset.imageSrc;
    if (!source) return;
    if (context && !await save()) return;
    const previousIndex = collectionLinks.index;
    const previousCover = collectionLinks.entry.coverImage;
    collectionLinks.index = nextIndex;
    collectionLinks.entry.coverImage = source;
    if (editable) try {
      setStatus('Saving cover…');
      await repository.saveDocument(state.manifest.images, state.documents.get(state.manifest.images));
      state.snapshot = '';
      setStatus('');
    } catch (error) {
      collectionLinks.index = previousIndex;
      if (previousCover === undefined) delete collectionLinks.entry.coverImage;
      else collectionLinks.entry.coverImage = previousCover;
      console.error('Failed to save collection cover image', error);
      setStatus(error?.message || String(error), true);
      return;
    }
    openImageLink(link);
  };
  collectionPrevious?.addEventListener('click', () => moveCollectionCover(-1));
  collectionNext?.addEventListener('click', () => moveCollectionCover(1));
  window.addEventListener('resize', () => { updateGeometry(); updatePreview(); }, { passive: true });
  regionButton?.addEventListener('click', () => { regionMode = !regionMode; ignoreFocusClick = false; selectedIndex = null; updateFocusOverlay(); });
  removeRegionButton?.addEventListener('click', async () => {
    const regions = currentRegions();
    if (selectedRegionIndex === null || !regions[selectedRegionIndex]) return;
    regions.splice(selectedRegionIndex, 1);
    selectedRegionIndex = null;
    render();
    await save();
  });
  closeButton.addEventListener('click', close);
  previewName?.addEventListener('input', () => { const seal = selectedIndex === null ? null : currentSeals()[selectedIndex]; if (seal) seal.person = previewName.value; });
  [['#image-lightbox-seal-width', 'width'], ['#image-lightbox-seal-widening-rotation', 'wideningRotation'], ['#image-lightbox-seal-rotation', 'rotation']].forEach(([selector, key]) => $(selector)?.addEventListener('input', (event) => { const seal = selectedIndex === null ? null : currentSeals()[selectedIndex]; if (seal) { seal[key] = Number(event.target.value); render(); } }));
  document.querySelectorAll('input[name="image-lightbox-seal-type"]').forEach((input) => input.addEventListener('change', () => { const seal = selectedIndex === null ? null : currentSeals()[selectedIndex]; if (seal && input.checked) seal.type = input.value; }));
  annotations.addEventListener('pointerdown', (event) => { const marker = event.target.closest('.seal-marker'); if (context && marker) startDrag(event, Number(marker.dataset.sealIndex), marker); }); annotations.addEventListener('pointermove', moveDrag); annotations.addEventListener('pointerup', () => { drag = null; }); annotations.addEventListener('pointercancel', () => { drag = null; });
  regionOverlay?.addEventListener('pointerdown', (event) => {
    if (!regionMode || !regionOverlay.clientWidth || !regionOverlay.clientHeight) return;
    const p = regionPoint(event); regionDrag = { pointerId: event.pointerId, start: p, moved: false };
  });
  window.addEventListener('pointermove', (event) => {
    if (regionDrag?.pointerId !== event.pointerId) return;
    const current = regionPoint(event);
    if (Math.abs(current.x - regionDrag.start.x) + Math.abs(current.y - regionDrag.start.y) > 0.005) regionDrag.moved = true;
    if (regionMode) drawRegion(regionDrag.start, current);
  });
  window.addEventListener('pointerup', async (event) => {
    if (!regionDrag || event.pointerId !== regionDrag.pointerId) return;
    if (!regionMode) { regionDrag = null; return; }
    const region = drawRegion(regionDrag.start, regionPoint(event));
    const name = window.prompt('Name this image region:');
    if (name?.trim()) { const owner = context?.node || context?.entry; if (owner) { if (!Array.isArray(owner.regions)) owner.regions = []; owner.regions.push({ ...region, name: name.trim() }); render(); await save(); } }
    regionMode = false;
    regionDrag = null; ignoreFocusClick = true; updateFocusOverlay();
  });
  window.addEventListener('pointercancel', () => { regionDrag = null; });
  regionOverlay?.addEventListener('click', (event) => {
    if (ignoreFocusClick) { ignoreFocusClick = false; return; }
    if (regionMode) event.preventDefault();
  });
  preview?.addEventListener('pointerdown', (event) => { if (context && selectedIndex !== null && preview.classList.contains('is-seal-preview') && event.target.closest('.seal-crop')) startDrag(event, selectedIndex, preview); }); preview?.addEventListener('pointermove', moveDrag); preview?.addEventListener('pointerup', () => { drag = null; }); preview?.addEventListener('pointercancel', () => { drag = null; });
  stage.addEventListener('click', async (event) => {
    if (!context) return;
    const marker = event.target.closest?.('.seal-marker'); if (marker) { const seal = currentSeals()[Number(marker.dataset.sealIndex)]; if (seal) { const [x, y] = String(seal.position || '').split(',').map(Number); magnifierPoint = { x, y }; } magnifierDismissed = false; selectedIndex = Number(marker.dataset.sealIndex); render(); return; } const old = selectedIndex; selectedIndex = null; const rect = annotations.getBoundingClientRect(); if (event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom) { magnifierPoint = point(event); const box = lightbox.getBoundingClientRect(); if (preview) { preview.style.left = `${event.clientX - box.left}px`; preview.style.top = `${event.clientY - box.top}px`; } } else magnifierPoint = null; magnifierDismissed = true; render(); if (old !== null) await save();
  });
  annotations.addEventListener('click', async (event) => {
    const marker = event.target.closest('.image-region');
    if (!context || !marker) return;
    event.stopPropagation();
    const owner = context.node || context.entry;
    const regions = owner?.regions || [];
    const region = regions[Number(marker.dataset.regionIndex)];
    if (!region) return;
    selectedRegionIndex = Number(marker.dataset.regionIndex);
    render();
    const name = window.prompt('Rename image region (leave empty to keep the current name):', region.name);
    if (name === null || !name.trim()) return;
    region.name = name.trim();
    render();
    await save();
  });
  stage.addEventListener('pointermove', (event) => { if (regionDrag || selectedIndex !== null) return; const rect = annotations.getBoundingClientRect(); if (!rect.width || event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) { magnifierPoint = null; magnifierDismissed = false; updatePreview(); return; } magnifierPoint = point(event); magnifierDismissed = false; updatePreview(); const box = lightbox.getBoundingClientRect(); if (preview) { preview.style.left = `${event.clientX - box.left}px`; preview.style.top = `${event.clientY - box.top}px`; } });
  stage.addEventListener('pointerleave', () => { if (selectedIndex === null) { magnifierPoint = null; updatePreview(); } });
  lightbox.addEventListener('wheel', (event) => {
    event.preventDefault();
    if (selectedIndex === null && magnifierPoint) {
      magnifierDismissed = false;
      magnifierSize = Math.max(0.03, Math.min(magnifierMaximumSize(), magnifierSize + (event.deltaY < 0 ? -MAGNIFIER_SIZE_STEP : MAGNIFIER_SIZE_STEP)));
      updatePreview();
      return;
    }
    if (!context) return;
    const marker = event.target.closest('.seal-marker');
    const index = marker ? Number(marker.dataset.sealIndex) : selectedIndex;
    const seal = index === null ? null : currentSeals()[index];
    if (seal && index === selectedIndex) {
      seal.size = Math.max(0.01, Math.min(0.5, Number(seal.size) + (event.deltaY < 0 ? 0.0005 : -0.0005)));
      render();
    }
  }, { passive: false });
  $('#image-lightbox-add-seal')?.addEventListener('click', () => { if (!context) return; const person = window.prompt('Person shown by this seal:'); if (!person?.trim()) return; currentSeals().push({ person: person.trim(), position: '0.5,0.5', size: 0.08, width: 0, wideningRotation: 0, rotation: 0, type: 'full' }); selectedIndex = currentSeals().length - 1; render(); });
  $('#image-lightbox-remove-seal')?.addEventListener('click', () => { if (selectedIndex !== null) { currentSeals().splice(selectedIndex, 1); selectedIndex = null; render(); } });
  $('#image-lightbox-remove-image')?.addEventListener('click', async () => {
    if (!context || !await confirmImageRemoval()) return;
    const document = state.documents.get(context.path); const entry = document?.entries?.[Number(context.entryIndex)];
    if (!entry) return;
    if (Array.isArray(entry.img)) {
      const item = entry.img[Number(context.imageIndex)];
      if (item && typeof item === 'object') item.deleted = 'true'; else entry.img[Number(context.imageIndex)] = { src: item, deleted: 'true' };
    } else if (entry.img && typeof entry.img === 'object') entry.img.deleted = 'true';
    else entry.img = { src: entry.img, deleted: 'true' };
    if (await save()) { lightbox.close(); await rerender?.(); }
  });
  lightbox.addEventListener('click', (event) => { if (!context && event.target === lightbox) close(); });
  lightbox.addEventListener('cancel', (event) => { event.preventDefault(); close(); });
  lightbox.addEventListener('close', () => { image.removeAttribute('src'); annotations.replaceChildren(); if (preview) preview.hidden = true; context = null; collectionLinks = null; if (collectionNavigation) collectionNavigation.hidden = true; visibleRegions = []; selectedIndex = null; selectedRegionIndex = null; drag = null; regionDrag = null; regionMode = false; regionOverlay?.classList.remove('is-visible', 'is-editing'); magnifierPoint = null; magnifierDismissed = false; lightbox.classList.remove('is-editable'); setStatus(''); });
}
