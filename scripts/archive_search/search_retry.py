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
        pause = delay
        print(f'Request timed out; waiting {pause:g} seconds before one retry', file=sys.stderr)
        time.sleep(pause)
        if before_retry is not None:
            before_retry()
        return operation()


HTTP_500_RETRY_DELAYS = (5, 10, 20, 30, 60, 120, 240)


def retry_http_500(operation, before_retry):
    """Retry an HTTP 500 from a read-only archive request with backoff."""
    for delay in HTTP_500_RETRY_DELAYS:
        try:
            return operation()
        except HTTPError as exc:
            if exc.code != 500:
                raise
            exc.close()
            print(f'HTTP 500; waiting {delay} seconds before retry', file=sys.stderr, flush=True)
            time.sleep(delay)
            before_retry()
    return operation()
