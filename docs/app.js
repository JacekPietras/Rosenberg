import { startApplication } from './app/bootstrap.js?v=209';

const localRefresh = document.querySelector('#local-refresh');
if (localRefresh) {
  const diagnosticKey = 'rosenberg-heartbeat-diagnostic';
  const sentKey = 'rosenberg-heartbeat-last-sent';
  const historyKey = 'rosenberg-heartbeat-history';
  const heartbeatUrl = new URL('/api/heartbeat', window.location.href);
  if (heartbeatUrl.hostname === 'localhost') heartbeatUrl.hostname = '127.0.0.1';
  else if (heartbeatUrl.hostname === '127.0.0.1') heartbeatUrl.hostname = 'localhost';
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
  const flushHistory = async () => {
    try {
      const history = sessionStorage.getItem(historyKey);
      if (!history) return;
      const response = await fetch('/api/heartbeat-diagnostics', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `Browser heartbeat attempts (UTC, visibility): ${history}` }),
      });
      if (response.ok && sessionStorage.getItem(historyKey) === history) sessionStorage.removeItem(historyKey);
    } catch {}
  };
  fetch('/api/local-server', { cache: 'no-store' }).then((response) => {
    if (response.ok) {
      localRefresh.hidden = false;
      fetch('/api/heartbeat-diagnostics', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `Heartbeat URL selected by page ${window.location.origin}: ${heartbeatUrl.href}` }),
      }).catch(() => {});
      flushDiagnostic();
      flushLastSent();
      flushHistory();
      let heartbeatFailed = false;
      let lastHeartbeatResponse = performance.now();
      const heartbeat = () => {
        const sentAt = new Date().toISOString();
        try { localStorage.setItem(sentKey, sentAt); } catch {}
        try {
          const history = JSON.parse(sessionStorage.getItem(historyKey) || '[]');
          history.push(`${sentAt} ${document.visibilityState}`);
          sessionStorage.setItem(historyKey, JSON.stringify(history.slice(-80)));
        } catch {}
        return fetch(heartbeatUrl.href, {
          method: 'POST', keepalive: true, headers: { 'Content-Type': 'text/plain' },
          body: JSON.stringify({ sentAt }),
        }).then((result) => {
        if (!result.ok) throw new Error(`HTTP ${result.status}`);
        const responseGap = performance.now() - lastHeartbeatResponse;
        lastHeartbeatResponse = performance.now();
        if (responseGap >= 20000) flushHistory();
        if (heartbeatFailed) {
          console.info('Local server heartbeat recovered.');
          flushDiagnostic();
          flushLastSent();
          flushHistory();
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
