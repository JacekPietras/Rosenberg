// Safety checks for automatic rewriting of fact participant names.
const words = (value) => value.trim().split(/\s+/u).filter(Boolean);

// A normalization may fix spelling, particles and places but never drop the
// surname, reduce a full name to a lone given name, or add words (a place).
export function acceptNormalizedName(name, canonical) {
  const before = words(name);
  const after = words(canonical);
  if (!after.length) return false;
  if (before.length > 1 && after.length === 1) return false;
  return after.length <= before.length;
}

// Moving a title out of a name must not leave a lone given name: a trailing word
// such as `Keller` in `Georg Keller` is a surname.
export function acceptTitleSplit(original, split) {
  const before = words(original);
  const after = words(split.name ?? '');
  return after.length > 0 && !(before.length > 1 && after.length === 1);
}
