"""Conservative retry handling for read-only archive requests."""
import sys
import time
from urllib.error import HTTPError, URLError


def retry_get(operation, delay=15, before_retry=None):
    """Retry one timed-out GET after a pause; propagate every other failure."""
    try:
        return operation()
    except HTTPError:
        raise
    except (TimeoutError, URLError) as exc:
        if isinstance(exc, URLError) and not isinstance(exc.reason, TimeoutError):
            raise
        pause = max(15, delay)
        print(f'Request timed out; waiting {pause:g} seconds before one retry', file=sys.stderr)
        time.sleep(pause)
        if before_retry is not None:
            before_retry()
        return operation()
