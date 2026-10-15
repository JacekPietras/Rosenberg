export function positionSealCrop(image, crop, x, y, size, sealWidth = 0, wideningRotation = 0, rotation = 0) {
  const cropSize = image.naturalHeight * Math.max(size, 0.035);
  const scale = crop.clientHeight / cropSize;
  const imageWidth = image.naturalWidth * scale;
  const height = image.naturalHeight * scale;
  image.style.width = `${imageWidth}px`;
  image.style.height = `${height}px`;
  image.style.left = `${crop.clientWidth / 2 - x * imageWidth}px`;
  image.style.top = `${crop.clientHeight / 2 - y * height}px`;
  image.style.transformOrigin = `${x * imageWidth}px ${y * height}px`;
  image.style.transform = `rotate(${rotation}deg) rotate(${-wideningRotation}deg) scaleX(${1 + sealWidth}) rotate(${wideningRotation}deg)`;
}

export function setupSealAnnotations({ state, position = positionSealCrop } = {}) {
  state.sealMarkerCleanup?.();
  state.sealMarkerCleanup = null;
  const annotatedImages = [...document.querySelectorAll('.annotated-image img')];
  const cropImages = [...document.querySelectorAll('.seal-crop img')];
  const focusedImages = [...document.querySelectorAll('img[data-focus-x]')];
  if (!annotatedImages.length && !cropImages.length && !focusedImages.length) return;
  const cropReveals = new Map();
  const update = () => {
    focusedImages.forEach((image) => {
      if (!image.naturalWidth || !image.naturalHeight) return;
      const box = image.getBoundingClientRect();
      if (!box.width || !box.height || getComputedStyle(image).objectFit !== 'cover') return;
      const scale = Math.max(box.width / image.naturalWidth, box.height / image.naturalHeight);
      const renderedWidth = image.naturalWidth * scale, renderedHeight = image.naturalHeight * scale;
      const focusX = Number(image.dataset.focusX) + Number(image.dataset.focusWidth) / 2;
      const focusY = Number(image.dataset.focusY) + Number(image.dataset.focusHeight) / 2;
      const positionX = renderedWidth > box.width ? (focusX * renderedWidth - box.width / 2) / (renderedWidth - box.width) : 0.5;
      const positionY = renderedHeight > box.height ? (focusY * renderedHeight - box.height / 2) / (renderedHeight - box.height) : 0.5;
      image.style.objectPosition = `${Math.max(0, Math.min(1, positionX)) * 100}% ${Math.max(0, Math.min(1, positionY)) * 100}%`;
    });
    annotatedImages.forEach((image) => {
      const height = image.clientHeight;
      image.closest('.annotated-image')?.querySelectorAll('.seal-marker').forEach((marker) => {
        marker.style.setProperty('--seal-diameter', `${height * Number(marker.dataset.size)}px`);
        marker.style.setProperty('--seal-width', Number(marker.dataset.width) || 0);
        marker.style.setProperty('--seal-widening-rotation', `${Number(marker.dataset.wideningRotation) || 0}deg`);
        marker.style.setProperty('--seal-rotation', `${Number(marker.dataset.rotation) || 0}deg`);
      });
    });
    cropImages.forEach((image) => {
      if (!image.naturalWidth || !image.naturalHeight) return;
      const crop = image.closest('.seal-crop');
      if (!crop) return;
      const values = ['sealX', 'sealY', 'sealSize', 'sealWidth', 'sealWideningRotation', 'sealRotation'].map((key) => Number(crop.dataset[key]));
      const [x, y, size, width, wideningRotation, rotation] = values;
      if (!values.every(Number.isFinite) || size <= 0 || !crop.clientWidth || !crop.clientHeight) return;
      position(image, crop, x, y, size, width, wideningRotation, rotation);
    });
  };
  annotatedImages.forEach((image) => image.addEventListener('load', update));
  focusedImages.forEach((image) => image.addEventListener('load', update));
  cropImages.forEach((image) => {
    const reveal = () => { update(); image.closest('.seal-crop')?.classList.remove('is-loading'); };
    cropReveals.set(image, reveal);
    image.addEventListener('load', reveal);
    if (image.complete && image.naturalWidth && image.naturalHeight) reveal();
  });
  window.addEventListener('resize', update, { passive: true });
  state.sealMarkerCleanup = () => {
    annotatedImages.forEach((image) => image.removeEventListener('load', update));
    focusedImages.forEach((image) => image.removeEventListener('load', update));
    cropImages.forEach((image) => image.removeEventListener('load', cropReveals.get(image)));
    window.removeEventListener('resize', update);
  };
  update();
}
