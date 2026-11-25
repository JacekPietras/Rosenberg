"""Conservative retry handling for read-only archive requests."""
import sys
import time
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'archive_utils'))
from archive_anubis import ANUBIS_CHALLENGE_RE


def retry_get(operation, delay=15, before_retry=None):
    """Retry one timed-out GET after a pause; propagate every other failure."""
    try:
        return operation()
    except HTTPError:
        raise
    except (TimeoutError, URLError) as exc:
        if isinstance(exc, URLError) and not isinstance(exc.reason, TimeoutError):
            raise
        pause = delay
        print(f'Request timed out; waiting {pause:g} seconds before one retry', file=sys.stderr)
        time.sleep(pause)
        if before_retry is not None:
            before_retry()
        return operation()


HTTP_500_RETRY_DELAYS = (5, 10, 20, 30, 60, 120, 240)


def retry_http_500(operation, before_retry=None):
    """Retry HTTP 403, 429 and 5xx errors on read-only archive requests."""
    for delay in HTTP_500_RETRY_DELAYS:
        try:
            return operation()
        except HTTPError as exc:
            if exc.code not in (403, 429) and not 500 <= exc.code < 600:
                raise
            if exc.code == 403 and exc.fp is not None:
                body = exc.read()
                if ANUBIS_CHALLENGE_RE.search(body.decode('utf-8', 'replace')):
                    exc.close()
                    raise HTTPError(exc.url, exc.code, exc.reason, exc.headers, BytesIO(body)) from exc
            exc.close()
            print(f'HTTP {exc.code}; waiting {delay} seconds before retry', file=sys.stderr, flush=True)
            time.sleep(delay)
            if before_retry is not None:
                before_retry()
    return operation()
