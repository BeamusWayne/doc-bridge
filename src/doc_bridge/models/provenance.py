"""Provenance tracking data models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ContextQuote(BaseModel):
    paragraph: int = Field(ge=1, description="段落编号")
    quote: str = Field(min_length=1, description="原文引用")


class Provenance(BaseModel):
    original_file: str = Field(description="原始文档路径 (相对于workspace)")
    markdown_file: str = Field(description="Markdown文件路径 (相对于workspace)")
    paragraphs: list[int] = Field(min_length=1, description="出现的段落编号列表")
    extraction_prompt: str = Field(description="使用的提示词文件路径")
    extracted_at: datetime = Field(default_factory=datetime.now)
    prompt_version: str = Field(default="v1.0")
    llm_model: str = Field(default="")
    llm_call_id: str = Field(default="")
    synthesis_backlinks: list[str] = Field(
        default_factory=list,
        description="关联的总表文件路径列表 (合成阶段自动填入)",
    )
