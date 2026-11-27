import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { buildSourcePersonPattern, findPersonNameMentions } = await import(await moduleUrl(new URL('../docs/app/data/person-name-recognition.js', import.meta.url)));
const titles = await readFile(new URL('../data/titles-office.md', import.meta.url), 'utf8');
const names = '# Men\nEberhard\n';
const places = [{ name: 'Rosenberg', variations: ['Rosenberg'] }, { name: 'Lauda', variations: ['Lauda'] }];

test('recognizes Reichsvogt variants and retains the imperial title', () => {
  const pattern = buildSourcePersonPattern(names, 'von', places, titles);
  for (const form of ['Reichsvogt', 'Reichs Vogt', 'Reichs-Vogt']) {
    const text = `Eberhard von Rosenberg, ${form} zu Lauda`;
    const result = findPersonNameMentions(text, titles, '', 'von', names, '', places, pattern);
    assert.deepEqual(result.singles.map(({ route, titles: values }) => ({ route, values })),
      [{ route: 'Eberhard von Rosenberg', values: ['Reichsvogt zu Lauda'] }]);
  }
});
