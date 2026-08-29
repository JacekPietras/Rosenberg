export function createLanguageRenderer({ state, markdownMarkup }) {
  function displayedLanguagesFor(entry) {
    const available = ['english', 'german', 'latin'].filter((language) => String(entry[language] || '').trim());
    if (!available.length) return [];
    const original = ['german', 'latin'].find((language) => available.includes(language));
    const languages = state.language === 'original'
      ? ['english', original].filter(Boolean).filter((language) => available.includes(language))
      : ['english'].filter((language) => available.includes(language));
    return languages.length ? languages : available.slice(0, 1);
  }

  function languageMarkup(entry) {
    const displayedLanguages = displayedLanguagesFor(entry);
    if (!displayedLanguages.length) return '';
    return `<div class="text-grid ${displayedLanguages.length === 1 ? 'single' : ''}">${displayedLanguages.map((language) => `<div class="language"><div class="text">${markdownMarkup(entry[language], language === 'english')}</div></div>`).join('')}</div>`;
  }

  return { displayedLanguagesFor, languageMarkup };
}
