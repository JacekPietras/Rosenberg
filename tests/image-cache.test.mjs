import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { moduleUrl } from './browser-module.mjs';

const { localImageName } = await import(await moduleUrl(new URL('../docs/app/rendering/image-paths.js', import.meta.url)));

test('document image names identify the complete URL', () => {
  for (const url of [
    'https://api.digitale-sammlungen.de/iiif/image/v2/bav80035235_00001/full/max/0/default.jpg',
    'https://api.digitale-sammlungen.de/iiif/image/v2/bav80035235_00002/full/max/0/default.jpg',
    'https://example.org/image?originalBilddatei=Gr%C3%BCn%20%231.JPG',
  ]) {
    assert.equal(localImageName(url, true), createHash('sha256').update(url).digest('hex') + '.jpg');
  }
});
