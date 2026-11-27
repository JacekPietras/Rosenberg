const SELECTOR_ID = 'record-label-selector';

function labelsFor(document) {
  const value = document?.label;
  return (Array.isArray(value) ? value : [value])
    .map((label) => String(label || '').trim())
    .filter(Boolean);
}

function capitalizeFirst(label) {
  return label ? label[0].toLocaleUpperCase() + label.slice(1) : label;
}

export function setupRecordLabelSelector({ state, repository, rerender, escapeHtml, distinctFamilies = new Set(), markSaved = () => {} }) {
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
    const imageButton = event.target.closest('[data-delete-image-path]');
    if (imageButton) {
      const path = imageButton.dataset.deleteImagePath;
      const entryIndex = Number(imageButton.dataset.entryIndex);
      const imageIndex = Number(imageButton.dataset.imageIndex);
      const doc = state.documents.get(path);
      const entry = doc?.entries?.[entryIndex];
      const images = Array.isArray(entry?.img) ? entry.img : [entry?.img];
      const image = images[imageIndex];
      if (!state.canEditDocuments || state.active !== 'documents' || !path.startsWith('data/documents/') || !image || image.deleted) return;
      const updatedImages = images.map((item, index) => index === imageIndex
        ? { ...(typeof item === 'string' ? { src: item } : item), deleted: true } : item);
      const updated = { ...doc, entries: doc.entries.map((item, index) => index === entryIndex
        ? { ...item, img: Array.isArray(entry.img) ? updatedImages : updatedImages[0] } : item) };
      const status = imageButton.parentElement.querySelector('.document-image-status');
      imageButton.disabled = true;
      try {
        const result = await repository.saveDocument(path, updated);
        state.documents.set(path, updated);
        markSaved(path, result.version);
        await rerender();
      } catch (error) {
        if (status) status.textContent = `Could not remove image: ${error.message}`;
        imageButton.disabled = false;
      }
      return;
    }

    const reviewLabelsButton = event.target.closest('[data-show-review-labels]');
    if (reviewLabelsButton) {
      const path = reviewLabelsButton.dataset.showReviewLabels;
      const article = reviewLabelsButton.closest('.document');
      const doc = state.documents.get(path);
      const aside = article?.querySelector('.document-heading-aside');
      if (!doc || !aside || !state.renderReviewNameLabels) return;
      const html = await state.renderReviewNameLabels(doc, path);
      const target = article.querySelector('.review-name-mentions');
      if (target) {
        if (html) target.outerHTML = html;
        else target.remove();
      } else if (html) aside.insertAdjacentHTML('beforeend', html);
      reviewLabelsButton.remove();
      return;
    }

    const splitButton = event.target.closest('[data-split-document]');
    if (splitButton) {
      const path = splitButton.dataset.splitDocument;
      const doc = state.documents.get(path);
      if (!doc || !state.canEditDocuments || !path.startsWith('data/documents/')) return;
      const labels = labelsFor(doc);
      if (labels.some((label) => label.toLocaleLowerCase() === 'split')) return;
      const updated = { ...doc, label: [...labels, 'Split'] };
      const status = splitButton.closest('.document-heading-aside')?.querySelector('.record-delete-status');
      splitButton.disabled = true;
      if (status) status.textContent = 'Saving…';
      try {
        const result = await repository.saveDocument(path, updated);
        state.documents.set(path, updated);
        markSaved(path, result.version);
        await rerender();
      } catch (error) {
        if (status) status.textContent = `Could not save labels: ${error.message}`;
        splitButton.disabled = false;
      }
      return;
    }

    const deleteDocumentButton = event.target.closest('[data-delete-document]');
    if (deleteDocumentButton) {
      const path = deleteDocumentButton.dataset.deleteDocument;
      if (!state.documents.has(path) || !state.canEditDocuments || !path.startsWith('data/documents/')) return;
      const controls = deleteDocumentButton.closest('.document-heading-aside');
      const status = controls?.querySelector('.record-delete-status');
      deleteDocumentButton.disabled = true;
      if (status) status.textContent = 'Moving to deleted…';
      try {
        await repository.deleteDocument(path);
        state.documents.delete(path);
        state.manifest.documents = state.manifest.documents.filter((recordPath) => recordPath !== path);
        if (state.active === path) state.active = 'documents';
        if (state.record === path) {
          state.record = null;
          state.recordSource = null;
        }
        if (state.navigationRecord === path) {
          state.navigationRecord = null;
          state.navigationRecordSource = null;
        }
        await rerender();
      } catch (error) {
        if (status) status.textContent = `Could not delete: ${error.message}`;
        deleteDocumentButton.disabled = false;
      }
      return;
    }

    const editButton = event.target.closest('[data-edit-record-labels]');
    if (editButton) {
      activePath = editButton.dataset.editRecordLabels;
      const current = new Set(labelsFor(state.documents.get(activePath)).map((label) => label.toLocaleLowerCase()));
      const choices = new Map();
      distinctFamilies.forEach((label) => {
        choices.set(label.toLocaleLowerCase(), capitalizeFirst(label));
      });
      state.manifest.documents.forEach((path) => labelsFor(state.documents.get(path)).forEach((label) => {
        if (!choices.has(label.toLocaleLowerCase())) choices.set(label.toLocaleLowerCase(), label);
      }));
      fieldset.innerHTML = `<legend>Labels</legend>${[...choices.values()]
        .sort((left, right) => {
          const leftIsDistinctFamily = distinctFamilies.has(left.toLocaleLowerCase());
          const rightIsDistinctFamily = distinctFamilies.has(right.toLocaleLowerCase());
          if (leftIsDistinctFamily !== rightIsDistinctFamily) return leftIsDistinctFamily ? 1 : -1;
          return left.localeCompare(right, undefined, { sensitivity: 'base' });
        })
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
