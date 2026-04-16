"""Document chunking for large markdown files."""

from __future__ import annotations

import re
from dataclasses import dataclass

from doc_bridge.utils.token_counter import TOKEN_LIMIT, estimate_tokens


@dataclass
class Chunk:
    text: str
    start_paragraph: int
    end_paragraph: int
    heading: str


def count_paragraphs(text: str) -> int:
    """Count non-empty paragraphs (double-newline separated blocks)."""
    paragraphs = re.split(r"\n{2,}", text.strip())
    return len([p for p in paragraphs if p.strip()])


def split_into_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs, preserving content."""
    paragraphs = re.split(r"\n{2,}", text.strip())
    return [p for p in paragraphs if p.strip()]


def chunk_by_headings(text: str) -> list[Chunk]:
    """Split markdown by top-level headings (# or ##).

    Used when the full document exceeds TOKEN_LIMIT.
    """
    lines = text.split("\n")
    chunks: list[Chunk] = []
    current_lines: list[str] = []
    current_heading = "(文档开头)"
    para_counter = 0
    chunk_start_para = 1

    for line in lines:
        if re.match(r"^#{1,2}\s+", line) and current_lines:
            chunk_text = "\n".join(current_lines)
            paras_in_chunk = len(split_into_paragraphs(chunk_text))
            chunks.append(Chunk(
                text=chunk_text,
                start_paragraph=chunk_start_para,
                end_paragraph=chunk_start_para + paras_in_chunk - 1,
                heading=current_heading,
            ))
            chunk_start_para += paras_in_chunk
            current_lines = [line]
            current_heading = line.strip("# ").strip()
        else:
            current_lines.append(line)

    # Last chunk
    if current_lines:
        chunk_text = "\n".join(current_lines)
        paras_in_chunk = len(split_into_paragraphs(chunk_text))
        chunks.append(Chunk(
            text=chunk_text,
            start_paragraph=chunk_start_para,
            end_paragraph=chunk_start_para + paras_in_chunk - 1,
            heading=current_heading,
        ))

    return chunks


def needs_chunking(text: str) -> bool:
    """Check if the document exceeds the token limit."""
    return estimate_tokens(text) > TOKEN_LIMIT


def prepare_chunks(text: str) -> list[Chunk]:
    """Return a list of chunks for processing.

    If the document fits in one chunk, returns a single chunk.
    Otherwise splits by headings.
    """
    if not needs_chunking(text):
        total_paras = count_paragraphs(text)
        return [Chunk(
            text=text,
            start_paragraph=1,
            end_paragraph=total_paras,
            heading="(完整文档)",
        )]

    chunks = chunk_by_headings(text)

    # If a single heading-chunk is still too large, split further by paragraph count
    final_chunks: list[Chunk] = []
    for chunk in chunks:
        if estimate_tokens(chunk.text) > TOKEN_LIMIT:
            paragraphs = split_into_paragraphs(chunk.text)
            sub_text: list[str] = []
            sub_start = chunk.start_paragraph
            for i, para in enumerate(paragraphs):
                sub_text.append(para)
                if estimate_tokens("\n\n".join(sub_text)) > TOKEN_LIMIT * 0.9:
                    # Flush current sub-chunk (without the last paragraph)
                    if len(sub_text) > 1:
                        sub_text.pop()
                        final_chunks.append(Chunk(
                            text="\n\n".join(sub_text),
                            start_paragraph=sub_start,
                            end_paragraph=sub_start + len(sub_text) - 1,
                            heading=chunk.heading,
                        ))
                        sub_start += len(sub_text)
                        sub_text = [para]
                    else:
                        # Single paragraph exceeds limit — keep it anyway
                        final_chunks.append(Chunk(
                            text=para,
                            start_paragraph=sub_start,
                            end_paragraph=sub_start,
                            heading=chunk.heading,
                        ))
                        sub_start += 1
                        sub_text = []

            if sub_text:
                final_chunks.append(Chunk(
                    text="\n\n".join(sub_text),
                    start_paragraph=sub_start,
                    end_paragraph=sub_start + len(sub_text) - 1,
                    heading=chunk.heading,
                ))
        else:
            final_chunks.append(chunk)

    return final_chunks
