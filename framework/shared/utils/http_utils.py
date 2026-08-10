"""Minimal HTTP transport helpers.

Generic transport built on :mod:`urllib.request`, so the framework has no
third-party HTTP dependency.

**Scope boundary — read before using.** This module knows nothing about
EmpMonitor's API. No endpoints, no authentication scheme, no payload shapes; the
API contract is unverified (``knowledge_base/RE-006``) and calling product APIs
is not Phase 1 work.

It also does not settle the open architectural question in
``docs/design/Synchronization_Monitor.md`` §6: how Layer 3 activity should be
observed is still an unresolved spike, and the design defaults to *passive*
observation. The existence of this helper must not be read as endorsing active
request injection or proxy interception. Whatever the spike concludes, this
remains generic transport, not a sanctioned observation strategy.

The framework never handles credentials. Callers must not pass secrets in URLs
(``docs/ADS/logging_standard.md`` §8); pass headers explicitly and keep them out
of logs.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping

from framework.shared.exceptions import FrameworkError

__all__ = ["HttpResponse", "request", "get", "post_json", "build_url"]

_DEFAULT_TIMEOUT = 15.0


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """An HTTP response.

    Args:
        status: HTTP status code.
        headers: Response headers.
        body: Response body as text.
        url: Final URL, after any redirects.
        elapsed_seconds: Wall-clock duration of the request.
    """

    status: int
    body: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        """Whether the status code indicates success (2xx)."""
        return 200 <= self.status < 300

    def json(self) -> Any:
        """Parse the body as JSON.

        Returns:
            The parsed value.

        Raises:
            FrameworkError: If the body is not valid JSON.
        """
        try:
            return json.loads(self.body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise FrameworkError(
                "Response body is not valid JSON", {"url": self.url, "status": self.status}
            ) from exc


def build_url(base: str, path: str = "", params: Mapping[str, Any] | None = None) -> str:
    """Join a base URL, path, and query parameters.

    Args:
        base: Base URL.
        path: Path to append.
        params: Query parameters.

    Returns:
        The composed URL.

    Note:
        Never place personal or sensitive data in query parameters.
    """
    url = base.rstrip("/")
    if path:
        url = f"{url}/{path.lstrip('/')}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    return url


def request(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> HttpResponse:
    """Perform an HTTP request.

    Non-2xx responses are returned rather than raised: for an observing
    framework a 401 or 500 is *evidence*, not an error, and a collector needs to
    record it rather than have it thrown away as an exception.

    Args:
        url: Target URL.
        method: HTTP method.
        headers: Request headers.
        body: Request body bytes.
        timeout: Timeout in seconds.

    Returns:
        The response, including the status code for non-2xx results.

    Raises:
        FrameworkError: Only for transport-level failures (DNS, connection,
            timeout) where no response was received at all.
    """
    import time  # noqa: PLC0415 -- local import keeps module import cost minimal

    if not url.lower().startswith(("http://", "https://")):
        raise FrameworkError("Only http and https URLs are supported", {"url": url})

    prepared = urllib.request.Request(  # noqa: S310 -- scheme validated above
        url, data=body, method=method.upper(), headers=dict(headers or {})
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(prepared, timeout=timeout) as response:  # noqa: S310
            payload = response.read().decode("utf-8", errors="replace")
            return HttpResponse(
                status=int(response.status),
                body=payload,
                url=str(response.url),
                headers={key.lower(): value for key, value in response.headers.items()},
                elapsed_seconds=time.perf_counter() - started,
            )
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return HttpResponse(
            status=int(exc.code),
            body=payload,
            url=url,
            headers={key.lower(): value for key, value in (exc.headers or {}).items()},
            elapsed_seconds=time.perf_counter() - started,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FrameworkError(
            "HTTP request failed at transport level", {"url": url, "method": method}
        ) from exc


def get(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> HttpResponse:
    """Perform a GET request.

    Args:
        url: Target URL.
        headers: Request headers.
        timeout: Timeout in seconds.

    Returns:
        The response.
    """
    return request(url, method="GET", headers=headers, timeout=timeout)


def post_json(
    url: str,
    payload: Any,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> HttpResponse:
    """Perform a POST request with a JSON body.

    Args:
        url: Target URL.
        payload: Value to serialise as the request body.
        headers: Additional request headers.
        timeout: Timeout in seconds.

    Returns:
        The response.

    Raises:
        FrameworkError: If the payload cannot be serialised or transport fails.
    """
    try:
        encoded = json.dumps(payload, default=str).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FrameworkError("Request payload could not be serialised") from exc
    merged = {"content-type": "application/json", **{k.lower(): v for k, v in (headers or {}).items()}}
    return request(url, method="POST", headers=merged, body=encoded, timeout=timeout)
