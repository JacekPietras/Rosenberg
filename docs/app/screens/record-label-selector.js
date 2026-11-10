const SELECTOR_ID = 'record-label-selector';

function labelsFor(document) {
  const value = document?.label;
  return (Array.isArray(value) ? value : [value])
    .map((label) => String(label || '').trim())
    .filter(Boolean);
}

export function setupRecordLabelSelector({ state, repository, rerender, escapeHtml, markSaved = () => {} }) {
  let activePath = null;
  let dialog = document.getElementById(SELECTOR_ID);
  if (!dialog) {
    document.body.insertAdjacentHTML('beforeend', `
      <dialog id="${SELECTOR_ID}" class="record-label-dialog" aria-labelledby="record-label-title">
        <form method="dialog" class="record-label-dialog-form">
          <h2 id="record-label-title">Edit record labels</h2>
          <fieldset class="record-label-options"><legend>Labels</legend></fieldset>
          <p class="record-label-status" role="status" aria-live="polite"></p>
          <div class="record-label-dialog-actions">
            <button type="button" data-label-action="cancel">Cancel</button>
            <button type="button" data-label-action="save">Save</button>
          </div>
        </form>
      </dialog>`);
    dialog = document.getElementById(SELECTOR_ID);
  }

  const fieldset = dialog.querySelector('.record-label-options');
  const status = dialog.querySelector('.record-label-status');
  const close = () => {
    activePath = null;
    dialog.close();
  };

  document.addEventListener('click', async (event) => {
    const deleteDocumentButton = event.target.closest('[data-delete-document]');
    if (deleteDocumentButton) {
      const path = deleteDocumentButton.dataset.deleteDocument;
      const original = state.documents.get(path);
      if (!original || !state.canEditDocuments || !path.startsWith('data/documents/')) return;
      const updated = { ...original, deleted: true };
      const controls = deleteDocumentButton.closest('.document-heading-aside');
      const status = controls?.querySelector('.record-delete-status');
      deleteDocumentButton.disabled = true;
      if (status) status.textContent = 'Saving…';
      try {
        const result = await repository.saveDocument(path, updated);
        state.documents.set(path, updated);
        markSaved(path, result.version);
        await rerender();
      } catch (error) {
        if (status) status.textContent = `Could not save: ${error.message}`;
        deleteDocumentButton.disabled = false;
      }
      return;
    }

    const reviewButton = event.target.closest('[data-review-action]');
    if (reviewButton) {
      const path = reviewButton.dataset.reviewPath;
      const original = state.documents.get(path);
      if (!original || !state.canEditDocuments) return;
      const updated = { ...original };
      if (reviewButton.dataset.reviewAction === 'delete') updated.deleted = true;
      else if (reviewButton.dataset.reviewAction === 'keep') {
        const labels = labelsFor(original).filter((label) => label.toLocaleLowerCase() !== 'to review');
        if (!labels.length) delete updated.label;
        else updated.label = labels.length === 1 ? labels[0] : labels;
      } else return;
      const controls = reviewButton.closest('.document-heading-aside');
      const status = controls.querySelector('.record-review-status');
      controls.querySelectorAll('[data-review-action]').forEach((button) => { button.disabled = true; });
      status.textContent = 'Saving…';
      try {
        const result = await repository.saveDocument(path, updated);
        state.documents.set(path, updated);
        markSaved(path, result.version);
        await rerender();
      } catch (error) {
        status.textContent = `Could not save: ${error.message}`;
        controls.querySelectorAll('[data-review-action]').forEach((button) => { button.disabled = false; });
      }
      return;
    }
    const editButton = event.target.closest('[data-edit-record-labels]');
    if (editButton) {
      activePath = editButton.dataset.editRecordLabels;
      const current = new Set(labelsFor(state.documents.get(activePath)).map((label) => label.toLocaleLowerCase()));
      const choices = new Map();
      state.manifest.documents.forEach((path) => labelsFor(state.documents.get(path)).forEach((label) => {
        if (!choices.has(label.toLocaleLowerCase())) choices.set(label.toLocaleLowerCase(), label);
      }));
      fieldset.innerHTML = `<legend>Labels</legend>${[...choices.values()]
        .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: 'base' }))
        .map((label) => `<label class="record-label-option"><input type="checkbox" value="${escapeHtml(label)}"${current.has(label.toLocaleLowerCase()) ? ' checked' : ''}>${escapeHtml(label)}</label>`)
        .join('')}`;
      status.textContent = '';
      status.classList.remove('error');
      dialog.showModal();
      return;
    }

    if (!dialog.open) return;
    const action = event.target.closest('[data-label-action]')?.dataset.labelAction;
    if (action === 'cancel') {
      close();
      return;
    }
    if (action !== 'save' || !activePath) return;

    const selected = [...fieldset.querySelectorAll('input[type="checkbox"]:checked')].map((input) => input.value);
    const updated = { ...state.documents.get(activePath) };
    if (!selected.length) delete updated.label;
    else updated.label = selected.length === 1 ? selected[0] : selected;
    status.textContent = 'Saving…';
    status.classList.remove('error');
    dialog.querySelectorAll('button').forEach((button) => { button.disabled = true; });
    try {
      const result = await repository.saveDocument(activePath, updated);
      state.documents.set(activePath, updated);
      markSaved(activePath, result.version);
      close();
      await rerender();
    } catch (error) {
      status.textContent = `Could not save labels: ${error.message}`;
      status.classList.add('error');
    } finally {
      dialog.querySelectorAll('button').forEach((button) => { button.disabled = false; });
    }
  });

  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) close();
  });
}
