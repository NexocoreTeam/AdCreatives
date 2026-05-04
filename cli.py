"""AdCreatives CLI — AI-powered ad creative generation for Meta and TikTok."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def cli():
    """AdCreatives — Generate high-converting ad creatives with AI."""
    pass


# ─── Client Management ──────────────────────────────────────────────────────


@cli.command()
@click.option("--name", required=True, help="Client slug (lowercase, no spaces)")
def init_client(name: str):
    """Create a new client from the template."""
    src = Path("clients/_template")
    dest = Path("clients") / name

    if dest.exists():
        console.print(f"[red]Client '{name}' already exists at {dest}[/red]")
        raise SystemExit(1)

    shutil.copytree(src, dest)
    console.print(f"[green]Created client '{name}' at {dest}[/green]")
    console.print(f"  Edit {dest}/brand.yaml to configure brand identity")
    console.print(f"  Edit {dest}/products/example-product.yaml for your first product")
    console.print(f"  Add reviews to {dest}/voc/ for VOC mining")


@cli.command()
def list_clients():
    """List all configured clients."""
    from models.loader import list_clients as _list_clients, list_products

    clients = _list_clients()
    if not clients:
        console.print("[yellow]No clients found. Run: adc init-client --name your-client[/yellow]")
        return

    table = Table(title="Clients")
    table.add_column("Client", style="cyan")
    table.add_column("Products", style="green")

    for client in clients:
        products = list_products(client)
        table.add_row(client, ", ".join(products) or "[dim]none[/dim]")

    console.print(table)


# ─── Brand Research (auto + interactive) ────────────────────────────────────


def _flatten(field):
    """Strip {value, confidence, source} envelopes recursively to plain values."""
    if isinstance(field, dict) and "value" in field and "confidence" in field:
        return field["value"]
    if isinstance(field, dict):
        return {k: _flatten(v) for k, v in field.items()}
    if isinstance(field, list):
        return [_flatten(item) for item in field]
    return field


def _slugify(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "untitled"


@cli.command()
@click.option("--client", required=True, help="Client slug (will be created if missing)")
@click.option("--url", required=True, help="Brand homepage URL")
@click.option("--max-products", default=3, type=int, help="Max products to focus on")
@click.option("--auto/--review", default=False,
              help="--auto skips PHASE 4 confirmations and accepts all extractions as-is")
def research(client: str, url: str, max_products: int, auto: bool):
    """Brand research using Motion's interview-first methodology.

    Phase 1: 6 batched seed questions about products, audience, competitors,
    constraints, and existing creative.
    Phase 2: Web research — fetches homepage and standard sub-pages.
    Phase 3: Compiles a comprehensive brand-context.md doc using the
    motion/brand-intake skill + structured data with confidence tagging.
    Phase 4: Interactive review — confirm extractions, fill gaps, write YAMLs.
    """
    import shutil
    import yaml as _yaml

    from strategy.researcher import (
        INTAKE_QUESTIONS,
        confidence_buckets,
        extract_brand_colors_via_vision,
        fetch_pages,
        fetch_shopify_bestsellers,
        find_logo_url,
        is_shopify_site,
        parse_shopify_product_cards,
        run_brand_intake,
    )

    client_dir = Path("clients") / client

    if not client_dir.exists():
        if not click.confirm(
            f"Client '{client}' doesn't exist. Create from template?", default=True
        ):
            raise SystemExit(0)
        shutil.copytree("clients/_template", client_dir)
        console.print(f"[green]Created clients/{client}/[/green]")
    elif (client_dir / "brand.yaml").exists():
        console.print(f"[yellow]Warning: clients/{client}/brand.yaml already exists.[/yellow]")
        if not click.confirm("Overwrite existing files at the end?", default=False):
            raise SystemExit(0)

    # ─── PHASE 1: INTAKE INTERVIEW ────────────────────────────────────────
    console.print("\n[bold cyan]PHASE 1 — INTAKE INTERVIEW[/bold cyan]")
    console.print("[dim]Answer all questions before research begins. Type 'skip' to leave blank.[/dim]\n")
    brand_name = click.prompt("  Brand name", default="")
    console.print()
    for q in INTAKE_QUESTIONS:
        console.print(f"  [yellow]Q[/yellow] {q['prompt']}")
    console.print()

    seed_answers: dict[str, str] = {}
    for q in INTAKE_QUESTIONS:
        ans = click.prompt(f"  [{q['key']}]", default=q["default"])
        seed_answers[q["key"]] = "" if ans.lower() == "skip" else ans

    # ─── PHASE 2: WEB RESEARCH ────────────────────────────────────────────
    console.print("\n[bold cyan]PHASE 2 — WEB RESEARCH[/bold cyan]")
    with console.status(f"Fetching pages from {url}..."):
        pages = fetch_pages(url)

    if not pages:
        console.print(f"[red]No pages fetched from {url}. Check the URL.[/red]")
        raise SystemExit(1)
    console.print(f"[green]Fetched {len(pages)} pages:[/green]")
    for page_url in pages:
        console.print(f"  - {page_url}")

    # Detect Shopify and pull best-sellers if so
    homepage_html = next(iter(pages.values()), "")
    bestsellers = []
    if is_shopify_site(homepage_html):
        console.print("\n[cyan]Detected Shopify store — fetching best-sellers (3 pages)...[/cyan]")
        with console.status("Pulling /collections/all?sort_by=best-selling..."):
            best_pages = fetch_shopify_bestsellers(url, page_count=3)
            for page_url, page_html in best_pages:
                cards = parse_shopify_product_cards(page_html, url)
                # Re-rank by overall position across pages
                for card in cards:
                    card.rank = len(bestsellers) + 1
                    bestsellers.append(card)
        console.print(f"[green]Parsed {len(bestsellers)} best-selling products from {len(best_pages)} pages.[/green]")
        if bestsellers:
            console.print("  [dim]Top 5:[/dim]")
            for c in bestsellers[:5]:
                console.print(f"    [dim]{c.rank}. {c.name}[/dim]")

    # Find the logo and run GPT-4o vision to extract real brand colors
    vision_colors = None
    logo_url = find_logo_url(homepage_html, url)
    if logo_url:
        console.print(f"\n[cyan]Found logo: {logo_url}[/cyan]")
        with console.status("Running GPT-4o vision on logo for brand colors..."):
            vision_colors = extract_brand_colors_via_vision(logo_url)
        if vision_colors and vision_colors.get("primary"):
            console.print(
                f"[green]Vision colors:[/green] "
                f"primary={vision_colors.get('primary')} "
                f"secondary={vision_colors.get('secondary')} "
                f"accent={vision_colors.get('accent', 'none')}"
            )
        else:
            console.print("[yellow]Vision extraction returned no colors — falling back to CSS extraction.[/yellow]")
    else:
        console.print("[yellow]Couldn't find logo URL — colors will come from CSS extraction only.[/yellow]")

    # ─── PHASE 3: BUILD BRAND CONTEXT ─────────────────────────────────────
    console.print("\n[bold cyan]PHASE 3 — BUILDING BRAND CONTEXT[/bold cyan]")
    with console.status("Compiling brand-context.md + structured data with Claude Sonnet 4.6..."):
        result = run_brand_intake(
            brand_name=brand_name,
            brand_url=url,
            seed_answers=seed_answers,
            pages=pages,
            bestsellers=bestsellers,
            vision_colors=vision_colors,
        )
    data = result.data
    console.print("[green]Compiled.[/green]\n")

    context_path = client_dir / "brand-context.md"
    context_path.write_text(result.brand_context_md, encoding="utf-8")
    console.print(f"[green]Wrote {context_path}[/green]")
    console.print(f"[dim]Open it: cat {context_path}[/dim]\n")

    # ─── PHASE 4: REVIEW & CONFIRM ────────────────────────────────────────
    console.print("[bold cyan]PHASE 4 — REVIEW EXTRACTIONS[/bold cyan]\n")
    if auto:
        console.print("[dim](--auto mode: skipping interactive review, accepting all extractions)[/dim]\n")

    # Brand colors get special treatment — always reviewed because they're
    # high-impact and CSS extraction is unreliable.
    brand = data.get("brand", {})
    color_fields = brand.get("colors", {}) or {}
    if color_fields:
        console.print("[bold magenta]BRAND COLORS — special review (high impact, unreliable extraction):[/bold magenta]")
        for color_name in ("primary", "secondary", "background", "accent"):
            field = color_fields.get(color_name)
            if not isinstance(field, dict):
                continue
            current = field.get("value", "")
            source = field.get("source", "")
            console.print(f"  [cyan]{color_name}[/cyan]: [bold]{current}[/bold]  [dim]({source})[/dim]")
            if not auto:
                new_val = click.prompt(f"    Confirm {color_name} (Enter to accept, or paste a hex)", default=str(current))
                if new_val and new_val != current:
                    field["value"] = new_val
                    field["confidence"] = "high"
                    field["source"] = "user override"
        if auto:
            console.print(
                "  [yellow]REVIEW NEEDED:[/yellow] auto mode used CSS/vision extraction. "
                "Verify these match your real brand palette before generating creative."
            )
        console.print()

    buckets = confidence_buckets(data)

    if buckets["high"]:
        console.print(f"[bold green]HIGH CONFIDENCE — {len(buckets['high'])} items auto-accepted:[/bold green]")
        for path, field in buckets["high"]:
            val = field.get("value")
            display = str(val)[:80] + ("..." if len(str(val)) > 80 else "")
            console.print(f"  [green]✓[/green] {path}: {display!r}")
            console.print(f"      [dim]from {field.get('source', '')}[/dim]")
        console.print()

    if buckets["medium"]:
        console.print(f"[bold yellow]MEDIUM CONFIDENCE — {len(buckets['medium'])} items:[/bold yellow]")
        for path, field in buckets["medium"]:
            console.print(f"\n  {path}: {field.get('value')!r}")
            console.print(f"  [dim]source: {field.get('source', '')}[/dim]")
            if not auto and not click.confirm("  Accept?", default=True):
                new_val = click.prompt("  Correct value (or empty to skip)", default="")
                if new_val:
                    field["value"] = new_val
        console.print()

    if buckets["low"] or buckets["unknown"]:
        items = buckets["low"] + buckets["unknown"]
        console.print(f"[bold red]LOW / UNKNOWN — {len(items)} items:[/bold red]")
        for path, field in items:
            console.print(f"\n  {path}")
            current = field.get("value")
            if current:
                console.print(f"  [dim]My guess: {current!r} ({field.get('source', 'inference')})[/dim]")
            if not auto:
                answer = click.prompt("  Value (or 'skip')", default=str(current) if current else "skip")
                if answer.lower() != "skip":
                    field["value"] = answer
        console.print()

    questions = data.get("questions_for_user", []) or []
    if questions and not auto:
        console.print(f"[bold cyan]LLM ASKS — {len(questions)} clarifying questions:[/bold cyan]")
        extra_answers = {}
        for q in questions:
            console.print(f"\n  [cyan]{q.get('field', '?')}[/cyan]")
            console.print(f"  Q: {q.get('question', '')}")
            console.print(f"  [dim]Why: {q.get('why_asking', '')}[/dim]")
            answer = click.prompt("  A (or 'skip')", default="skip")
            if answer.lower() != "skip":
                extra_answers[q.get("field", "")] = answer
        for field_path, value in extra_answers.items():
            parts = field_path.split(".")
            target = data
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            if isinstance(target.get(parts[-1]), dict) and "value" in target[parts[-1]]:
                target[parts[-1]]["value"] = value
            else:
                target[parts[-1]] = {"value": value, "confidence": "high", "source": "user"}
    elif questions and auto:
        console.print(f"[dim]LLM had {len(questions)} clarifying questions — skipped in --auto mode.[/dim]")
        for q in questions:
            console.print(f"  [dim]- {q.get('field')}: {q.get('question')}[/dim]")

    products = data.get("products", []) or []
    chosen_products = []
    if products:
        console.print(f"\n[bold]PRODUCTS — {len(products)} found:[/bold]")
        for i, p in enumerate(products, 1):
            name = _flatten(p.get("name", "?"))
            price = _flatten(p.get("price", "?"))
            hero = " [HERO]" if p.get("is_likely_hero") else ""
            console.print(f"  [{i}] {name} — {price}{hero}")
        default_choice = ",".join(
            str(i + 1) for i, p in enumerate(products[:max_products])
            if p.get("is_likely_hero")
        ) or "1"
        if auto:
            choice = default_choice
            console.print(f"\n  [dim](--auto: picking {default_choice})[/dim]")
        else:
            choice = click.prompt(
                f"\n  Which to focus on? (comma-separated, max {max_products}, or 'all')",
                default=default_choice,
            )
        if choice.strip().lower() == "all":
            chosen_products = products[:max_products]
        else:
            indices = [int(i.strip()) - 1 for i in choice.split(",") if i.strip().isdigit()]
            chosen_products = [products[i] for i in indices if 0 <= i < len(products)][:max_products]

        for product in chosen_products:
            pname = _flatten(product.get("name", "?"))
            console.print(f"\n  [cyan]Follow-ups for: {pname}[/cyan]")
            if not auto:
                mech = click.prompt("    Unique mechanism / why it works (or 'skip')", default="skip")
                if mech.lower() != "skip":
                    product["_unique_mechanism"] = mech
                benefits = click.prompt("    Top 3 benefits, comma-separated (or 'skip')", default="skip")
                if benefits.lower() != "skip":
                    product["_benefits"] = [b.strip() for b in benefits.split(",")]

    console.print("\n[bold magenta]CUSTOMER AVATAR[/bold magenta] (site can't tell us this — please share):")
    signals = data.get("avatar_signals", {}) or {}
    if signals:
        console.print(f"  [dim]Site signals: {signals.get('inferred_demographic', '?')}[/dim]")

    auto_pains: list[str] = []
    auto_desires: list[str] = []
    auto_objections: list[str] = []
    auto_triggers: list[str] = []

    if auto:
        demo = str(signals.get("inferred_demographic", ""))
        psycho = ""
        aware = signals.get("inferred_awareness_level", "problem_aware")
        # Use the raw lists directly — comma-splitting breaks on punctuation inside sentences.
        auto_pains = [p for p in signals.get("inferred_pain_points", []) if p]
        auto_desires = [d for d in signals.get("inferred_desires", []) if d]
        auto_objections = [o for o in signals.get("inferred_objections", []) if o]
        auto_triggers = [t for t in signals.get("inferred_trigger_events", []) if t]
        pain_input = desire_input = objection_input = trigger_input = "skip"
        console.print("  [dim](--auto: using signals from research)[/dim]")
    else:
        demo = click.prompt(
            "  Demographic (age, gender, location, income)",
            default=str(signals.get("inferred_demographic", "")),
        )
        psycho = click.prompt(
            "  Psychographic (values, lifestyle — 1-2 sentences)", default=""
        )
        aware = click.prompt(
            "  Awareness level",
            type=click.Choice(
                ["unaware", "problem_aware", "solution_aware", "product_aware", "most_aware"]
            ),
            default=signals.get("inferred_awareness_level", "problem_aware"),
        )
        pain_input = click.prompt("  Top 3 pain points, comma-separated (or 'skip')", default="skip")
        desire_input = click.prompt("  Top desires, comma-separated (or 'skip')", default="skip")
        objection_input = click.prompt("  Top objections, comma-separated (or 'skip')", default="skip")
        trigger_input = click.prompt("  Trigger events that make them buy (or 'skip')", default="skip")

    brand_data = data.get("brand", {})
    brand_yaml = {
        "name": _flatten(brand_data.get("name", {"value": ""})),
        "colors": {
            "primary": _flatten(brand_data.get("colors", {}).get("primary", {"value": "#000000"})),
            "secondary": _flatten(brand_data.get("colors", {}).get("secondary", {"value": "#FFFFFF"})),
            "background": _flatten(brand_data.get("colors", {}).get("background", {"value": "#FFFFFF"})),
        },
        "typography": {
            "heading": _flatten(brand_data.get("typography", {}).get("heading", {"value": "Sans-Serif"})),
            "body": _flatten(brand_data.get("typography", {}).get("body", {"value": "Sans-Serif"})),
        },
        "tone": _flatten(brand_data.get("tone", {"value": ""})),
        "audience": {
            "age_range": _flatten(brand_data.get("audience", {}).get("age_range", {"value": ""})),
            "gender": _flatten(brand_data.get("audience", {}).get("gender", {"value": ""})),
            "interests": _flatten(brand_data.get("audience", {}).get("interests", {"value": []})),
        },
        "platforms": ["meta", "tiktok"],
        "press_mentions": _flatten(brand_data.get("press_mentions", {"value": []})),
        "social_proof": _flatten(brand_data.get("social_proof", {"value": []})),
        "founded": _flatten(brand_data.get("founded", {"value": ""})),
        "founder": _flatten(brand_data.get("founder", {"value": ""})),
        "mission": _flatten(brand_data.get("mission", {"value": ""})),
        "tagline": _flatten(brand_data.get("tagline", {"value": ""})),
    }

    if auto:
        pain_list = [
            {"pain": p, "intensity": "medium", "customer_language": [], "source": "auto_from_site_signals"}
            for p in auto_pains
        ]
        desire_list = [{"desire": d, "customer_language": []} for d in auto_desires]
        objection_list = list(auto_objections)
        trigger_list = list(auto_triggers)
    else:
        pain_list = (
            []
            if pain_input.lower() == "skip"
            else [
                {"pain": p.strip(), "intensity": "medium", "customer_language": [], "source": "research_interview"}
                for p in pain_input.split(",") if p.strip()
            ]
        )
        desire_list = (
            []
            if desire_input.lower() == "skip"
            else [
                {"desire": d.strip(), "customer_language": []}
                for d in desire_input.split(",") if d.strip()
            ]
        )
        objection_list = (
            [] if objection_input.lower() == "skip"
            else [o.strip() for o in objection_input.split(",") if o.strip()]
        )
        trigger_list = (
            [] if trigger_input.lower() == "skip"
            else [t.strip() for t in trigger_input.split(",") if t.strip()]
        )

    avatar_yaml = {
        "name": "Auto-drafted — please review and rename",
        "demographic": demo,
        "psychographic": psycho,
        "pain_points": pain_list,
        "desires": desire_list,
        "objections": objection_list,
        "trigger_events": trigger_list,
        "awareness_level": aware,
        "language_patterns": [],
        "current_solutions": [],
    }

    console.print("\n[bold]READY TO WRITE:[/bold]")
    console.print(f"  brand.yaml ({len([k for k in brand_yaml if brand_yaml[k]])} populated fields)")
    console.print(f"  {len(chosen_products)} product YAML(s)")
    console.print(f"  avatar.yaml (DRAFT — please review)")

    if not auto and not click.confirm(f"\nWrite to clients/{client}/?", default=True):
        console.print("[yellow]Aborted, no files written.[/yellow]")
        raise SystemExit(0)

    (client_dir / "brand.yaml").write_text(
        _yaml.dump(brand_yaml, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    products_dir = client_dir / "products"
    products_dir.mkdir(exist_ok=True)
    written_products = []
    for product in chosen_products:
        pname = _flatten(product.get("name", "untitled"))
        slug = _slugify(pname)
        prod_yaml = {
            "name": pname,
            "description": _flatten(product.get("description", {"value": ""})),
            "price": str(_flatten(product.get("price", {"value": ""}))),
            "category": "general",
            "image_path": "",
            "image_url": _flatten(product.get("image_url", {"value": ""})),
            "url": _flatten(product.get("url", {"value": ""})),
            "unique_mechanism": product.get("_unique_mechanism", ""),
            "benefits": product.get("_benefits", []),
            "objections": [],
            "social_proof": [],
        }
        path = products_dir / f"{slug}.yaml"
        path.write_text(_yaml.dump(prod_yaml, sort_keys=False, allow_unicode=True), encoding="utf-8")
        written_products.append(slug)

    (client_dir / "avatar.yaml").write_text(
        _yaml.dump(avatar_yaml, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    console.print(f"\n[green]Wrote brand.yaml, {len(written_products)} product(s), and avatar.yaml.[/green]")
    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  1. Review the files: clients/{client}/brand.yaml, avatar.yaml, products/")
    console.print(f"  2. Add customer reviews to clients/{client}/voc/ (.json or .txt)")
    console.print(f"  3. adc mine-voc --client {client} --category <category>")
    console.print(f"  4. adc voc-to-avatar --client {client} --apply  (after reviewing the VOC)")
    if written_products:
        console.print(f"  5. adc brief --client {client} --product {written_products[0]} --angles 6")


# ─── Strategy: Brief Generation ─────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--product", required=True, help="Product slug")
@click.option("--angles", default=5, help="Number of messaging angles to generate")
@click.option("--platform", default="meta", help="Target platform: meta, tiktok")
def brief(client: str, product: str, angles: int, platform: str):
    """Generate creative briefs with messaging angles for a product."""
    from models.loader import load_brand, load_product, load_avatar, load_winning_patterns, save_brief
    from strategy.brief_generator import generate_briefs

    with console.status("Loading client data..."):
        brand = load_brand(client)
        prod = load_product(client, product)
        avatar = load_avatar(client)
        patterns = load_winning_patterns(client)

    if not avatar:
        console.print(
            f"[yellow]No avatar found for '{client}'. "
            f"Run 'adc mine-voc' or create clients/{client}/avatar.yaml[/yellow]"
        )
        raise SystemExit(1)

    with console.status(f"Generating {angles} creative briefs..."):
        briefs = generate_briefs(
            client_slug=client,
            product=prod,
            brand=brand,
            avatar=avatar,
            count=angles,
            platform=platform,
            winning_patterns=patterns,
        )

    table = Table(title=f"Creative Briefs — {brand.name} / {prod.name}")
    table.add_column("#", style="dim")
    table.add_column("Hook", style="cyan", max_width=50)
    table.add_column("Angle", style="green", max_width=30)
    table.add_column("Framework", style="yellow")
    table.add_column("Brief ID", style="dim")

    for i, b in enumerate(briefs, 1):
        path = save_brief(client, b)
        table.add_row(str(i), b.hook, b.angle, b.framework.value, b.brief_id)

    console.print(table)
    console.print(f"\n[green]Saved {len(briefs)} briefs to clients/{client}/briefs/[/green]")
    console.print("Generate images: adc generate --client {client} --brief <brief-id> --style <style>")


# ─── Show Prompt Template ────────────────────────────────────────────────────


@cli.command()
@click.option("--prompt", "prompt_id", required=True, help="Library prompt ID (e.g. cooper-07-us-vs-them)")
def show_prompt(prompt_id: str):
    """Show a prompt template's full details and raw template text."""
    from models.library import load_prompt as load_lib_prompt

    p = load_lib_prompt(prompt_id)

    console.print(f"\n[bold cyan]{p.name}[/bold cyan] ({p.id})")
    console.print(f"[dim]Source: {p.source}[/dim]")
    console.print(f"[dim]Category: {p.category} | Products: {', '.join(p.product_types)} | "
                  f"Funnel: {p.funnel_stage}[/dim]")
    console.print(f"[dim]Aspect ratios: {', '.join(p.aspect_ratios)} | "
                  f"Audience: {', '.join(p.audience_fit)}[/dim]")
    if p.description:
        console.print(f"\n{p.description}")
    console.print(f"\n[bold]Template Prompt:[/bold]")
    console.print(f"\n{p.template_prompt}")
    console.print(f"\n[green]To use this, ask Claude to customize it for your client/product.[/green]")
    console.print(f"Or copy the template and fill in the [PLACEHOLDERS] manually.")


# ─── Show Client Context ────────────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--product", required=True, help="Product slug")
def show_context(client: str, product: str):
    """Show the full brand + product + avatar context for a client.

    Use this to give Claude (in chat) all the context it needs to write
    customized prompts for your product. Copy-paste the output into Claude.
    """
    from models.loader import load_brand, load_product, load_avatar
    from generators.prompt_engine import _build_product_context

    brand = load_brand(client)
    prod = load_product(client, product)
    avatar = load_avatar(client)

    context = _build_product_context(brand, prod, avatar)

    console.print(f"\n[bold cyan]Client Context: {brand.name} / {prod.name}[/bold cyan]")
    console.print(f"[dim]Copy this into Claude to give it full brand context.[/dim]\n")
    console.print(context)

    # Also show product image URLs
    console.print(f"\n[bold]Product Images (attach these in Higgsfield/Nano Banana 2):[/bold]")
    if prod.image_url:
        console.print(f"  Primary: {prod.image_url}")
    if prod.image_path:
        console.print(f"  Local: clients/{client}/{prod.image_path}")
    for img in prod.additional_images:
        console.print(f"  Additional: clients/{client}/{img}")


# ─── VOC Mining ──────────────────────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--category", default="general", help="Product category for analysis context")
def mine_voc(client: str, category: str):
    """Mine voice-of-customer data from reviews in clients/{client}/voc/."""
    from strategy.voc_miner import mine_voc_for_client, voc_to_avatar_fields

    with console.status(f"Mining VOC data for '{client}'..."):
        voc_data = mine_voc_for_client(client, category)

    # Display results
    pain_points = voc_data.get("pain_points", [])
    console.print(f"\n[green]Found {len(pain_points)} pain points:[/green]")
    for p in pain_points[:5]:
        if isinstance(p, dict):
            console.print(f"  [{p.get('intensity', '?')}] {p.get('pain', '')}")
            for lang in p.get("customer_language", [])[:2]:
                console.print(f"    → \"{lang}\"")

    # Save extracted data
    import yaml
    output_path = Path("clients") / client / "voc" / "extracted_pains.yaml"
    with open(output_path, "w") as f:
        yaml.dump(voc_data, f, default_flow_style=False, sort_keys=False)

    console.print(f"\n[green]Saved to {output_path}[/green]")
    console.print("Use this to update your avatar: clients/{client}/avatar.yaml")


# ─── VOC → Avatar Sync ───────────────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--mode", type=click.Choice(["replace", "merge"]), default="replace",
              help="replace = overwrite avatar fields with VOC; merge = append")
@click.option("--apply/--dry-run", default=False,
              help="--dry-run (default) prints diff only; --apply writes changes")
def voc_to_avatar(client: str, mode: str, apply: bool):
    """Sync extracted VOC into the client's avatar.yaml.

    Reads clients/{client}/voc/extracted_pains.yaml and updates avatar.yaml.
    Always preserves: name, demographic, psychographic, awareness_level.
    Replaces or merges: pain_points, desires, objections, trigger_events, language_patterns.

    Default is dry-run — preview the diff before committing with --apply.
    """
    import yaml as _yaml
    from models.loader import load_avatar, save_avatar
    from strategy.voc_miner import voc_to_avatar_fields

    voc_path = Path("clients") / client / "voc" / "extracted_pains.yaml"
    if not voc_path.exists():
        console.print(f"[red]No extracted VOC found at {voc_path}[/red]")
        console.print(f"Run: adc mine-voc --client {client} --category <category>")
        raise SystemExit(1)

    with open(voc_path) as f:
        voc_data = _yaml.safe_load(f)

    new_fields = voc_to_avatar_fields(voc_data)
    avatar = load_avatar(client)
    if avatar is None:
        console.print(f"[red]No existing avatar at clients/{client}/avatar.yaml[/red]")
        raise SystemExit(1)

    before = {
        "pain_points": len(avatar.pain_points),
        "desires": len(avatar.desires),
        "objections": len(avatar.objections),
        "trigger_events": len(avatar.trigger_events),
        "language_patterns": len(avatar.language_patterns),
    }

    if mode == "replace":
        avatar.pain_points = new_fields["pain_points"]
        avatar.desires = new_fields["desires"]
        avatar.objections = new_fields["objections"]
        avatar.trigger_events = new_fields["trigger_events"]
        avatar.language_patterns = new_fields["language_patterns"]
    else:  # merge — append, dedup by primary key
        existing_pains = {p.pain for p in avatar.pain_points}
        avatar.pain_points.extend(
            p for p in new_fields["pain_points"] if p.pain not in existing_pains
        )
        existing_desires = {d.desire for d in avatar.desires}
        avatar.desires.extend(
            d for d in new_fields["desires"] if d.desire not in existing_desires
        )
        avatar.objections = list(dict.fromkeys(avatar.objections + new_fields["objections"]))
        avatar.trigger_events = list(dict.fromkeys(
            avatar.trigger_events + new_fields["trigger_events"]
        ))
        avatar.language_patterns = list(dict.fromkeys(
            avatar.language_patterns + new_fields["language_patterns"]
        ))

    after = {
        "pain_points": len(avatar.pain_points),
        "desires": len(avatar.desires),
        "objections": len(avatar.objections),
        "trigger_events": len(avatar.trigger_events),
        "language_patterns": len(avatar.language_patterns),
    }

    table = Table(title=f"Avatar field counts ({mode} mode)")
    table.add_column("Field", style="cyan")
    table.add_column("Before", style="dim")
    table.add_column("After", style="green")
    table.add_column("Delta", style="yellow")
    for key in before:
        delta = after[key] - before[key]
        sign = "+" if delta >= 0 else ""
        table.add_row(key, str(before[key]), str(after[key]), f"{sign}{delta}")
    console.print(table)

    console.print("\n[cyan]Preserved (untouched):[/cyan]")
    console.print(f"  name: {avatar.name}")
    console.print(f"  demographic: {avatar.demographic[:80]}...")
    console.print(f"  awareness_level: {avatar.awareness_level}")

    if apply:
        path = save_avatar(client, avatar, backup=True)
        console.print(f"\n[green]Wrote {path}[/green]")
        console.print(f"[dim]Backup at {path.with_suffix('.yaml.bak')}[/dim]")
    else:
        console.print("\n[yellow]Dry run — no changes written.[/yellow]")
        console.print(f"Re-run with --apply to write changes to clients/{client}/avatar.yaml")


# ─── Performance Feedback Loop ───────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True)
@click.option("--creative-id", required=True, help="Creative filename or ID")
@click.option("--style", default="", help="Style used")
@click.option("--hook", default="", help="Hook text used")
@click.option("--angle", default="", help="Messaging angle")
@click.option("--platform", default="meta")
@click.option("--ctr", type=float, default=None, help="Click-through rate (%)")
@click.option("--cpa", type=float, default=None, help="Cost per acquisition ($)")
@click.option("--roas", type=float, default=None, help="Return on ad spend")
@click.option("--spend", type=float, default=None, help="Total spend ($)")
@click.option("--verdict", default="", help="winner, loser, control, testing")
@click.option("--notes", default="", help="What worked or didn't")
def log_result(client: str, creative_id: str, **kwargs):
    """Log ad performance data for the feedback loop."""
    from models.loader import load_performance_log, save_performance_log
    from models.result import CreativeResult

    existing = load_performance_log(client)

    result = CreativeResult(
        creative_id=creative_id,
        client=client,
        product=kwargs.get("product", ""),
        style=kwargs["style"],
        hook=kwargs["hook"],
        angle=kwargs["angle"],
        platform=kwargs["platform"],
        ctr=kwargs["ctr"],
        cpa=kwargs["cpa"],
        roas=kwargs["roas"],
        spend=kwargs["spend"],
        verdict=kwargs["verdict"],
        notes=kwargs["notes"],
    )

    existing.append(result)
    save_performance_log(client, existing)
    console.print(f"[green]Logged result for '{creative_id}' ({kwargs.get('verdict', 'logged')})[/green]")


@cli.command()
@click.option("--client", required=True)
@click.option("--days", default=90, help="Analyze last N days")
def analyze_results(client: str, days: int):
    """Analyze performance data and generate winning patterns."""
    from models.loader import load_performance_log, save_winning_patterns
    from strategy.pattern_learner import analyze_results as _analyze

    results = load_performance_log(client)
    if not results:
        console.print(f"[yellow]No performance data for '{client}'. Use 'adc log-result' first.[/yellow]")
        return

    with console.status(f"Analyzing {len(results)} results from last {days} days..."):
        patterns = _analyze(results, client, days)

    save_winning_patterns(client, patterns)

    console.print(f"\n[green]Analyzed {patterns.total_creatives_analyzed} creatives[/green]")

    if patterns.best_styles:
        console.print("\n[cyan]Best styles:[/cyan]")
        for s in patterns.best_styles:
            console.print(f"  {s.style}: {s.avg_ctr:.2f}% CTR (n={s.sample_size})")

    if patterns.recommendations:
        console.print("\n[cyan]Recommendations:[/cyan]")
        for r in patterns.recommendations:
            console.print(f"  • {r}")


# ─── Creative Matrix ─────────────────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True)
@click.option("--product", required=True)
@click.option("--hooks", required=True, help="Comma-separated hook types")
@click.option("--styles", required=True, help="Comma-separated style slugs")
@click.option("--platforms", default="meta", help="Comma-separated platforms")
def matrix(client: str, product: str, hooks: str, styles: str, platforms: str):
    """Generate a creative testing matrix (all combinations)."""
    from models.loader import load_brand, load_product
    from strategy.matrix_builder import MatrixConfig, build_matrix, estimate_matrix_cost

    brand = load_brand(client)
    prod = load_product(client, product)

    config = MatrixConfig(
        hooks=[h.strip() for h in hooks.split(",")],
        styles=[s.strip() for s in styles.split(",")],
        platforms=[p.strip() for p in platforms.split(",")],
    )

    combos = build_matrix(config)
    cost = estimate_matrix_cost(combos)

    table = Table(title="Creative Matrix")
    table.add_column("#", style="dim")
    table.add_column("Hook", style="cyan")
    table.add_column("Style", style="green")
    table.add_column("Platform", style="yellow")

    for i, combo in enumerate(combos, 1):
        table.add_row(
            str(i),
            combo.get("hook", ""),
            combo.get("style", ""),
            combo.get("platform", ""),
        )

    console.print(table)
    console.print(f"\n[cyan]Total combinations: {cost['combinations']}[/cyan]")
    console.print(f"[cyan]Estimated images: {cost['total_images']}[/cyan]")
    console.print(f"[cyan]Estimated cost: {cost['estimated_cost']}[/cyan]")
    console.print("\nTo generate all, run each combination with 'adc generate'")


# ─── Compliance Check ────────────────────────────────────────────────────────


@cli.command()
@click.option("--text", default=None, help="Text to check")
@click.option("--brief-id", default=None, help="Brief ID to check")
@click.option("--client", default=None, help="Client slug for brand-specific rules")
@click.option("--category", multiple=True, default=["general"], help="Rule categories to check")
def check_compliance(text: str | None, brief_id: str | None, client: str | None, category: tuple):
    """Check ad copy for compliance issues."""
    from validators.compliance.scanner import scan_text, scan_brief, Severity

    if brief_id and client:
        from models.loader import load_brief
        brief_obj = load_brief(client, brief_id)
        issues = scan_brief(
            brief_obj.model_dump(),
            categories=list(category),
            client_slug=client,
        )
    elif text:
        issues = scan_text(text, categories=list(category), client_slug=client)
    else:
        console.print("[red]Provide --text or --brief-id + --client[/red]")
        return

    if not issues:
        console.print("[green]No compliance issues found.[/green]")
        return

    errors = [i for i in issues if i.severity == Severity.ERROR]
    warnings = [i for i in issues if i.severity == Severity.WARNING]

    if errors:
        console.print(f"\n[red]{len(errors)} ERROR(s):[/red]")
        for i in errors:
            console.print(f"  [red]ERROR[/red] [{i.category}] {i.rule}: matched '{i.match}'")
            console.print(f"         {i.context}")

    if warnings:
        console.print(f"\n[yellow]{len(warnings)} WARNING(s):[/yellow]")
        for i in warnings:
            console.print(f"  [yellow]WARN[/yellow]  [{i.category}] {i.rule}: matched '{i.match}'")


# ─── Check Copy Length ───────────────────────────────────────────────────────


@cli.command()
@click.option("--text", required=True, help="The ad copy text to check")
@click.option("--platform", required=True, help="Platform: meta, google, tiktok, linkedin, x")
@click.option("--field", required=True, help="Field: headline, primary_text, description, etc. (use --list-fields to see)")
@click.option("--trim/--no-trim", default=False, help="Show a trimmed suggestion if over limit")
def check_copy(text: str, platform: str, field: str, trim: bool):
    """Check ad copy text against platform char limits."""
    from validators.copy_checker import Severity, check_copy as _check, suggest_trim

    result = _check(text, platform=platform, field=field)

    icon = {
        Severity.OK: "[green]PASS[/green]",
        Severity.WARNING: "[yellow]WARN[/yellow]",
        Severity.ERROR: "[red]FAIL[/red]",
    }[result.severity]

    console.print(f"\n{icon} {result.platform}/{result.field}: {result.detail}")

    if not result.passed and trim:
        suggestion = suggest_trim(text, target=result.recommended)
        console.print(f"\n[cyan]Trimmed to {result.recommended} chars:[/cyan]")
        console.print(f"  {suggestion}")


@cli.command()
def list_copy_specs():
    """List all platforms and fields with their char limits."""
    from validators.copy_checker import PLATFORM_LIMITS, list_platforms

    for platform in list_platforms():
        table = Table(title=f"{platform.upper()} ad copy limits")
        table.add_column("Field", style="cyan")
        table.add_column("Recommended", style="green")
        table.add_column("Hard max", style="yellow")
        for field, limits in PLATFORM_LIMITS[platform].items():
            hard = str(limits["hard_max"]) if limits["hard_max"] is not None else "—"
            table.add_row(field, str(limits["recommended"]), hard)
        console.print(table)


# ─── Validate Image ──────────────────────────────────────────────────────────


@cli.command()
@click.option("--image", required=True, help="Path to image file")
@click.option("--client", default=None, help="Client slug for brand color checking")
@click.option("--platform", default="meta", help="Platform to validate against")
def validate(image: str, client: str | None, platform: str):
    """Validate a generated image against platform specs and brand colors."""
    from validators.platform_checker import check_image
    from validators.brand_checker import check_brand_colors

    image_path = Path(image)
    console.print(f"\nValidating: {image_path}")

    # Platform checks
    console.print(f"\n[cyan]Platform checks ({platform}):[/cyan]")
    platform_checks = check_image(image_path, platform)
    for c in platform_checks:
        icon = "[green]PASS[/green]" if c.passed else "[red]FAIL[/red]"
        console.print(f"  {icon} {c.check}: {c.detail}")

    # Brand color checks
    if client:
        from models.loader import load_brand
        brand = load_brand(client)
        color_dict = {
            "primary": brand.colors.primary,
            "secondary": brand.colors.secondary,
        }
        console.print(f"\n[cyan]Brand color checks ({client}):[/cyan]")
        brand_checks = check_brand_colors(image_path, color_dict)
        for c in brand_checks:
            icon = "[green]PASS[/green]" if c.passed else "[yellow]WARN[/yellow]"
            console.print(f"  {icon} {c.detail}")


# ─── Browse Prompt Library ───────────────────────────────────────────────────


@cli.command()
@click.option("--category", default=None, help="Filter by category: headline, comparison, ugc, etc.")
@click.option("--product-type", default=None, help="Filter by product type: apparel, food, etc.")
@click.option("--source", default=None, help="Filter by source dir: cooper, nanobana, custom")
@click.option("--platform", default=None, help="Filter by platform: meta, tiktok")
def browse_library(category: str | None, product_type: str | None,
                   source: str | None, platform: str | None):
    """Browse the prompt library with optional filters."""
    from models.library import list_prompts, list_categories

    prompts = list_prompts(
        category=category,
        product_type=product_type,
        platform=platform,
        source_dir=source,
    )

    if not prompts:
        console.print("[yellow]No prompts found matching filters.[/yellow]")
        console.print(f"[dim]Available categories: {', '.join(list_categories())}[/dim]")
        return

    table = Table(title=f"Prompt Library ({len(prompts)} prompts)")
    table.add_column("ID", style="cyan", max_width=30)
    table.add_column("Name", style="green", max_width=25)
    table.add_column("Category", style="yellow")
    table.add_column("Products", style="dim", max_width=20)
    table.add_column("Tags", style="dim", max_width=30)

    for p in prompts:
        table.add_row(
            p.id,
            p.name,
            p.category,
            ", ".join(p.product_types[:3]),
            ", ".join(p.tags[:4]),
        )

    console.print(table)
    console.print(f"\n[green]To use a prompt:[/green]")
    console.print("  adc use-prompt --client <client> --product <product> --prompt <id>")


if __name__ == "__main__":
    cli()
