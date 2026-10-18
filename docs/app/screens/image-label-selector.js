import { imageLabels } from '../image-labels.js';

const SELECTOR_ID = 'image-label-selector';
const IMAGE_PATH = 'data/images/images.json';

export function setupImageLabelSelector({ state, repository, rerender, escapeHtml }) {
  let activeIndex = null;
  let dialog = document.getElementById(SELECTOR_ID);
  if (!dialog) {
    document.body.insertAdjacentHTML('beforeend', `
      <dialog id="${SELECTOR_ID}" class="letter-label-dialog" aria-labelledby="image-label-title">
        <form method="dialog" class="image-label-dialog-form">
          <h2 id="image-label-title">Edit image labels</h2>
          <fieldset class="letter-label-options"><legend>Labels</legend></fieldset>
          <label for="image-label-input">Add a label</label>
          <input id="image-label-input" type="text" autocomplete="off">
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
  const fieldset = dialog.querySelector('.letter-label-options');
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
        .flatMap((item) => imageLabels(item)))]
        .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: 'base' }));
      const current = new Set(imageLabels(entry));
      fieldset.innerHTML = `<legend>Labels</legend>${labels.map((label) => `<label class="letter-label-option"><input type="checkbox" value="${escapeHtml(label)}"${current.has(label) ? ' checked' : ''}>${escapeHtml(label)}</label>`).join('')}`;
      input.value = '';
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
    const labels = imageLabels({ label: [
      ...[...fieldset.querySelectorAll('input[type="checkbox"]:checked')].map((option) => option.value),
      input.value,
    ] });
    if (labels.length) updatedEntry.label = labels.length === 1 ? labels[0] : labels;
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
