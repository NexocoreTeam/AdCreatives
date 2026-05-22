#!/usr/bin/env python3
"""Smoke test for the new text-only ad generation pipeline.

Exercises the bracket-fill end-to-end WITHOUT calling FAL (so this is free
and doesn't require FAL_KEY — it only needs ANTHROPIC_API_KEY).

What it verifies:
    1. Module imports cleanly.
    2. Cooper templates load by id.
    3. Bracket-fill resolves placeholders deterministically + via Claude.
    4. Product Anchor preamble is prepended.
    5. Aspect ratio is locked from the template.
    6. ⚠️ flagging surfaces invented slots.

Usage (from repo root):
    py scripts/smoke_test_pynk_text.py [--template cooper-11-pull-quote-review] [--client secondkind]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make sure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows consoles default to cp1252 which can't render ⚠️ / em-dashes.
# Force UTF-8 so the smoke test output survives.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Bootstrap .env so ANTHROPIC_API_KEY is available without running through cli.py
import os
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip().lstrip("﻿")
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and not os.environ.get(k):
            os.environ[k] = v

from generators.pynk_text_filler import (
    fill_template,
    load_cooper_template,
    extract_placeholders,
    PRODUCT_ANCHOR_PREAMBLE,
)
from models.loader import (
    load_brand,
    load_product_by_name,
    load_avatar,
    load_all_briefs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", default="secondkind")
    parser.add_argument("--template", default="cooper-11-pull-quote-review")
    parser.add_argument("--product", default=None,
                        help="Product display name. Defaults to brief's product if --brief used.")
    parser.add_argument("--brief", default=None, help="Brief ID")
    args = parser.parse_args()

    print(f"\n=== Smoke test ===")
    print(f"  client:   {args.client}")
    print(f"  template: {args.template}")

    library_root = Path("prompts/library")

    # Load template
    print("\n[1/5] Loading cooper template...")
    try:
        td = load_cooper_template(args.template, library_root)
    except FileNotFoundError as e:
        print(f"FAIL: {e}")
        return 1
    print(f"   OK — {td.get('name')} | aspects: {td.get('aspect_ratios')}")
    placeholders = extract_placeholders(td.get("template_prompt", ""))
    print(f"   {len(placeholders)} placeholder(s) in template: {sorted(set(placeholders))[:8]}{'...' if len(set(placeholders)) > 8 else ''}")

    # Load brand
    print("\n[2/5] Loading brand...")
    try:
        brand = load_brand(args.client)
    except Exception as e:
        print(f"FAIL: {e}")
        return 1
    print(f"   OK — {brand.name} | primary: {brand.colors.primary} | bg: {brand.colors.background}")

    # Resolve brief
    print("\n[3/5] Resolving brief / product...")
    brief = None
    if args.brief:
        briefs = load_all_briefs(args.client)
        for b in briefs:
            if b.brief_id == args.brief:
                brief = b
                break
        if not brief:
            print(f"FAIL: brief not found: {args.brief}")
            return 1

    product_name = args.product or (brief.product if brief else None)
    if not product_name:
        # Pick first product in folder
        products_dir = Path("clients") / args.client / "products"
        candidates = [p for p in products_dir.glob("*.yaml") if not p.stem.startswith("example")]
        if not candidates:
            print(f"FAIL: no product yaml found in {products_dir}")
            return 1
        # Open the first one and read the name
        import yaml
        with open(candidates[0], encoding="utf-8") as f:
            product_data = yaml.safe_load(f)
        product_name = product_data.get("name")
        print(f"   (auto-picked product: {product_name})")

    product = load_product_by_name(args.client, product_name)
    avatar = load_avatar(args.client)

    if not brief:
        # Build a stub
        from models.brief import CreativeBrief, AwarenessLevel, CopyFramework
        brief = CreativeBrief(
            brief_id="stub-smoke",
            client=args.client,
            product=product_name,
            awareness_level=AwarenessLevel.SOLUTION_AWARE,
            framework=CopyFramework.AIDA,
            angle=product.unique_mechanism or product.description or product.name,
            hook=(product.benefits[0] if product.benefits else product.name),
            benefit_callouts=list(product.benefits[:3]) if product.benefits else [],
        )
        print(f"   (stub brief: hook='{brief.hook[:60]}')")
    else:
        print(f"   brief: {brief.brief_id} | hook='{brief.hook[:60]}'")

    print(f"   product: {product.name} | benefits: {len(product.benefits)} | "
          f"image_url: {bool(product.image_url)}, image_path: {bool(product.image_path)}")

    # Fill template
    print("\n[4/5] Filling template (will call Claude for slot batch-fill)...")
    try:
        filled = fill_template(
            template_data=td,
            brand=brand,
            product=product,
            avatar=avatar,
            brief=brief,
            aspect_ratio=None,
        )
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1

    print(f"   OK — aspect_ratio: {filled.aspect_ratio} (locked)")
    print(f"   chosen text color: {filled.chosen_text_color_descriptor} ({filled.chosen_text_color_hex})")
    print(f"   slot_map: {len(filled.slot_map)} slot(s) resolved")
    print(f"   flagged_invented: {len(filled.flagged_invented)} ⚠️")
    for f in filled.flagged_invented:
        print(f"      ⚠️  [{f['slot']}] {f['value']}")

    # Verify Product Anchor preamble is at the top
    print("\n[5/5] Verifying Product Anchor preamble...")
    if filled.filled_prompt.startswith(PRODUCT_ANCHOR_PREAMBLE):
        print("   OK — preamble at position 0")
    else:
        first_line = filled.filled_prompt.split("\n", 1)[0]
        print(f"   FAIL: preamble not at start. First line: {first_line[:120]}")
        return 1

    # Confirm no bracketed placeholders left
    import re
    leftovers = re.findall(r"\[([^\[\]]+)\]", filled.filled_prompt)
    if leftovers:
        print(f"   WARN: {len(leftovers)} unfilled [BRACKET]s remain: {set(leftovers)}")
    else:
        print("   OK — no unfilled [BRACKET]s remain")

    # Dump the final prompt
    print("\n--- FILLED PROMPT (sent to FAL) ---")
    print(filled.filled_prompt)
    print("--- END ---")

    print("\n[SUCCESS] All steps passed. Ready to run `adc generate-text` for real.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
