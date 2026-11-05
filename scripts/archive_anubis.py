"""Shared support for Anubis SHA-256 proof-of-work pages."""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
from urllib.parse import urlencode, urljoin, urlsplit

ANUBIS_CHALLENGE_RE = re.compile(
    r'<script\s+id=["\']anubis_challenge["\']\s+type=["\']application/json["\']\s*>(.*?)</script>',
    re.I | re.S,
)
BASE_PREFIX_RE = re.compile(
    r'<script\s+id=["\']anubis_base_prefix["\']\s+type=["\']application/json["\']\s*>(.*?)</script>',
    re.I | re.S,
)


def solve_anubis(page: bytes, page_url: str) -> str | None:
    """Return a challenge response URL, or None when the page has no challenge."""
    text = page.decode('utf-8', 'replace')
    match = ANUBIS_CHALLENGE_RE.search(text)
    if not match:
        return None
    data = json.loads(html.unescape(match.group(1)))
    challenge, rules = data['challenge'], data.get('rules', {})
    algorithm = rules.get('algorithm')
    if algorithm is not None and algorithm not in {'fast', 'slow', 'preact'}:
        raise ValueError(f'Unsupported Anubis algorithm: {algorithm!r}')
    difficulty = int(rules.get('difficulty', challenge.get('difficulty', 0)))
    if not 0 <= difficulty <= 64:
        raise ValueError('Invalid Anubis difficulty')
    seed = challenge['randomData'].encode()
    started = time.monotonic()
    for nonce in range(10_000_000):
        digest = hashlib.sha256(seed + str(nonce).encode()).hexdigest()
        if digest.startswith('0' * difficulty):
            break
    else:
        raise ValueError(f'Anubis proof-of-work difficulty {difficulty} exceeded the nonce limit')
    prefix_match = BASE_PREFIX_RE.search(text)
    prefix = json.loads(html.unescape(prefix_match.group(1))) if prefix_match else ''
    if not isinstance(prefix, str) or (prefix and (not prefix.startswith('/') or prefix.startswith('//'))):
        raise ValueError('Invalid Anubis base prefix')
    pass_url = urljoin(page_url, prefix.rstrip('/') + '/.within.website/x/cmd/anubis/api/pass-challenge')
    if urlsplit(pass_url).netloc != urlsplit(page_url).netloc:
        raise ValueError('Unexpected Anubis challenge host')
    return pass_url + '?' + urlencode({
        'id': challenge['id'], 'response': digest, 'nonce': nonce,
        'redir': page_url, 'elapsedTime': max(1, int((time.monotonic() - started) * 1000)),
    })
