"""Audience Conversion raw-data collector.

This module consolidates existing client research artifacts into the
source-preserved raw dump used by docs/audience-conversion-report.md. It is a
free/local collection layer: it reads files already present in clients/<slug>/.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

CLIENTS_DIR = Path("clients")


@dataclass(frozen=True)
class AudienceRecord:
    """A single source-preserved audience/VOC record."""

    source_type: str
    source_label: str
    text: str
    source_url: str = ""
    product: str = ""
    competitor: str = ""
    automation_method: str = "repo"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self, record_id: int, generated_at: str) -> dict[str, Any]:
        return {
            "id": f"acr-{record_id:05d}",
            "collected_at": generated_at,
            "source_type": self.source_type,
            "source_label": self.source_label,
            "source_url": self.source_url,
            "product": self.product,
            "competitor": self.competitor,
            "automation_method": self.automation_method,
            "text": self.text,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class CollectionResult:
    out_dir: Path
    raw_md_path: Path
    raw_jsonl_path: Path
    manifest_path: Path
    research_document_path: Path
    source_truth_path: Path
    record_count: int
    source_counts: dict[str, int]
    empty_lanes: list[dict[str, Any]]


def collect_audience_conversion_raw(
    client_slug: str,
    *,
    product: str | None = None,
    category: str | None = None,
    include_exa: bool = True,
    manual_sources: list[Path] | None = None,
    clients_dir: Path = CLIENTS_DIR,
) -> CollectionResult:
    """Collect existing research artifacts into Audience Conversion raw files."""

    client_dir = clients_dir / client_slug
    if not client_dir.exists():
        raise FileNotFoundError(f"Client not found: {client_dir}")

    generated_at = datetime.now(timezone.utc).isoformat()
    out_dir = client_dir / "research" / "audience-conversion"
    out_dir.mkdir(parents=True, exist_ok=True)

    empty_lanes: list[dict[str, Any]] = []
    records: list[AudienceRecord] = []

    records.extend(_collect_product_context(client_dir, product=product))
    records.extend(_collect_brand_yaml(client_dir, empty_lanes))
    records.extend(_collect_persona_context(client_dir, empty_lanes))
    records.extend(_collect_voc_files(client_dir, empty_lanes))
    records.extend(_collect_competitor_reviews(client_dir, empty_lanes))
    records.extend(_collect_amazon_reviews(client_dir, empty_lanes))
    records.extend(_collect_social_comments(client_dir, empty_lanes))
    if include_exa:
        records.extend(_collect_exa_results(client_dir, empty_lanes))
    if manual_sources:
        records.extend(_collect_manual_sources(manual_sources))

    raw_md_path = out_dir / "raw-data.md"
    raw_jsonl_path = out_dir / "raw-data.jsonl"
    manifest_path = out_dir / "source-manifest.yaml"
    research_document_path = out_dir / "research-document.md"
    source_truth_path = out_dir / "source-truth-check.md"

    _write_jsonl(raw_jsonl_path, records, generated_at)
    _write_raw_markdown(
        raw_md_path,
        client_slug=client_slug,
        product=product,
        category=category,
        records=records,
        generated_at=generated_at,
    )
    source_counts = dict(Counter(r.source_type for r in records))
    _write_manifest(
        manifest_path,
        client_slug=client_slug,
        product=product,
        category=category,
        records=records,
        source_counts=source_counts,
        empty_lanes=empty_lanes,
        generated_at=generated_at,
    )
    _write_research_document_stub(research_document_path, client_slug, product, category)
    _write_source_truth_stub(source_truth_path, client_slug, product, category)

    return CollectionResult(
        out_dir=out_dir,
        raw_md_path=raw_md_path,
        raw_jsonl_path=raw_jsonl_path,
        manifest_path=manifest_path,
        research_document_path=research_document_path,
        source_truth_path=source_truth_path,
        record_count=len(records),
        source_counts=source_counts,
        empty_lanes=empty_lanes,
    )


def _collect_product_context(client_dir: Path, *, product: str | None) -> list[AudienceRecord]:
    records: list[AudienceRecord] = []
    brand_context = client_dir / "brand-context.md"
    if brand_context.exists():
        text = _read_text(brand_context).strip()
        if text:
            records.append(
                AudienceRecord(
                    source_type="brand_context",
                    source_label=str(brand_context.relative_to(client_dir)),
                    text=text,
                    automation_method="repo",
                )
            )

    products_dir = client_dir / "products"
    if not products_dir.exists():
        return records

    for path in sorted(products_dir.glob("*.yaml")):
        if product and path.stem != product:
            continue
        payload = _read_yaml(path)
        if not isinstance(payload, dict):
            continue
        text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).strip()
        if text:
            records.append(
                AudienceRecord(
                    source_type="product_context",
                    source_label=str(path.relative_to(client_dir)),
                    text=text,
                    product=path.stem,
                    automation_method="repo",
                )
            )
    return records


def _collect_brand_yaml(
    client_dir: Path, empty_lanes: list[dict[str, Any]]
) -> list[AudienceRecord]:
    path = client_dir / "brand.yaml"
    if not path.exists():
        empty_lanes.append({"lane": "brand_information", "reason": "brand.yaml does not exist"})
        return []

    payload = _read_yaml(path)
    if not isinstance(payload, dict) or not payload:
        empty_lanes.append({"lane": "brand_information", "file": str(path), "reason": "empty brand.yaml"})
        return []

    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).strip()
    if not text:
        empty_lanes.append({"lane": "brand_information", "file": str(path), "reason": "0 usable fields"})
        return []

    return [
        AudienceRecord(
            source_type="brand_information",
            source_label=str(path.relative_to(client_dir)),
            text=text,
            automation_method="repo",
        )
    ]


def _collect_persona_context(
    client_dir: Path, empty_lanes: list[dict[str, Any]]
) -> list[AudienceRecord]:
    persona_paths: list[Path] = []
    avatar_file = client_dir / "avatar.yaml"
    if avatar_file.exists():
        persona_paths.append(avatar_file)
    avatars_dir = client_dir / "avatars"
    if avatars_dir.exists():
        persona_paths.extend(
            path for path in sorted(avatars_dir.glob("*.yaml")) if path.name != "_index.yaml"
        )

    if not persona_paths:
        empty_lanes.append(
            {
                "lane": "existing_personas",
                "reason": "no avatar.yaml or avatars/*.yaml found",
            }
        )
        return []

    records: list[AudienceRecord] = []
    for path in persona_paths:
        payload = _read_yaml(path)
        if not isinstance(payload, dict) or not payload:
            empty_lanes.append({"lane": "existing_personas", "file": str(path), "reason": "empty persona"})
            continue
        text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).strip()
        if not text:
            empty_lanes.append({"lane": "existing_personas", "file": str(path), "reason": "0 usable fields"})
            continue
        records.append(
            AudienceRecord(
                source_type="existing_persona",
                source_label=str(path.relative_to(client_dir)),
                text=text,
                automation_method="repo",
            )
        )
    return records


def _collect_voc_files(client_dir: Path, empty_lanes: list[dict[str, Any]]) -> list[AudienceRecord]:
    voc_dir = client_dir / "voc"
    if not voc_dir.exists():
        empty_lanes.append({"lane": "own_voc", "reason": "clients/<slug>/voc does not exist"})
        return []

    records: list[AudienceRecord] = []
    for path in sorted(voc_dir.glob("*.json")):
        data = _read_json(path)
        before = len(records)
        for item in _iter_items(data):
            text = _text_from_item(item)
            if not text:
                continue
            source = _string(item.get("source")) or path.stem
            source_type = _voc_source_type(path.stem, source)
            records.append(
                AudienceRecord(
                    source_type=source_type,
                    source_label=str(path.relative_to(client_dir)),
                    text=text,
                    product=_string(item.get("product")),
                    source_url=_string(item.get("url") or item.get("post_url")),
                    automation_method="repo",
                    metadata=_compact_metadata(item, exclude={"text", "body", "content", "review"}),
                )
            )
        if len(records) == before:
            empty_lanes.append({"lane": "own_voc", "file": str(path), "reason": "0 usable records"})
    return records


def _collect_competitor_reviews(
    client_dir: Path, empty_lanes: list[dict[str, Any]]
) -> list[AudienceRecord]:
    reviews_dir = client_dir / "research" / "competitor-reviews"
    if not reviews_dir.exists():
        empty_lanes.append(
            {"lane": "competitor_reviews", "reason": "research/competitor-reviews does not exist"}
        )
        return []

    records: list[AudienceRecord] = []
    for path in sorted(reviews_dir.glob("*.json")):
        data = _read_json(path)
        competitor = data.get("competitor") or {}
        competitor_name = _string(competitor.get("name")) or path.stem
        reviews = data.get("reviews") or []
        if not reviews:
            empty_lanes.append(
                {
                    "lane": "competitor_reviews",
                    "file": str(path),
                    "competitor": competitor_name,
                    "reason": data.get("notes") or "0 reviews",
                    "vendor": data.get("vendor"),
                }
            )
            continue
        for review in reviews:
            if not isinstance(review, dict):
                continue
            text = _text_from_item(review)
            if not text:
                continue
            records.append(
                AudienceRecord(
                    source_type="competitor_review",
                    source_label=str(path.relative_to(client_dir)),
                    text=text,
                    competitor=competitor_name,
                    source_url=_string(review.get("url") or review.get("source_url")),
                    automation_method="repo",
                    metadata=_compact_metadata(review, exclude={"text", "body", "content", "review"}),
                )
            )
    return records


def _collect_amazon_reviews(
    client_dir: Path, empty_lanes: list[dict[str, Any]]
) -> list[AudienceRecord]:
    reviews_dir = client_dir / "research" / "amazon-reviews"
    if not reviews_dir.exists():
        empty_lanes.append({"lane": "amazon_reviews", "reason": "research/amazon-reviews does not exist"})
        return []

    records: list[AudienceRecord] = []
    for path in sorted(reviews_dir.glob("*.json")):
        data = _read_json(path)
        reviews = data.get("reviews") if isinstance(data, dict) else data
        before = len(records)
        for review in _iter_items(reviews):
            text = _text_from_item(review)
            if not text:
                continue
            records.append(
                AudienceRecord(
                    source_type="amazon_review",
                    source_label=str(path.relative_to(client_dir)),
                    text=text,
                    product=_string(review.get("product") or review.get("asin")),
                    source_url=_string(review.get("url") or review.get("review_url")),
                    automation_method="repo",
                    metadata=_compact_metadata(review, exclude={"text", "body", "content", "review"}),
                )
            )
        if len(records) == before:
            empty_lanes.append({"lane": "amazon_reviews", "file": str(path), "reason": "0 usable reviews"})
    return records


def _collect_social_comments(
    client_dir: Path, empty_lanes: list[dict[str, Any]]
) -> list[AudienceRecord]:
    research_dir = client_dir / "research"
    if not research_dir.exists():
        return []

    records: list[AudienceRecord] = []
    comment_dirs = sorted(research_dir.glob("*-comments"))
    if not comment_dirs:
        empty_lanes.append({"lane": "social_comments", "reason": "no research/*-comments dirs"})
        return []

    for comment_dir in comment_dirs:
        platform = comment_dir.name.removesuffix("-comments")
        for path in sorted(comment_dir.glob("*.json")):
            data = _read_json(path)
            comments = data.get("comments") if isinstance(data, dict) else data
            before = len(records)
            for comment in _iter_items(comments):
                text = _text_from_item(comment)
                if not text:
                    continue
                records.append(
                    AudienceRecord(
                        source_type=f"{platform}_comment",
                        source_label=str(path.relative_to(client_dir)),
                        text=text,
                        competitor=_string(data.get("competitor_name")) if isinstance(data, dict) else "",
                        source_url=_string(comment.get("post_url") or data.get("post_url"))
                        if isinstance(data, dict)
                        else _string(comment.get("post_url")),
                        automation_method="repo",
                        metadata=_compact_metadata(comment, exclude={"text", "body", "content", "review"}),
                    )
                )
            if len(records) == before:
                empty_lanes.append(
                    {"lane": f"{platform}_comments", "file": str(path), "reason": "0 usable comments"}
                )
    return records


def _collect_exa_results(client_dir: Path, empty_lanes: list[dict[str, Any]]) -> list[AudienceRecord]:
    raw_dir = client_dir / "research" / "exa" / "raw"
    if not raw_dir.exists():
        empty_lanes.append({"lane": "exa", "reason": "research/exa/raw does not exist"})
        return []

    records: list[AudienceRecord] = []
    for path in sorted(raw_dir.glob("*.json")):
        data = _read_json(path)
        query = data.get("query") if isinstance(data, dict) else {}
        results = data.get("results") if isinstance(data, dict) else []
        source_type = "exa_result"
        category = _string(query.get("category")) if isinstance(query, dict) else ""
        if category:
            source_type = f"exa_{category}"
        before = len(records)
        for result in _iter_items(results):
            text = _exa_text(result)
            if not text:
                continue
            records.append(
                AudienceRecord(
                    source_type=source_type,
                    source_label=str(path.relative_to(client_dir)),
                    text=text,
                    source_url=_string(result.get("url")),
                    automation_method="exa",
                    metadata={
                        "title": result.get("title"),
                        "query_label": query.get("label") if isinstance(query, dict) else "",
                    },
                )
            )
        if len(records) == before:
            empty_lanes.append({"lane": "exa", "file": str(path), "reason": "0 usable results"})
    return records


def _collect_manual_sources(paths: list[Path]) -> list[AudienceRecord]:
    records: list[AudienceRecord] = []
    for path in paths:
        text = _read_text(path).strip()
        if text:
            records.append(
                AudienceRecord(
                    source_type="manual_source",
                    source_label=str(path),
                    text=text,
                    automation_method="manual",
                )
            )
    return records


def _write_jsonl(path: Path, records: list[AudienceRecord], generated_at: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for i, record in enumerate(records, 1):
            fh.write(json.dumps(record.to_json(i, generated_at), ensure_ascii=False) + "\n")


def _write_raw_markdown(
    path: Path,
    *,
    client_slug: str,
    product: str | None,
    category: str | None,
    records: list[AudienceRecord],
    generated_at: str,
) -> None:
    grouped: dict[str, list[AudienceRecord]] = defaultdict(list)
    for record in records:
        grouped[record.source_type].append(record)

    lines = [
        f"# Audience Conversion Raw Data - {client_slug}",
        "",
        f"- Generated: {generated_at}",
        f"- Product: {product or 'not specified'}",
        f"- Category: {category or 'not specified'}",
        f"- Records: {len(records)}",
        "",
        "Raw records are preserved for source-truthed synthesis. Do not edit customer",
        "phrasing here unless correcting a scrape artifact.",
        "",
    ]
    for source_type in sorted(grouped):
        lines.append(f"## {source_type.replace('_', ' ').title()}")
        lines.append("")
        for i, record in enumerate(grouped[source_type], 1):
            lines.append(f"### {i}. {record.source_label}")
            if record.source_url:
                lines.append(f"- URL: {record.source_url}")
            if record.product:
                lines.append(f"- Product: {record.product}")
            if record.competitor:
                lines.append(f"- Competitor: {record.competitor}")
            lines.append("")
            lines.append(_markdown_quote(record.text))
            lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_manifest(
    path: Path,
    *,
    client_slug: str,
    product: str | None,
    category: str | None,
    records: list[AudienceRecord],
    source_counts: dict[str, int],
    empty_lanes: list[dict[str, Any]],
    generated_at: str,
) -> None:
    manifest = {
        "client": client_slug,
        "product": product or "",
        "category": category or "",
        "generated_at": generated_at,
        "automation_method": "repo_cli_collect",
        "record_count": len(records),
        "source_counts": source_counts,
        "empty_or_blocked_lanes": empty_lanes,
        "output_files": {
            "raw_data_md": "raw-data.md",
            "raw_data_jsonl": "raw-data.jsonl",
            "research_document": "research-document.md",
            "source_truth_check": "source-truth-check.md",
        },
    }
    path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_research_document_stub(
    path: Path, client_slug: str, product: str | None, category: str | None
) -> None:
    if path.exists():
        return
    text = f"""# Audience Conversion Report - {client_slug}

- Product: {product or "not specified"}
- Category: {category or "not specified"}
- Status: not synthesized

Use `raw-data.md` and `raw-data.jsonl` with the prompt in
`docs/audience-conversion-report.md` to synthesize this report.

Required sections:

- Brand information.
- Categorized insights.
- Top pain points.
- Failed solutions.
- Desired outcomes.
- Objections.
- Misconceptions.
- Behaviors and moments.
- Exact customer terminology.
- Golden nuggets.
- Strategy implications.
- Objection-to-ad mapping.
- Product-USP angle mapping.
- ICP language analysis.
- Key personas.
- Concepts.

## Brand Information

- Brand Name:
- Unique Differentiator:
- Best-Selling Product/Service:
- Three Things Prospects Should Know:
- Desired Brand Perception:
- Seasonal Patterns:
- FAQs And Common Claims:
- Claims To Avoid Or Verify:

## Key Personas

Generate exactly three source-supported personas after synthesis, or paste in
three reviewed personas if they already exist in the client files.

## Concepts

Concept section intentionally left open for next-phase concept brainstorming.
"""
    path.write_text(text, encoding="utf-8")


def _write_source_truth_stub(
    path: Path, client_slug: str, product: str | None, category: str | None
) -> None:
    if path.exists():
        return
    text = f"""# Source Truth Check - {client_slug}

- Product: {product or "not specified"}
- Category: {category or "not specified"}
- Status: not audited

Audit the finished research document against `raw-data.md` and
`raw-data.jsonl`.

Track:

- Unsupported claims removed.
- Strongest raw quotes.
- Insights with direct source support.
- Insights that need more data.
- Claims that need client approval or proof.
"""
    path.write_text(text, encoding="utf-8")


def _iter_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("reviews", "comments", "items", "results", "data"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def _text_from_item(item: dict[str, Any]) -> str:
    parts = []
    for key in ("title", "headline", "text", "body", "content", "review", "comment"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return "\n".join(dict.fromkeys(parts)).strip()


def _exa_text(item: dict[str, Any]) -> str:
    parts = []
    for key in ("title", "text", "summary", "snippet", "highlights"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
        elif isinstance(value, list):
            parts.extend(str(v).strip() for v in value if str(v).strip())
    return "\n".join(dict.fromkeys(parts)).strip()


def _voc_source_type(stem: str, source: str) -> str:
    label = f"{stem} {source}".lower()
    if "tiktok" in label:
        return "tiktok_comment"
    if "youtube" in label:
        return "youtube_comment"
    if "instagram" in label:
        return "instagram_comment"
    return "own_review"


def _compact_metadata(item: dict[str, Any], *, exclude: set[str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key, value in item.items():
        if key in exclude:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            metadata[key] = value
    return metadata


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _markdown_quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())
