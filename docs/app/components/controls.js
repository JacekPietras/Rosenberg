export function setupControls({ state, repository, updateLanguageControl, updateFactsControl, applyTheme, applyMermaidTheme, savePreferences, rerender }) {
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
  const savePush = document.querySelector('#local-save-push');
  const updateSaveVisibility = async () => {
    if (!savePush) return;
    try {
      const response = await fetch('/api/git-status', { cache: 'no-store' });
      if (!response.ok) return;
      const status = await response.json();
      savePush.hidden = !status.changed;
    } catch {}
  };
  repository.isLocalServer().then((isLocal) => {
    if (isLocal) {
      updateSaveVisibility();
      window.setInterval(updateSaveVisibility, 3000);
    }
  });
  savePush?.addEventListener('click', async () => {
    savePush.disabled = true;
    savePush.title = 'Saving and pushing…';
    savePush.setAttribute('aria-label', 'Saving and pushing changes');
    try {
      const response = await fetch('/api/save-and-push', { method: 'POST' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Save failed (${response.status})`);
      savePush.title = result.changed ? 'Changes committed and pushed' : 'No changes to save';
      savePush.setAttribute('aria-label', savePush.title);
      savePush.hidden = true;
    } catch (error) {
      savePush.title = `Could not commit and push: ${error.message}`;
      savePush.setAttribute('aria-label', savePush.title);
      window.alert(savePush.title);
    } finally {
      savePush.disabled = false;
    }
  });
}
