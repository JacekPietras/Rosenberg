// Targets are in document order, even when their heights change after loading.
export function documentAtMarker(targets, marker = 160) {
  if (!targets.length) return null;
  let left = 0;
  let right = targets.length;
  while (left < right) {
    const middle = Math.floor((left + right) / 2);
    if (targets[middle].element.getBoundingClientRect().top <= marker) left = middle + 1;
    else right = middle;
  }
  return targets[Math.max(0, left - 1)];
}
