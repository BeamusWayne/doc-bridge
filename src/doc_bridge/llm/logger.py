"""LLM call logging — one JSONL entry per API call."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any


class LLMCallLogger:
    def __init__(self, log_dir: Path):
        self._log_dir = log_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._jsonl_path = log_dir / "llm_calls.jsonl"
        self._fh = open(self._jsonl_path, "a", encoding="utf-8")

    def log_call(
        self,
        call_id: str,
        step: str,
        source_file: str,
        system: str,
        prompt_file: str,
        prompt_version: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
        retry_count: int,
        request_system: str,
        request_user: str,
        response_raw: str,
        validation_result: str,
        items_extracted: int = 0,
        items_filtered: int = 0,
        filter_reasons: list[dict[str, str]] | None = None,
    ) -> None:
        record = {
            "call_id": call_id,
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "source_file": source_file,
            "system": system,
            "prompt_file": prompt_file,
            "prompt_version": prompt_version,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_ms": duration_ms,
            "retry_count": retry_count,
            "request_system": request_system,
            "request_user": request_user,
            "response_raw": response_raw,
            "validation_result": validation_result,
            "items_extracted": items_extracted,
            "items_filtered": items_filtered,
            "filter_reasons": filter_reasons or [],
        }
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def setup_flow_logger(log_dir: Path, name: str) -> logging.Logger:
    """Set up a standard Python logger writing to log_dir/<name>.log."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"doc_bridge.{name}")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fh = logging.FileHandler(log_dir / f"{name}.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s]  %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger
