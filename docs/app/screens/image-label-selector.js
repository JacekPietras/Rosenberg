const SELECTOR_ID = 'image-label-selector';
const IMAGE_PATH = 'data/images/images.json';

export function setupImageLabelSelector({ state, repository, rerender, escapeHtml }) {
  let activeIndex = null;
  let dialog = document.getElementById(SELECTOR_ID);
  if (!dialog) {
    document.body.insertAdjacentHTML('beforeend', `
      <dialog id="${SELECTOR_ID}" class="letter-label-dialog" aria-labelledby="image-label-title">
        <form method="dialog" class="image-label-dialog-form">
          <h2 id="image-label-title">Edit image label</h2>
          <label for="image-label-input">Label</label>
          <input id="image-label-input" type="text" list="image-label-choices" autocomplete="off">
          <datalist id="image-label-choices"></datalist>
          <p class="letter-label-status" role="status" aria-live="polite"></p>
          <div class="letter-label-dialog-actions">
            <button type="button" data-image-label-action="cancel">Cancel</button>
            <button type="button" data-image-label-action="save">Save</button>
          </div>
        </form>
      </dialog>`);
    dialog = document.getElementById(SELECTOR_ID);
  }

  const input = dialog.querySelector('#image-label-input');
  const choices = dialog.querySelector('#image-label-choices');
  const status = dialog.querySelector('.letter-label-status');
  const close = () => {
    activeIndex = null;
    dialog.close();
  };

  document.addEventListener('click', async (event) => {
    const editButton = event.target.closest('[data-edit-image-label]');
    if (editButton) {
      activeIndex = Number(editButton.dataset.editImageLabel);
      const documentData = state.documents.get(IMAGE_PATH);
      const entry = documentData?.entries?.[activeIndex];
      if (!entry) return;
      const labels = [...new Set((documentData.entries || [])
        .map((item) => String(item.label || '').trim())
        .filter(Boolean))]
        .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: 'base' }));
      choices.innerHTML = labels.map((label) => `<option value="${escapeHtml(label)}"></option>`).join('');
      input.value = String(entry.label || '');
      status.textContent = '';
      status.classList.remove('error');
      dialog.showModal();
      input.focus();
      return;
    }

    if (!dialog.open) return;
    const action = event.target.closest('[data-image-label-action]')?.dataset.imageLabelAction;
    if (action === 'cancel') {
      close();
      return;
    }
    if (action !== 'save' || activeIndex === null) return;

    const current = state.documents.get(IMAGE_PATH);
    const entries = [...(current?.entries || [])];
    const updatedEntry = { ...entries[activeIndex] };
    const label = input.value.trim();
    if (label) updatedEntry.label = label;
    else delete updatedEntry.label;
    entries[activeIndex] = updatedEntry;
    const updated = { ...current, entries };
    status.textContent = 'Saving…';
    status.classList.remove('error');
    dialog.querySelectorAll('button').forEach((button) => { button.disabled = true; });
    try {
      await repository.saveDocument(IMAGE_PATH, updated);
      state.documents.set(IMAGE_PATH, updated);
      state.snapshot = '';
      close();
      await rerender();
    } catch (error) {
      status.textContent = `Could not save label: ${error.message}`;
      status.classList.add('error');
    } finally {
      dialog.querySelectorAll('button').forEach((button) => { button.disabled = false; });
    }
  });

  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) close();
  });
}
