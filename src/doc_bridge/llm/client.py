"""Async LLM client wrapping the Anthropic SDK."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from anthropic import AsyncAnthropic

from doc_bridge.llm.logger import LLMCallLogger
from doc_bridge.models.config import LLMConfig


class LLMClient:
    def __init__(
        self,
        config: LLMConfig,
        logger: LLMCallLogger,
        semaphore: asyncio.Semaphore,
    ):
        self._client = AsyncAnthropic(
            base_url=config.base_url,
            api_key=config.api_key,
        )
        self._model = config.model
        self._logger = logger
        self._semaphore = semaphore

    async def extract(
        self,
        system_prompt: str,
        user_content: str,
        *,
        step: str = "",
        source_file: str = "",
        system_name: str = "",
        prompt_file: str = "",
        prompt_version: str = "v1.0",
        max_retries: int = 3,
    ) -> str:
        """Send a message to the LLM and return the text response.

        Retries on failure with exponential backoff.
        """
        call_id = f"call_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        last_error: Exception | None = None

        for attempt in range(max_retries):
            async with self._semaphore:
                start = time.monotonic()
                try:
                    response = await self._client.messages.create(
                        model=self._model,
                        max_tokens=8192,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_content}],
                    )
                    duration_ms = int((time.monotonic() - start) * 1000)
                    text = response.content[0].text

                    self._logger.log_call(
                        call_id=call_id,
                        step=step,
                        source_file=source_file,
                        system=system_name,
                        prompt_file=prompt_file,
                        prompt_version=prompt_version,
                        model=self._model,
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        duration_ms=duration_ms,
                        retry_count=attempt,
                        request_system=system_prompt[:500],
                        request_user=user_content[:500],
                        response_raw=text[:2000],
                        validation_result="pending",
                    )
                    return text

                except Exception as e:
                    duration_ms = int((time.monotonic() - start) * 1000)
                    last_error = e
                    self._logger.log_call(
                        call_id=call_id,
                        step=step,
                        source_file=source_file,
                        system=system_name,
                        prompt_file=prompt_file,
                        prompt_version=prompt_version,
                        model=self._model,
                        input_tokens=0,
                        output_tokens=0,
                        duration_ms=duration_ms,
                        retry_count=attempt,
                        request_system=system_prompt[:500],
                        request_user=user_content[:500],
                        response_raw=f"ERROR: {e}",
                        validation_result="error",
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** (attempt + 1))

        raise RuntimeError(
            f"LLM 调用在 {max_retries} 次重试后仍然失败: {last_error}"
        )
