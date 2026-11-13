import os
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_url(endpoint, params):
    return endpoint + ("&" if "?" in endpoint else "?") + urlencode(params)


def get(url, attempts=4):
    """TLS is always checked; SSL_CERT_FILE supports organisation-specific CAs."""
    context = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE"))
    req = Request(url, headers={"User-Agent": "behoerden-resolver/0.1 (public-geodata ETL)",
                                "Accept": "application/json, application/xml, text/xml"})
    for attempt in range(attempts):
        try:
            with urlopen(req, context=context, timeout=120) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise RuntimeError(f"HTTP {exc.code}: {url}: {exc.read(600).decode(errors='replace')}") from exc
            delay = exc.headers.get("Retry-After", "")
            time.sleep(min(int(delay), 30) if delay.isdigit() else 2 ** attempt)
        except (URLError, TimeoutError, OSError):
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)
