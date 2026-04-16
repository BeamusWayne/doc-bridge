"""Atom data models — structured representations of extracted items."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .provenance import ContextQuote, Provenance

VALID_DOMAINS = [
    "客运", "货运", "机务", "车辆", "工务", "电务",
    "供电", "安监", "计统", "财务", "人事", "建设",
    "物资", "运输", "企法", "科信", "待确认",
]


class GlossaryItem(BaseModel):
    type: Literal["glossary"] = "glossary"
    name: str = Field(min_length=2, max_length=50, description="术语名称")
    domain: str = Field(description="专业域")
    aliases: list[str] = Field(default_factory=list, description="别名列表")
    definition: str = Field(min_length=1, description="定义")
    context_quotes: list[ContextQuote] = Field(min_length=1, description="原文引用")
    paragraphs: list[int] = Field(min_length=1)
    provenance: Optional[Provenance] = None

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        if v not in VALID_DOMAINS:
            raise ValueError(
                f"专业域 '{v}' 不在允许范围内。"
                f"允许值: {', '.join(VALID_DOMAINS)}"
            )
        return v

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, v: list[str], info) -> list[str]:
        name = info.data.get("name", "")
        return [a for a in v if a != name]


class EntityItem(BaseModel):
    type: Literal["entity"] = "entity"
    name: str = Field(min_length=2, max_length=50, description="实体名称")
    description: str = Field(min_length=1, description="描述")
    responsibilities: list[str] = Field(default_factory=list, description="职责列表")
    context_quotes: list[ContextQuote] = Field(min_length=1, description="原文引用")
    paragraphs: list[int] = Field(min_length=1)
    provenance: Optional[Provenance] = None


class DataFlowItem(BaseModel):
    type: Literal["data-flow"] = "data-flow"
    name: str = Field(min_length=2, max_length=100, description="数据流名称")
    source_entity: str = Field(min_length=1, description="源实体")
    target_entity: str = Field(min_length=1, description="目标实体")
    intermediate_entities: list[str] = Field(
        default_factory=list, description="中间实体"
    )
    data_content: str = Field(min_length=1, description="传输的数据内容")
    description: str = Field(default="", description="描述")
    context_quotes: list[ContextQuote] = Field(min_length=1, description="原文引用")
    paragraphs: list[int] = Field(min_length=1)
    provenance: Optional[Provenance] = None


class LLMExtractionResult(BaseModel):
    """LLM returns this structure."""

    glossary: list[GlossaryItem] = Field(default_factory=list)
    entities: list[EntityItem] = Field(default_factory=list)
    data_flows: list[DataFlowItem] = Field(default_factory=list)
