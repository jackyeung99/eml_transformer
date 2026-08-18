import cProfile
import io
import logging
import pstats

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from eml_transformer.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def profile(
    *,
    sort_by: str = "cumulative",
    limit: int = 40,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def decorator(function: Callable[P, T]) -> Callable[P, T]:
        @wraps(function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            profiler = cProfile.Profile()
            profiler.enable()

            try:
                return function(*args, **kwargs)
            finally:
                profiler.disable()

                output = io.StringIO()
                stats = pstats.Stats(
                    profiler,
                    stream=output,
                )

                stats.strip_dirs()
                stats.sort_stats(sort_by)
                stats.print_stats(limit)

                logger.info(
                    "Profile | function=%s.%s\n%s",
                    function.__module__,
                    function.__qualname__,
                    output.getvalue(),
                )

        return wrapper

    return decorator