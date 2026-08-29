export function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
}

export function urlLabel(value) {
  try {
    const hostname = new URL(value).hostname.replace(/^www\./i, '');
    return hostname.split('.').slice(-2).join('.');
  } catch {
    return value;
  }
}

export function urlMarkup(value) {
  const links = (Array.isArray(value) ? value : [value])
    .filter((url) => /^https?:\/\//i.test(String(url || '')))
    .map((url) => `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(urlLabel(url))}</a>`);
  return links.length ? `<p class="document-url">${links.join(' · ')}</p>` : '';
}
