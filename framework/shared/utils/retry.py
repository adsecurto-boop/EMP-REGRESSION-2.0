"""Retry helpers with bounded backoff.

Note the distinction this module must not blur. It retries *the framework's own*
flaky operations (a file briefly locked, a transient read failure). It has
nothing to do with EmpMonitor's retry behaviour, which is an observed product
characteristic and evidence for a ``DEGRADED`` verdict
(``docs/design/Synchronization_Monitor.md`` §9). Never use this to paper over a
product failure -- retrying until the product looks healthy would manufacture a
false positive.

``docs/ADS/error_handling_standard.md`` §6 leaves the framework's own retry
policy open, so these helpers take an explicit policy per call site rather than
imposing a default one globally.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence, TypeVar

from framework.shared.exceptions import FrameworkError

__all__ = ["RetryPolicy", "retry_call", "RetryExhaustedError"]

T = TypeVar("T")


class RetryExhaustedError(FrameworkError):
    """Every retry attempt failed.

    Chains the final underlying exception via ``__cause__`` so the original
    failure is never lost -- swallowing it would violate the "no silent failure"
    principle.
    """


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry policy.

    Args:
        attempts: Total attempts, including the first. Must be at least 1.
        initial_delay: Delay before the second attempt, in seconds.
        multiplier: Factor applied to the delay after each failure.
        max_delay: Ceiling for the delay, in seconds.
        retry_on: Exception types that should be retried. Anything else
            propagates immediately -- retrying a deterministic error such as a
            configuration mistake only delays the report of it.
    """

    attempts: int = 3
    initial_delay: float = 0.5
    multiplier: float = 2.0
    max_delay: float = 10.0
    retry_on: Sequence[type[BaseException]] = (OSError,)

    def __post_init__(self) -> None:
        """Validate the policy.

        Raises:
            FrameworkError: If the policy values are not usable.
        """
        if self.attempts < 1:
            raise FrameworkError(
                "Retry policy requires at least one attempt", {"attempts": self.attempts}
            )
        if self.initial_delay < 0 or self.max_delay < 0:
            raise FrameworkError("Retry delays must not be negative")
        if self.multiplier < 1:
            raise FrameworkError(
                "Retry multiplier must be at least 1", {"multiplier": self.multiplier}
            )

    def delays(self) -> Iterable[float]:
        """Yield the delay before each retry, honouring the ceiling.

        Yields:
            Delay in seconds before each retry (one fewer than ``attempts``).
        """
        delay = self.initial_delay
        for _ in range(self.attempts - 1):
            yield min(delay, self.max_delay)
            delay *= self.multiplier


def retry_call(
    operation: Callable[[], T],
    policy: RetryPolicy | None = None,
    *,
    description: str = "operation",
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``operation``, retrying transient failures per ``policy``.

    Args:
        operation: Zero-argument callable to invoke.
        policy: Retry policy; a default bounded policy is used when omitted.
        description: Human-readable description used in the error message.
        sleep: Sleep function, injected so tests need not actually wait.

    Returns:
        The operation's return value.

    Raises:
        RetryExhaustedError: If every attempt failed with a retryable error.
        BaseException: Immediately, for any exception not listed in
            ``policy.retry_on``.
    """
    effective = policy or RetryPolicy()
    retryable = tuple(effective.retry_on)
    delays = list(effective.delays())
    last_error: BaseException | None = None

    for attempt in range(effective.attempts):
        try:
            return operation()
        except retryable as exc:  # noqa: PERF203 -- retry requires per-attempt handling
            last_error = exc
            if attempt < len(delays):
                sleep(delays[attempt])

    raise RetryExhaustedError(
        f"All retry attempts failed for {description}",
        {"attempts": effective.attempts},
    ) from last_error
