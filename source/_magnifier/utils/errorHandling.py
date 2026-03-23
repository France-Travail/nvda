# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2026 NV Access Limited
# This file may be used under the terms of the GNU General Public License, version 2 or later, as modified by the NVDA license.
# For full terms and any additional permissions, see the NVDA license file: https://github.com/nvaccess/nvda/blob/master/copying.txt

"""
Error handling helpers for the magnifier module.
"""

from collections.abc import Callable
from functools import wraps
from logHandler import log
from typing import Literal, ParamSpec, TypeVar, overload


# ParamSpec captures the full parameter signature of a callable (names, types, defaults).
# TypeVar captures the return type.
# Together they allow the decorator to preserve the exact signature of the wrapped function,
# so callers and type checkers see the original parameters and return type unchanged.
_P = ParamSpec("_P")
_R = TypeVar("_R")


# These two @overload signatures are for the type checker only — they never run at runtime.
# They express two distinct contracts depending on the value of `swallow`:
#   - swallow=False (default): the decorated function always returns _R (never None).
#   - swallow=True:            the decorated function may return None on OSError.
# Without @overload, the type checker could not distinguish the two cases and would
# infer _R | None for every usage, even when swallow=False guarantees _R.
@overload
def trackNativeMagnifierErrors(
	operation: str,
	*,
	swallow: Literal[False] = ...,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]: ...


@overload
def trackNativeMagnifierErrors(
	operation: str,
	*,
	swallow: Literal[True],
) -> Callable[[Callable[_P, _R]], Callable[_P, _R | None]]: ...


def trackNativeMagnifierErrors(
	operation: str,
	*,
	swallow: bool = False,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R | None]]:
	"""
	Create a decorator for native magnifier API calls.

	This decorator handles only OSError, which is what our Windows/native
	bindings raise when an API call fails. Any other exception is re-raised,
	so programming bugs are not hidden.

	:param operation: Human-readable operation name included in log messages.
	:param swallow: If True, catch OSError, log at debug level and return None.
	               If False (default), catch OSError, log at error level and re-raise.
	"""

	# _decorator is the actual decorator returned to the @ syntax.
	# It receives the function to wrap (func) and returns _wrapped in its place.
	def _decorator(func: Callable[_P, _R]) -> Callable[_P, _R | None]:
		# @wraps copies __name__, __doc__, __module__ and __qualname__ from func
		# onto _wrapped, so the wrapped method keeps its original identity in
		# logs, debuggers and stack traces.
		@wraps(func)
		def _wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R | None:
			try:
				return func(*args, **kwargs)
			except OSError:
				# Build a log message that identifies both the logical operation
				# (e.g. "MagInitialize") and the exact Python path of the failing
				# method (e.g. "FullScreenMagnifier._initializeNativeMagnification"),
				# so the error is actionable without needing a full stack trace.
				functionPath = f"{func.__module__}.{func.__qualname__}"
				message = f"Native magnifier operation failed: {operation} ({functionPath})"
				if swallow:
					# Non-critical path: the caller does not need to know about
					# the failure. Log at debug level (visible only in debug builds)
					# and return None so execution continues normally.
					log.debug(message, exc_info=True)
					return None
				# Critical path: log at error level so it appears in release logs,
				# then re-raise so the caller (e.g. _attemptRecovery) can handle it.
				log.error(message, exc_info=True)
				raise

		return _wrapped

	return _decorator
