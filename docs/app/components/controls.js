export function setupControls({ state, updateLanguageControl, updateFactsControl, applyTheme, applyMermaidTheme, savePreferences, rerender }) {
  const languageToggle = document.querySelector('#language-toggle');
  updateLanguageControl();
  updateFactsControl();
  languageToggle.addEventListener('click', () => {
    state.language = state.language === 'english' ? 'original' : 'english';
    updateLanguageControl();
    savePreferences();
    rerender();
  });
  const factsToggle = document.querySelector('#facts-toggle');
  factsToggle.addEventListener('click', () => {
    state.showFacts = !state.showFacts;
    updateFactsControl();
    savePreferences();
    rerender();
  });
  const themeToggle = document.querySelector('#theme-toggle');
  themeToggle.addEventListener('click', () => {
    state.darkMode = !state.darkMode;
    applyTheme();
    applyMermaidTheme();
    savePreferences();
    rerender();
  });
}
