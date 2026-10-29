import { readFile } from 'node:fs/promises';

const modules = new Map();
export async function moduleUrl(path) {
  if (modules.has(path.href)) return modules.get(path.href);
  let source = await readFile(path, 'utf8');
  source = source.replaceAll('import.meta.url', JSON.stringify(path.href));
  for (const [statement, specifier] of [...source.matchAll(/from '([^']+)'/g)]) {
    const dependency = new URL(specifier, path);
    dependency.search = '';
    source = source.replace(statement, `from '${await moduleUrl(dependency)}'`);
  }
  const result = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
  modules.set(path.href, result);
  return result;
}
