export function parseRoute(location = window.location) {
  const params = new URLSearchParams(location.search);
  const tab = params.get('tab') || null;
  const document = params.get('document') || null;
  return {
    active: tab || document || 'books',
    tab,
    document,
    letter: params.get('letter') || null,
    source: params.get('source') || null,
    place: params.get('place') || null,
    person: params.get('person') || null,
    hash: decodeURIComponent(location.hash.slice(1)),
  };
}

export function replaceRoute(route, location = window.location, historyObject = window.history) {
  const url = new URL(location.href);
  url.search = '';
  url.hash = route.hash ? `#${route.hash}` : '';
  if (route.document) url.searchParams.set('document', route.document);
  else if (route.tab) url.searchParams.set('tab', route.tab);
  else if (route.active) url.searchParams.set(route.active.startsWith('data/') ? 'document' : 'tab', route.active);
  if (route.letter) url.searchParams.set('letter', route.letter);
  if (route.source) url.searchParams.set('source', route.source);
  if (route.place) url.searchParams.set('place', route.place);
  if (route.person) url.searchParams.set('person', route.person);
  historyObject.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
}
