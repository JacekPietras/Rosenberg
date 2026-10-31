import { verifyFamilyGraph, buildRelationshipGraph } from './relationships.js?v=9';
import { createRepository } from './repository.js?v=7';

self.onmessage = async ({ data }) => {
  try {
    const repository = createRepository({
      location: data.location,
      fetchFunction: (url, options) => fetch(new URL(url, data.location.href), options),
    });
    const tree = await repository.getFamilyTree();
    let verification = await verifyFamilyGraph(data.people, data.documents, repository, data.paths, tree);
    if (tree?.schema >= 4 && !tree.views?.includes('with-guesses')) verification = { valid: false, reason: 'The normal tree requires weighted guesses.' };
    const graph = buildRelationshipGraph(data.people, { tree, view: tree && (tree.schema === undefined || tree.schema >= 4) ? 'with-guesses' : data.view, verification });
    self.postMessage({ result: { tree, verification, graph } });
  } catch (error) {
    self.postMessage({ error: error.message });
  }
};
