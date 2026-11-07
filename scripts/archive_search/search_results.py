"""Store verified archive query existence results in publishable JSON."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ResultsStore:
    def __init__(self, archive, path=None):
        self.archive = archive
        self.path = Path(path) if path is not None else ROOT / 'data/archive_search' / f'{archive}.json'

    def _locked(self, query, check=None, value=None, lookup=False):
        lock_dir = ROOT / '.cache/archive_search/variation_locks'
        lock_dir.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(str(self.path.resolve()).encode()).hexdigest() + '.lock'
        with (lock_dir / name).open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if (not isinstance(data, dict) or data.get('archive') != self.archive
                        or not isinstance(data.get('queries'), dict)
                        or any(not isinstance(k, str) or not isinstance(v, bool)
                               for k, v in data['queries'].items())):
                    raise ValueError(f'Invalid results file: {self.path}')
            else:
                data = {'archive': self.archive, 'queries': {}}
            if lookup:
                return data['queries'].get(query)
            if check is not None and query in data['queries']:
                return data['queries'][query]
            found = check() if check is not None else value
            if not isinstance(found, bool):
                raise ValueError('Existence result must be a boolean')
            if data['queries'].get(query) is found:
                return found
            data['queries'][query] = found
            data['queries'] = dict(sorted(data['queries'].items()))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent, delete=False) as temp:
                    temp_path = Path(temp.name)
                    json.dump(data, temp, ensure_ascii=False, indent=2)
                    temp.write('\n')
                os.replace(temp_path, self.path)
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)
            return found

    def get(self, query):
        return self._locked(query, lookup=True)

    def exists(self, query, check):
        return self._locked(query, check=check)

    def record(self, query, found):
        return self._locked(query, value=found)
