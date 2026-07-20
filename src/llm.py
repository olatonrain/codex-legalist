"""LLM client factory — creates Qwen chat and structured-output model instances."""
import logging
import os
import time

from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0


def _retry_on_api_error(func, *args, **kwargs):
    """Call func with retry + exponential backoff on transient API errors."""
    last_exc = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except (APIConnectionError, RateLimitError) as exc:
            last_exc = exc
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "LLM API transient error (attempt %d/%d): %s. Retrying in %.1fs...",
                attempt,
                _MAX_RETRIES,
                exc,
                delay,
            )
            time.sleep(delay)
        except AuthenticationError as exc:
            logger.error("LLM AuthenticationError: %s. Check QWEN_API_KEY.", exc)
            raise
        except APIError as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "LLM API error (attempt %d/%d): %s. Retrying in %.1fs...",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.error("LLM API error after %d attempts: %s", _MAX_RETRIES, exc)
    raise last_exc


def get_llm(temperature: float = 0.7, model: str = "qwen-max"):
    """
    Initializes the Qwen Cloud API client using the OpenAI compatible endpoint.
    Requires QWEN_API_KEY environment variable — never hardcode the key here.
    """
    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "QWEN_API_KEY is not set. Add it to your .env file or export it as an "
            "environment variable. Never paste the key directly into source code."
        )
    base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    try:
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_retries=0,
        )
    except Exception as exc:
        logger.error("Failed to initialize ChatOpenAI (model=%s): %s", model, exc, exc_info=True)
        raise


class _RetryStructuredLLM:
    """Wrapper around a structured LLM that adds retry logic to invoke/ainvoke."""

    def __init__(self, structured_llm):
        self._llm = structured_llm

    def invoke(self, messages, **kwargs):
        return _retry_on_api_error(self._llm.invoke, messages, **kwargs)

    async def ainvoke(self, messages, **kwargs):
        return await _retry_on_api_error_async(self._llm.ainvoke, messages, **kwargs)

    def __getattr__(self, name):
        return getattr(self._llm, name)


async def _retry_on_api_error_async(func, *args, **kwargs):
    """Async version of retry wrapper."""
    last_exc = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return await func(*args, **kwargs)
        except (APIConnectionError, RateLimitError) as exc:
            last_exc = exc
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "LLM API transient error (attempt %d/%d): %s. Retrying in %.1fs...",
                attempt,
                _MAX_RETRIES,
                exc,
                delay,
            )
            import asyncio

            await asyncio.sleep(delay)
        except AuthenticationError as exc:
            logger.error("LLM AuthenticationError: %s. Check QWEN_API_KEY.", exc)
            raise
        except APIError as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "LLM API error (attempt %d/%d): %s. Retrying in %.1fs...",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    delay,
                )
                import asyncio

                await asyncio.sleep(delay)
            else:
                logger.error("LLM API error after %d attempts: %s", _MAX_RETRIES, exc)
    raise last_exc


def get_structured_llm(schema, temperature: float = 0.1, model: str = "qwen-max"):
    """Returns an LLM bound to a specific JSON schema for routing decisions."""
    llm = get_llm(temperature=temperature, model=model)
    try:
        structured = llm.with_structured_output(schema)
    except Exception as exc:
        logger.error(
            "Failed to bind structured output (schema=%s, model=%s): %s",
            schema.__name__ if hasattr(schema, "__name__") else str(schema),
            model,
            exc,
            exc_info=True,
        )
        raise
    return _RetryStructuredLLM(structured)
