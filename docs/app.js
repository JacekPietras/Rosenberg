import { startApplication } from './app/bootstrap.js?v=208';

const localRefresh = document.querySelector('#local-refresh');
if (localRefresh) {
  const diagnosticKey = 'rosenberg-heartbeat-diagnostic';
  const sentKey = 'rosenberg-heartbeat-last-sent';
  const saveDiagnostic = (message) => {
    console.error(message);
    try { localStorage.setItem(diagnosticKey, `${new Date().toISOString()} ${message}`); } catch {}
  };
  const flushStored = async (key, prefix = '') => {
    try {
      const stored = localStorage.getItem(key);
      if (!stored) return;
      const response = await fetch('/api/heartbeat-diagnostics', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: prefix + stored }),
      });
      if (response.ok && localStorage.getItem(key) === stored) localStorage.removeItem(key);
    } catch {}
  };
  const flushDiagnostic = () => flushStored(diagnosticKey);
  const flushLastSent = () => flushStored(sentKey, 'Last heartbeat attempted by browser: ');
  fetch('/api/local-server', { cache: 'no-store' }).then((response) => {
    if (response.ok) {
      localRefresh.hidden = false;
      flushDiagnostic();
      flushLastSent();
      let heartbeatFailed = false;
      const heartbeat = () => {
        const sentAt = new Date().toISOString();
        try { localStorage.setItem(sentKey, sentAt); } catch {}
        return fetch('/api/heartbeat', {
          method: 'POST', keepalive: true, headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sentAt }),
        }).then((result) => {
        if (!result.ok) throw new Error(`HTTP ${result.status}`);
        if (heartbeatFailed) {
          console.info('Local server heartbeat recovered.');
          flushDiagnostic();
          flushLastSent();
        }
        heartbeatFailed = false;
      }).catch((error) => {
        if (!heartbeatFailed) saveDiagnostic(`Local server heartbeat failed: ${error}`);
        heartbeatFailed = true;
      });
      };
      heartbeat();
      window.setInterval(heartbeat, 1000);
    } else {
      saveDiagnostic(`Local server heartbeat was not started: server probe returned HTTP ${response.status}.`);
    }
  }).catch((error) => saveDiagnostic(`Local server heartbeat was not started: server probe failed: ${error}`));

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
