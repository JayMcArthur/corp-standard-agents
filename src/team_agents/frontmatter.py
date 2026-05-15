from __future__ import annotations

from pathlib import Path
from typing import Any

from team_agents.errors import ValidationError


def parse_frontmatter_document(text: str, path: Path) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise ValidationError(f"Missing frontmatter in {path}")
    end_marker = "\n---\n"
    end_index = text.find(end_marker, 4)
    if end_index == -1:
        raise ValidationError(f"Unterminated frontmatter in {path}")
    raw_metadata = text[4:end_index]
    body = text[end_index + len(end_marker) :]
    metadata: dict[str, Any] = {}
    lines = raw_metadata.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if ":" not in line:
            raise ValidationError(f"Malformed frontmatter line in {path}: {line}")
        key, raw_value = line.split(":", 1)
        value = raw_value.strip()
        if value:
            if value in {">", "|"}:
                block_lines = []
                index += 1
                while index < len(lines):
                    nested = lines[index]
                    if not nested.strip():
                        block_lines.append("")
                        index += 1
                        continue
                    if not nested.startswith((" ", "\t")):
                        break
                    block_lines.append(nested.strip())
                    index += 1
                metadata[key.strip()] = parse_frontmatter_text_block(block_lines, style=value)
                continue
            metadata[key.strip()] = parse_frontmatter_value(value, path)
            index += 1
            continue
        block_lines: list[str] = []
        index += 1
        while index < len(lines):
            nested = lines[index]
            if not nested.strip():
                index += 1
                continue
            if not nested.startswith((" ", "\t")):
                break
            block_lines.append(nested.strip())
            index += 1
        metadata[key.strip()] = parse_frontmatter_block(block_lines, path)
    return metadata, body


def parse_frontmatter_value(value: str, path: Path) -> Any:
    if not value:
        return ""
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_frontmatter_scalar(part.strip(), path) for part in split_list_items(inner)]
    return parse_frontmatter_scalar(value, path)


def parse_frontmatter_scalar(value: str, path: Path) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    if value.startswith(('"', "'")) or value.endswith(('"', "'")):
        raise ValidationError(f"Malformed quoted frontmatter value in {path}: {value}")
    return value


def parse_frontmatter_block(lines: list[str], path: Path) -> Any:
    if not lines:
        return ""
    if all(line.startswith("- ") for line in lines):
        return [parse_frontmatter_scalar(line[2:].strip(), path) for line in lines]
    if all(":" in line and not line.startswith("- ") for line in lines):
        mapping: dict[str, Any] = {}
        for line in lines:
            key, raw_value = line.split(":", 1)
            value = raw_value.strip()
            mapping[key.strip()] = parse_frontmatter_value(value, path)
        return mapping
    raise ValidationError(f"Unsupported multiline frontmatter block in {path}: {lines[0]}")


def parse_frontmatter_text_block(lines: list[str], *, style: str) -> str:
    if style == ">":
        return " ".join(part for part in lines if part).strip()
    return "\n".join(lines).strip()


def split_list_items(raw: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in raw:
        if quote is not None:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            current.append(char)
            continue
        if char == ",":
            items.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        items.append("".join(current).strip())
    return items


def dump_frontmatter_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(dump_frontmatter_value(item) for item in value) + "]"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
