// Synchronous SHA-256 keeps the rendered local filename identical to the
// server and downloader cache names without delaying image markup.
function sha256(value) {
  const bytes = Array.from(new TextEncoder().encode(value));
  const bitLength = bytes.length * 8;
  bytes.push(0x80);
  while (bytes.length % 64 !== 56) bytes.push(0);
  const high = Math.floor(bitLength / 0x100000000);
  const low = bitLength >>> 0;
  for (const word of [high, low]) for (let shift = 24; shift >= 0; shift -= 8) bytes.push((word >>> shift) & 255);
  const constants = [];
  const initial = [];
  for (let candidate = 2; constants.length < 64; candidate++) {
    let prime = true;
    for (let divisor = 2; divisor * divisor <= candidate; divisor++) if (candidate % divisor === 0) { prime = false; break; }
    if (!prime) continue;
    if (initial.length < 8) initial.push((Math.sqrt(candidate) % 1 * 0x100000000) >>> 0);
    constants.push((Math.cbrt(candidate) % 1 * 0x100000000) >>> 0);
  }
  const rotate = (x, n) => (x >>> n) | (x << (32 - n));
  const hash = initial.slice();
  for (let offset = 0; offset < bytes.length; offset += 64) {
    const words = new Array(64);
    for (let i = 0; i < 16; i++) words[i] = ((bytes[offset + i * 4] << 24) | (bytes[offset + i * 4 + 1] << 16) | (bytes[offset + i * 4 + 2] << 8) | bytes[offset + i * 4 + 3]) >>> 0;
    for (let i = 16; i < 64; i++) {
      const a = words[i - 15], b = words[i - 2];
      words[i] = (words[i - 16] + (rotate(a, 7) ^ rotate(a, 18) ^ (a >>> 3)) + words[i - 7] + (rotate(b, 17) ^ rotate(b, 19) ^ (b >>> 10))) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = hash;
    for (let i = 0; i < 64; i++) {
      const t1 = (h + (rotate(e, 6) ^ rotate(e, 11) ^ rotate(e, 25)) + ((e & f) ^ (~e & g)) + constants[i] + words[i]) >>> 0;
      const t2 = ((rotate(a, 2) ^ rotate(a, 13) ^ rotate(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
      [a, b, c, d, e, f, g, h] = [(t1 + t2) >>> 0, a, b, c, (d + t1) >>> 0, e, f, g];
    }
    [a, b, c, d, e, f, g, h].forEach((word, i) => { hash[i] = (hash[i] + word) >>> 0; });
  }
  return hash.map((word) => word.toString(16).padStart(8, '0')).join('');
}

export function localImageName(fileName, useUrlHash = false) {
  if (!/^https?:\/\//i.test(fileName)) return fileName;
  try {
    const url = new URL(fileName);
    const original = url.searchParams.get('originalBilddatei');
    const name = (original || decodeURIComponent(url.pathname)).split('/').filter(Boolean).pop() || '';
    if (!useUrlHash) return name;
    const suffix = name.match(/\.[^.]+$/)?.[0].toLowerCase() || '';
    return sha256(fileName) + suffix;
  } catch {
    return '';
  }
}

export function imageRootForPath(path) {
  const match = String(path || '').match(/^data\/(books|documents|notes|images)\//);
  return match ? `data/${match[1]}` : 'data';
}
