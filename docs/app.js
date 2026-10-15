import { startApplication } from './app/bootstrap.js?v=81';

const localRefresh = document.querySelector('#local-refresh');
if (localRefresh) {
  fetch('/api/local-server', { cache: 'no-store' }).then((response) => {
    if (response.ok) {
      localRefresh.hidden = false;
      const heartbeat = () => fetch('/api/heartbeat', { method: 'POST', keepalive: true }).catch(() => {});
      heartbeat();
      window.setInterval(heartbeat, 1000);
    }
  }).catch(() => {});

  localRefresh.addEventListener('click', async () => {
    localRefresh.disabled = true;
    try {
      await fetch('/api/restart-server', { method: 'POST' });
      for (let attempt = 0; attempt < 80; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 250));
        try {
          if ((await fetch('/api/local-server', { cache: 'no-store' })).ok) {
            location.reload();
            return;
          }
        } catch {}
      }
      throw new Error('Local server did not come back online');
    } catch (error) {
      localRefresh.disabled = false;
      console.error('Could not restart the local server.', error);
      window.alert(`Could not restart the local server: ${error.message}`);
    }
  });
}

Promise.resolve().then(() => startApplication()).catch((error) => {
  const status = document.querySelector('#status');
  if (status) {
    const detail = error instanceof Error ? error.message : String(error);
    status.textContent = `Could not start the viewer: ${detail}`;
    status.classList.add('error');
  }
  console.error('Could not start the Rosenberg viewer.', error);
});
