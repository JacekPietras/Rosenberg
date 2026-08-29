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
  if (!annotatedImages.length && !cropImages.length) return;
  const cropReveals = new Map();
  const update = () => {
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
  cropImages.forEach((image) => {
    const reveal = () => { update(); image.closest('.seal-crop')?.classList.remove('is-loading'); };
    cropReveals.set(image, reveal);
    image.addEventListener('load', reveal);
    if (image.complete && image.naturalWidth && image.naturalHeight) reveal();
  });
  window.addEventListener('resize', update, { passive: true });
  state.sealMarkerCleanup = () => {
    annotatedImages.forEach((image) => image.removeEventListener('load', update));
    cropImages.forEach((image) => image.removeEventListener('load', cropReveals.get(image)));
    window.removeEventListener('resize', update);
  };
  update();
}
