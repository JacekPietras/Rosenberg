import { startApplication } from './app/bootstrap.js?v=56';

Promise.resolve().then(() => startApplication()).catch((error) => {
  const status = document.querySelector('#status');
  if (status) {
    const detail = error instanceof Error ? error.message : String(error);
    status.textContent = `Could not start the viewer: ${detail}`;
    status.classList.add('error');
  }
  console.error('Could not start the Rosenberg viewer.', error);
});
