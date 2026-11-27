export function setupDocumentTextEditor({ state, repository, renderText, markSaved }) {
  let pendingSave = Promise.resolve();
  document.addEventListener('click', (event) => {
    if (event.detail !== 3) return;
    const field = event.target.closest('[data-document-text-path]');
    if (!field || !state.canEditDocuments || field.querySelector('textarea')) return;
    const { documentTextPath: path, documentTextLanguage: language } = field.dataset;
    const index = Number(field.dataset.documentTextIndex);
    const entry = state.documents.get(path)?.entries?.[index];
    if (!entry || !['english', 'german', 'latin'].includes(language)) return;

    const original = field.innerHTML;
    const textarea = document.createElement('textarea');
    textarea.className = 'document-text-input';
    textarea.setAttribute('aria-label', `Edit ${language} text`);
    textarea.value = entry[language] || '';
    textarea.rows = Math.max(5, Math.min(20, textarea.value.split('\n').length + 1));
    const actions = document.createElement('div');
    actions.className = 'document-text-actions';
    const save = document.createElement('button');
    save.type = 'button';
    save.textContent = 'Save';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.textContent = 'Cancel';
    const status = document.createElement('span');
    status.setAttribute('role', 'status');
    actions.append(save, cancel, status);
    field.replaceChildren(textarea, actions);
    textarea.focus();
    cancel.addEventListener('click', () => { field.innerHTML = original; });
    save.addEventListener('click', async () => {
      save.disabled = true;
      cancel.disabled = true;
      textarea.disabled = true;
      status.textContent = 'Saving…';
      try {
        const value = textarea.value;
        const operation = pendingSave.catch(() => {}).then(async () => {
          const doc = state.documents.get(path);
          if (!doc?.entries?.[index]) throw new Error('Document is no longer available.');
          const updated = { ...doc, entries: doc.entries.map((item, i) => i === index ? { ...item, [language]: value } : item) };
          const result = await repository.saveDocument(path, updated);
          state.documents.set(path, updated);
          markSaved(path, result.version);
        });
        pendingSave = operation;
        await operation;
        field.innerHTML = renderText(value, language === 'english');
      } catch (error) {
        status.textContent = `Could not save: ${error.message}`;
        save.disabled = false;
        cancel.disabled = false;
        textarea.disabled = false;
      }
    });
  });
}
