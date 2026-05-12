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


# ─── Personas (Stage 2) ─────────────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--max-personas", default=4, type=int,
              help="Maximum number of personas to generate (1-4)")
def personas(client: str, max_personas: int):
    """Expand single avatar to multiple structured personas.

    Reads brand-context.md (which already identifies audience tiers) and
    generates one full CustomerAvatar YAML per persona under
    clients/<slug>/avatars/<persona-id>.yaml plus an _index.yaml roster.

    Each persona is genuinely distinct — different pains, triggers, awareness
    levels — so downstream stages (strategy matrix, brief) can target them.
    """
    from models.loader import load_brand
    from strategy.personas import build_personas, save_personas

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    context_path = client_dir / "brand-context.md"
    if not context_path.exists():
        console.print(
            f"[red]No brand-context.md at {context_path}. Run `adc research` first.[/red]"
        )
        raise SystemExit(1)

    brand = load_brand(client)
    brand_context_md = context_path.read_text(encoding="utf-8")

    console.print(
        f"\n[bold cyan]Expanding personas for {brand.name}[/bold cyan] "
        f"(up to {max_personas})"
    )

    with console.status("Identifying tiers + building personas with Claude Sonnet 4.6..."):
        result = build_personas(
            brand=brand,
            brand_context_md=brand_context_md,
            max_personas=max_personas,
        )

    if not result.personas:
        console.print("[yellow]No personas generated. Check brand-context.md content.[/yellow]")
        raise SystemExit(1)

    index_path, written = save_personas(client, result)
    console.print(f"\n[green]Wrote {len(written)} persona file(s):[/green]")
    for p in written:
        console.print(f"  - {p}")
    console.print(f"[green]Wrote roster: {index_path}[/green]")
    console.print()

    table = Table(title=f"Personas for {brand.name}")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Role", style="yellow")
    table.add_column("Awareness", style="dim")
    table.add_column("Confidence", style="dim")
    for p in result.index.get("personas", []):
        table.add_row(
            p.get("id", ""),
            p.get("name", ""),
            p.get("role", ""),
            p.get("awareness_level", ""),
            p.get("confidence", ""),
        )
    console.print(table)


# ─── Onboard wrapper (runs stages 1-5 in sequence) ──────────────────────────


@cli.command()
@click.option("--client", required=True, help="Client slug (will be created if missing)")
@click.option("--url", required=True, help="Brand homepage URL")
@click.option("--max-products", default=3, type=int)
@click.option("--max-personas", default=3, type=int)
@click.option("--skip", multiple=True,
              type=click.Choice(["research", "personas", "product-deep-dive", "offers", "strategy-matrix"]),
              help="Stage(s) to skip (can be repeated)")
@click.pass_context
def onboard(ctx, client: str, url: str, max_products: int, max_personas: int, skip: tuple):
    """Run the full onboarding pipeline (stages 1-5) end-to-end.

    Sequence: research → product-deep-dive → personas → offers → strategy-matrix.
    Each stage builds on the previous. Use --skip to omit any stage that's
    already done or not needed.

    All stages run with --auto where applicable. Use the individual commands
    if you want interactive review.
    """
    skipped = set(skip)

    def banner(num: int, name: str):
        console.print()
        console.print(f"[bold magenta]{'═' * 60}[/bold magenta]")
        console.print(f"[bold magenta]STAGE {num} — {name.upper()}[/bold magenta]")
        console.print(f"[bold magenta]{'═' * 60}[/bold magenta]")

    if "research" in skipped:
        console.print("[yellow]Skipping research[/yellow]")
    else:
        banner(1, "Research")
        ctx.invoke(research, client=client, url=url, max_products=max_products, auto=True)

    if "product-deep-dive" in skipped:
        console.print("[yellow]Skipping product-deep-dive[/yellow]")
    else:
        banner(4, "Product Deep-Dive")
        ctx.invoke(product_deep_dive, client=client, product=None)

    if "personas" in skipped:
        console.print("[yellow]Skipping personas[/yellow]")
    else:
        banner(2, "Personas")
        ctx.invoke(personas, client=client, max_personas=max_personas)

    if "offers" in skipped:
        console.print("[yellow]Skipping offers[/yellow]")
    else:
        banner(3, "Offers")
        ctx.invoke(offers, client=client, url=url)

    if "strategy-matrix" in skipped:
        console.print("[yellow]Skipping strategy-matrix[/yellow]")
    else:
        banner(5, "Strategy Matrix")
        ctx.invoke(strategy_matrix, client=client, max_products=max_products)

    console.print()
    console.print(f"[bold green]✓ Onboarding complete for '{client}'[/bold green]")
    console.print()
    console.print("[bold]Files now under clients/{}/:[/bold]".format(client))
    console.print("  - brand.yaml, brand-context.md")
    console.print("  - avatar.yaml + avatars/<id>.yaml × N")
    console.print("  - products/<id>.yaml × N (enriched)")
    console.print("  - offers.yaml")
    console.print("  - strategy-matrix.md, strategy-matrix.yaml")
    console.print()
    console.print("[bold]Next:[/bold]")
    console.print(
        f"  1. adc mine-voc --client {client} --category <category>  "
        "[dim](optional but recommended)[/dim]"
    )
    console.print(
        f"  2. adc profile-psychology --client {client}  "
        "[dim](diagnose buyer heuristics + pairings)[/dim]"
    )
    console.print(
        f"  3. adc brief --client {client} --product <id> --angles 6"
    )


# ─── Product Deep-Dive (Stage 4) ────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--product", default=None,
              help="Specific product slug to enrich (omit to enrich all)")
def product_deep_dive(client: str, product: str | None):
    """Fetch product detail pages and enrich product YAMLs with benefits + reviews.

    For each product (or one specific product if --product given), fetches
    its detail page and runs an LLM extraction using motion/review-audit +
    coreyhaines/customer-research as system context. Pulls functional/
    emotional/social benefits, unique mechanism, real price, objections,
    review quotes, and customer language verbatim quotes.

    Updates clients/<slug>/products/*.yaml in place — preserves existing
    fields, fills in empty ones, appends new lists with dedup.
    """
    from models.loader import (
        list_products as _list_products,
        load_brand,
        load_product,
    )
    from strategy.product_dive import deep_dive_products

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    brand = load_brand(client)

    if product:
        try:
            products = [load_product(client, product)]
        except Exception as e:
            console.print(f"[red]Failed to load product '{product}': {e}[/red]")
            raise SystemExit(1)
    else:
        products = []
        for slug in _list_products(client):
            if slug.startswith("example"):
                continue
            try:
                products.append(load_product(client, slug))
            except Exception:
                continue

    if not products:
        console.print(f"[yellow]No products to deep-dive for '{client}'.[/yellow]")
        raise SystemExit(0)

    products_with_url = [p for p in products if p.url]
    products_without_url = [p for p in products if not p.url]

    console.print(
        f"\n[bold cyan]Deep-diving {len(products_with_url)} product page(s) for {brand.name}[/bold cyan]"
    )
    if products_without_url:
        console.print(
            f"[yellow]Skipping {len(products_without_url)} product(s) without URL: "
            f"{', '.join(p.name for p in products_without_url)}[/yellow]"
        )

    with console.status("Fetching product pages + extracting with Sonnet 4.6..."):
        summary = deep_dive_products(client, brand, products_with_url)

    table = Table(title="Product enrichment results")
    table.add_column("Product", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Price", style="yellow")
    table.add_column("Benefits", style="dim")
    table.add_column("Quotes", style="dim")
    table.add_column("Reviews API", style="magenta")
    table.add_column("Confidence", style="dim")
    for name, info in summary.items():
        table.add_row(
            name[:40],
            info.get("status", "?"),
            str(info.get("price", ""))[:30],
            str(info.get("benefit_count", "")),
            str(info.get("social_proof_count", "")),
            f"{info.get('review_vendor', 'none')} ({info.get('reviews_fetched', 0)})",
            str(info.get("confidence", "")),
        )
    console.print(table)


# ─── Offers (Stage 3) ───────────────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--url", default=None,
              help="Brand homepage URL — defaults to brand context if available")
def offers(client: str, url: str | None):
    """Extract existing offers + generate suggested offers for a client.

    Crawls FAQ, shipping/returns policies, subscription pages on the brand's
    site for offers already running. Then runs offer engineering principles
    (value equation, offer stack, premium positioning) over the brand context
    to suggest new offers tailored to the brand.

    Output: clients/<slug>/offers.yaml
    """
    from models.loader import (
        list_products as _list_products,
        load_avatar,
        load_brand,
        load_product,
    )
    from strategy.offers import build_offers, fetch_offer_pages, save_offers
    from strategy.researcher import fetch_pages

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    brand = load_brand(client)
    avatar = load_avatar(client)
    avatars = [avatar] if avatar else []

    # Pull additional personas if Stage 2 has run
    avatars_dir = client_dir / "avatars"
    if avatars_dir.exists():
        from models.avatar import CustomerAvatar
        for f in sorted(avatars_dir.glob("*.yaml")):
            if f.name.startswith("_"):
                continue
            try:
                with open(f, encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                avatars.append(CustomerAvatar(**data))
            except Exception:
                continue

    product_slugs = [s for s in _list_products(client) if not s.startswith("example")]
    products = []
    for slug in product_slugs[:5]:
        try:
            products.append(load_product(client, slug))
        except Exception:
            continue

    if not url:
        url = _infer_url_from_products(products)
    if not url:
        console.print(
            "[red]No URL provided and couldn't infer one from products. "
            "Pass --url https://yourbrand.com[/red]"
        )
        raise SystemExit(1)

    brand_context_md = ""
    context_path = client_dir / "brand-context.md"
    if context_path.exists():
        brand_context_md = context_path.read_text(encoding="utf-8")

    homepage_html = ""
    with console.status(f"Fetching homepage + offer pages from {url}..."):
        homepage_pages = fetch_pages(url, paths=["/"])
        if homepage_pages:
            homepage_html = next(iter(homepage_pages.values()))
        offer_pages = fetch_offer_pages(url)

    console.print(
        f"[green]Fetched {len(offer_pages)} offer-bearing pages[/green]"
        + (" + homepage" if homepage_html else "")
    )

    console.print(
        f"\n[bold cyan]Extracting + generating offers for {brand.name}[/bold cyan]"
    )

    with console.status("Extracting existing + generating suggested offers (Sonnet 4.6)..."):
        result = build_offers(
            brand=brand,
            avatars=avatars,
            products=products,
            offer_pages=offer_pages,
            homepage_html=homepage_html,
            brand_context_md=brand_context_md,
        )

    out_path = save_offers(client, result)
    console.print(f"\n[green]Wrote {out_path}[/green]\n")

    if result.existing_offers:
        table = Table(title=f"Existing offers ({len(result.existing_offers)})")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Where", style="dim")
        for o in result.existing_offers:
            table.add_row(
                str(o.get("name", ""))[:50],
                str(o.get("type", "")),
                str(o.get("where_found", ""))[:40],
            )
        console.print(table)

    if result.suggested_offers:
        table = Table(title=f"Suggested offers ({len(result.suggested_offers)})")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Persona", style="green")
        table.add_column("Lift", style="dim")
        for o in result.suggested_offers:
            table.add_row(
                str(o.get("name", ""))[:50],
                str(o.get("type", "")),
                str(o.get("target_persona", "")),
                str(o.get("estimated_lift", "")),
            )
        console.print(table)

    notes = result.notes or {}
    if notes.get("highest_priority_test"):
        console.print(
            f"\n[bold]Highest priority test:[/bold] {notes['highest_priority_test']}"
        )


def _infer_url_from_products(products: list) -> str | None:
    """Extract a brand URL from product page URLs if available."""
    for p in products:
        if p.url and p.url.startswith("http"):
            from urllib.parse import urlparse
            parsed = urlparse(p.url)
            return f"{parsed.scheme}://{parsed.netloc}"
    return None


# ─── Strategy Matrix (Stage 5) ──────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--max-products", default=3, type=int, help="How many products to include in context")
def strategy_matrix(client: str, max_products: int):
    """Generate a Schwartz × persona strategy matrix for a client.

    Reads brand.yaml, avatar.yaml, brand-context.md, and product YAMLs.
    Produces strategy-matrix.md (human-readable) and strategy-matrix.yaml
    (structured) under clients/<slug>/.

    Each matrix cell maps one persona × one awareness stage to specific
    messaging guidance: angle, hook style, example hook, framework,
    creative mechanic, proof to surface, CTA, funnel placement.
    """
    from models.loader import (
        list_products as _list_products,
        load_avatar,
        load_brand,
        load_product,
    )
    from strategy.matrix import build_strategy_matrix, save_matrix

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    brand = load_brand(client)
    avatar = load_avatar(client)
    if not avatar:
        console.print(f"[red]No avatar found for '{client}'. Run `adc research` first.[/red]")
        raise SystemExit(1)

    product_slugs = [s for s in _list_products(client) if not s.startswith("example")]
    products = []
    for slug in product_slugs[:max_products]:
        try:
            products.append(load_product(client, slug))
        except Exception as e:
            console.print(f"[yellow]Skipping product {slug}: {e}[/yellow]")

    brand_context_md = ""
    context_path = client_dir / "brand-context.md"
    if context_path.exists():
        brand_context_md = context_path.read_text(encoding="utf-8")

    avatars = [avatar]

    console.print(
        f"\n[bold cyan]Building strategy matrix[/bold cyan] — "
        f"{len(avatars)} persona × 5 awareness stages = {len(avatars) * 5} cells"
    )
    console.print(f"  brand: {brand.name}")
    console.print(f"  products in scope: {', '.join(p.name for p in products) or '(none)'}")
    console.print()

    with console.status("Compiling matrix with Claude Sonnet 4.6 (motion/creative-strategy-engine + product-marketing-context)..."):
        result = build_strategy_matrix(
            brand=brand,
            avatars=avatars,
            products=products,
            brand_context_md=brand_context_md,
        )

    md_path, yaml_path = save_matrix(client, result)
    cell_count = sum(len(p.get("cells", [])) for p in result.data.get("matrix", []))

    console.print(f"[green]Wrote {md_path}[/green]")
    console.print(f"[green]Wrote {yaml_path}[/green]")
    console.print(f"[dim]{cell_count} matrix cells generated[/dim]")
    console.print()

    obs = result.data.get("cross_stage_observations") or {}
    if obs.get("highest_leverage_stages"):
        console.print(
            f"[bold]Highest leverage stages:[/bold] "
            f"{', '.join(obs['highest_leverage_stages'])}"
        )
    if obs.get("ad_distribution_recommendation"):
        console.print(f"[bold]Recommended distribution:[/bold] {obs['ad_distribution_recommendation']}")


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
        discover_visual_identity_images,
        extract_visual_identity,
        fetch_pages,
        fetch_shopify_bestsellers,
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

    # Visual identity capture (multi-image, Gemini 2.5 Pro via OpenRouter,
    # falls back to Claude vision if OPENROUTER_API_KEY not set).
    # Brand colors are NOT extracted — clients fill those in manually.
    visual_identity = None
    vi_images = discover_visual_identity_images(homepage_html, url, bestsellers=bestsellers)
    if vi_images:
        console.print(f"\n[cyan]Visual identity capture — analyzing {len(vi_images)} image(s):[/cyan]")
        for img in vi_images:
            console.print(f"  - {img[:100]}")
        with console.status("Running multi-image vision (Gemini 2.5 Pro / Claude fallback)..."):
            visual_identity = extract_visual_identity(vi_images)
        if visual_identity:
            console.print(f"[green]Visual identity captured.[/green] Aesthetic: "
                          f"{visual_identity.get('aesthetic', '')[:100]}")
        else:
            console.print("[yellow]Visual identity extraction returned nothing — brand-context will be text-only.[/yellow]")
    else:
        console.print("[yellow]No images found for visual identity analysis.[/yellow]")

    # ─── PHASE 3: BUILD BRAND CONTEXT ─────────────────────────────────────
    console.print("\n[bold cyan]PHASE 3 — BUILDING BRAND CONTEXT[/bold cyan]")
    with console.status("Compiling brand-context.md + structured data with Claude Sonnet 4.6..."):
        result = run_brand_intake(
            brand_name=brand_name,
            brand_url=url,
            seed_answers=seed_answers,
            pages=pages,
            bestsellers=bestsellers,
            visual_identity=visual_identity,
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

    # Visual identity gets a dedicated display (it's the most actionable
    # output for downstream creative generation).
    brand = data.get("brand", {})
    vi = brand.get("visual_identity") or {}
    if vi:
        console.print("[bold magenta]VISUAL IDENTITY (from multi-image vision):[/bold magenta]")
        for key in ("aesthetic", "design_language", "photography_style", "typography_feel",
                    "mascot_or_character", "color_mood", "mood"):
            val = vi.get(key)
            if val:
                console.print(f"  [cyan]{key}[/cyan]: {val}")
        for key in ("visual_references", "notable_visual_signatures"):
            items = vi.get(key) or []
            if items:
                console.print(f"  [cyan]{key}[/cyan]:")
                for item in items[:5]:
                    console.print(f"    - {item}")
        console.print()
        console.print("  [dim]Brand colors are NOT auto-extracted — fill them in manually in brand.yaml.[/dim]\n")

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
            "primary": "",  # Fill in manually — research no longer extracts these
            "secondary": "",
            "background": "#FFFFFF",
        },
        "typography": {
            "heading": _flatten(brand_data.get("typography", {}).get("heading", {"value": ""})),
            "body": _flatten(brand_data.get("typography", {}).get("body", {"value": ""})),
        },
        "visual_identity": brand_data.get("visual_identity") or {},
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
@click.option(
    "--avatar",
    default=None,
    help="Specific avatar to use (e.g. 'primary'). Loads from clients/<slug>/avatars/<name>.yaml. "
    "Omit to fall back to legacy clients/<slug>/avatar.yaml.",
)
@click.option(
    "--ignore-psychology",
    is_flag=True,
    default=False,
    help="Skip the avatar's psychology_profile guardrails (filter + prompt block). "
    "Useful for before/after comparison.",
)
def brief(
    client: str,
    product: str,
    angles: int,
    platform: str,
    avatar: str | None,
    ignore_psychology: bool,
):
    """Generate creative briefs with messaging angles for a product."""
    import yaml

    from models.avatar import CustomerAvatar
    from models.loader import (
        load_brand,
        load_product,
        load_avatar as _load_legacy_avatar,
        load_winning_patterns,
        save_brief,
    )
    from strategy.brief_generator import generate_briefs

    with console.status("Loading client data..."):
        brand = load_brand(client)
        prod = load_product(client, product)
        patterns = load_winning_patterns(client)

        # Resolve avatar: explicit --avatar wins, then avatars/primary.yaml,
        # then legacy avatar.yaml.
        avatar_obj: CustomerAvatar | None = None
        avatar_source = ""
        if avatar:
            path = Path("clients") / client / "avatars" / f"{avatar}.yaml"
            if not path.exists():
                console.print(f"[red]Avatar '{avatar}' not found at {path}[/red]")
                raise SystemExit(1)
            with open(path, encoding="utf-8") as fh:
                avatar_obj = CustomerAvatar(**yaml.safe_load(fh))
            avatar_source = str(path)
        else:
            primary = Path("clients") / client / "avatars" / "primary.yaml"
            if primary.exists():
                with open(primary, encoding="utf-8") as fh:
                    avatar_obj = CustomerAvatar(**yaml.safe_load(fh))
                avatar_source = str(primary)
            else:
                avatar_obj = _load_legacy_avatar(client)
                avatar_source = f"clients/{client}/avatar.yaml (legacy)"

    if not avatar_obj:
        console.print(
            f"[yellow]No avatar found for '{client}'. "
            f"Run 'adc mine-voc' or create clients/{client}/avatar.yaml[/yellow]"
        )
        raise SystemExit(1)

    console.print(f"[dim]Avatar source: {avatar_source}[/dim]")
    use_profile = not ignore_psychology
    if avatar_obj.psychology_profile and use_profile:
        n_dom = len(avatar_obj.psychology_profile.dominant_heuristics)
        n_pairings = len(avatar_obj.psychology_profile.recommended_prompt_pairings)
        console.print(
            f"[dim]Psychology profile applied: {n_dom} dominant heuristics, "
            f"{n_pairings} recommended pairings.[/dim]"
        )
    elif avatar_obj.psychology_profile and ignore_psychology:
        console.print(
            "[yellow]Profile present but --ignore-psychology was set; skipping guardrails.[/yellow]"
        )
    else:
        console.print(
            "[yellow]No psychology profile on this avatar. "
            "Run `adc profile-psychology` first for heuristic-aware angle generation.[/yellow]"
        )

    with console.status(f"Generating {angles} creative briefs..."):
        try:
            briefs = generate_briefs(
                client_slug=client,
                product=prod,
                brand=brand,
                avatar=avatar_obj,
                count=angles,
                platform=platform,
                winning_patterns=patterns,
                use_profile=use_profile,
            )
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1)

    table = Table(title=f"Creative Briefs - {brand.name} / {prod.name}")
    table.add_column("#", style="dim")
    table.add_column("Hook", style="cyan", max_width=50)
    table.add_column("Angle", style="green", max_width=30)
    table.add_column("Framework", style="yellow")
    table.add_column("Brief ID", style="dim")

    for i, b in enumerate(briefs, 1):
        save_brief(client, b)
        table.add_row(str(i), b.hook, b.angle, b.framework.value, b.brief_id)

    console.print(table)
    console.print(f"\n[green]Saved {len(briefs)} briefs to clients/{client}/briefs/[/green]")
    console.print(f"Generate images: adc generate --client {client} --brief <brief-id> --style <style>")


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


# ─── Drive Asset Ingestion (Phase A) ─────────────────────────────────────────


@cli.command(name="enrich-brand")
@click.option("--client", required=True, help="Client slug")
@click.option(
    "--apply/--dry-run",
    default=False,
    help="--dry-run (default) prints the proposed diff only; --apply writes brand.yaml.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Bypass the Drive-modifiedTime cache and re-run vision on every asset.",
)
@click.option(
    "--no-backup",
    is_flag=True,
    default=False,
    help="Skip writing a .yaml.bak before overwriting brand.yaml.",
)
def enrich_brand(client: str, apply: bool, force: bool, no_backup: bool):
    """Pull `brand/` assets from the client's Drive folder, vision-analyze, merge into brand.yaml.

    Reads `drive_folder_id` from brand.yaml, then ingests the `brand/` subfolder
    of that Drive folder (images via Gemini multi-image vision, PDFs via
    pdftotext + page-image vision). Defaults to dry-run with a diff preview;
    pass `--apply` to commit changes.
    """
    from strategy.brand_enricher import enrich_brand_from_drive

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    backup = not no_backup
    with console.status(f"Pulling brand assets from Drive for '{client}'..."):
        try:
            result = enrich_brand_from_drive(
                client_slug=client,
                apply=apply,
                force=force,
                backup=backup,
            )
        except (ValueError, EnvironmentError, FileNotFoundError) as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1)

    _render_enrichment_summary(client, result, apply=apply)


def _render_enrichment_summary(client: str, result, *, apply: bool):
    """Print the proposed diff and run statistics."""
    console.print()
    console.print(
        f"[dim]images analyzed: {result.images_analyzed}  "
        f"pdfs analyzed: {result.pdfs_analyzed}  "
        f"cache hits: {result.cache_hits}  "
        f"skipped: {len(result.skipped)}[/dim]"
    )

    for filename, reason in result.skipped:
        console.print(f"[yellow]  skipped {filename}: {reason}[/yellow]")

    if not result.changes:
        console.print("[green]No proposed changes — brand.yaml already reflects Drive assets.[/green]")
        return

    console.print(f"\n[bold]Proposed {len(result.changes)} change(s) to brand.yaml:[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Field", style="cyan", max_width=32)
    table.add_column("Before", style="dim", max_width=50)
    table.add_column("After", style="green", max_width=50)
    for change in result.changes:
        before_str = _format_field_value(change.before)
        after_str = _format_field_value(change.after)
        table.add_row(change.path, before_str, after_str)
    console.print(table)

    if apply:
        console.print(
            f"\n[bold green]Applied. Wrote clients/{client}/brand.yaml "
            f"(backup at brand.yaml.bak).[/bold green]"
        )
    else:
        console.print(
            f"\n[yellow]Dry run — no changes written.[/yellow]\n"
            f"Re-run with --apply to commit: "
            f"[bold]adc enrich-brand --client {client} --apply[/bold]"
        )


def _format_field_value(value) -> str:
    """Format a brand-field value for table display."""
    if isinstance(value, list):
        if not value:
            return "[]"
        joined = ", ".join(str(v) for v in value[:3])
        if len(value) > 3:
            joined += f", +{len(value) - 3} more"
        return joined
    if value == "":
        return "(empty)"
    return str(value)[:200]


@cli.command(name="analyze-references")
@click.option("--client", required=True, help="Client slug")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Bypass cache and re-run vision on every reference ad.",
)
def analyze_references(client: str, force: bool):
    """Pull `reference-ads/` from Drive, vision-analyze each, cache per-file YAMLs.

    Static images go straight to vision. Videos have a representative frame
    extracted via ffmpeg, then vision runs on that frame. Output lives at
    clients/<slug>/reference_ads/analyses/, with a _summary.yaml index.
    """
    from strategy.reference_ads import analyze_references_from_drive

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    with console.status(f"Analyzing reference ads for '{client}' via Sonnet/Gemini..."):
        try:
            result = analyze_references_from_drive(client_slug=client, force=force)
        except (ValueError, EnvironmentError, FileNotFoundError) as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1)

    _render_references_summary(client, result)


def _render_references_summary(client: str, result):
    """Print compact analyzed-ad table."""
    console.print()
    console.print(
        f"[dim]analyzed: {len(result.analyses)}  "
        f"new: {result.new_analyses}  "
        f"cache hits: {result.cache_hits}  "
        f"skipped: {len(result.skipped)}[/dim]"
    )
    for name, reason in result.skipped:
        console.print(f"[yellow]  skipped {name}: {reason}[/yellow]")

    if not result.analyses:
        return

    table = Table(title="Reference ad analyses", show_header=True, header_style="bold")
    table.add_column("File", style="cyan", max_width=28)
    table.add_column("Fmt", style="dim", max_width=6)
    table.add_column("Hook type", style="green", max_width=18)
    table.add_column("Visual format", style="yellow", max_width=16)
    table.add_column("Mechanic", style="magenta", max_width=28)
    table.add_column("Mood", style="dim", max_width=24)

    for a in result.analyses:
        p = a.payload
        fmt = "video" if a.is_video_frame else "img"
        mood = ", ".join((p.get("mood") or [])[:3])
        table.add_row(
            a.filename[:26],
            fmt,
            (p.get("hook_type") or "")[:18],
            (p.get("visual_format") or "")[:16],
            (p.get("creative_mechanic") or "")[:28],
            mood[:24],
        )
    console.print(table)
    console.print(
        f"\n[bold green]Wrote analyses to clients/{client}/reference_ads/analyses/[/bold green]"
    )


# ─── Psychology Profiling (Stage 1.5) ────────────────────────────────────────


@cli.command(name="profile-psychology")
@click.option("--client", required=True, help="Client slug")
@click.option(
    "--avatar",
    default=None,
    help="Specific avatar to profile (e.g. 'primary'). Omit to profile every avatar.",
)
@click.option(
    "--no-backup",
    is_flag=True,
    default=False,
    help="Skip writing the .yaml.bak sibling before overwriting.",
)
def profile_psychology(client: str, avatar: str | None, no_backup: bool):
    """Diagnose buyer psychology for an avatar — heuristics, valence/intensity, pairings.

    Reads the avatar + brand context + (optional) extracted VOC, runs the
    psychology-profiling skill via Sonnet 4.6, and writes a `psychology_profile`
    block into the avatar yaml in place. Downstream angle generation reads this
    to choose which psychological levers to activate.

    Run AFTER `adc mine-voc` for highest-confidence output. Without VOC the
    profiler will still run but flag confidence accordingly.
    """
    from strategy.psychology_profiler import (
        profile_all_avatars,
        profile_avatar_file,
    )

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    backup = not no_backup

    if avatar:
        avatar_path = client_dir / "avatars" / f"{avatar}.yaml"
        if not avatar_path.exists():
            legacy = client_dir / "avatar.yaml"
            if avatar in ("avatar", "default") and legacy.exists():
                avatar_path = legacy
            else:
                console.print(f"[red]Avatar '{avatar}' not found at {avatar_path}[/red]")
                raise SystemExit(1)

        with console.status(f"Profiling psychology for {avatar} with Sonnet 4.6..."):
            try:
                profile = profile_avatar_file(client, avatar_path, backup=backup)
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                raise SystemExit(1)

        _render_psychology_summary({avatar: profile})
    else:
        with console.status(f"Profiling all avatars for '{client}' with Sonnet 4.6..."):
            try:
                profiles = profile_all_avatars(client, backup=backup)
            except (FileNotFoundError, ValueError) as e:
                console.print(f"[red]{e}[/red]")
                raise SystemExit(1)
        _render_psychology_summary(profiles)

    console.print()
    console.print(
        f"[bold green]Psychology profiles written to clients/{client}/avatars/[/bold green]"
    )
    if backup:
        console.print(
            "[dim]Backups at <avatar>.yaml.bak - delete if you're happy with results.[/dim]"
        )
    console.print(
        "\n[bold]Next:[/bold] briefs and angle generation will read "
        "`psychology_profile` from each avatar automatically (wiring coming next)."
    )


def _render_psychology_summary(profiles):
    """Print a compact table of each avatar's profile.

    Rich treats `[...]` as markup, so square brackets in literal output must be
    escaped with a backslash. We use parens for quadrant/confidence labels to
    avoid the visual noise of escape sequences.
    """
    for name, profile in profiles.items():
        console.print(f"\n[bold cyan]{name}[/bold cyan]")

        if profile.emotional_position:
            ep = profile.emotional_position
            console.print(
                f"  [dim]Position:[/dim] primary ({ep.primary.valence}/{ep.primary.intensity}), "
                f"secondary ({ep.secondary.valence}/{ep.secondary.intensity})"
            )

        if profile.dominant_heuristics:
            console.print("  [dim]Dominant:[/dim]")
            for h in profile.dominant_heuristics:
                console.print(f"    ({h.confidence:>6}) {h.heuristic}")

        if profile.weak_heuristics:
            console.print("  [dim]Avoid (weak):[/dim]")
            for h in profile.weak_heuristics:
                console.print(f"    {h.heuristic}")

        if profile.recommended_prompt_pairings:
            console.print("  [dim]Recommended pairings:[/dim]")
            for p in profile.recommended_prompt_pairings:
                console.print(f"    + {p.pairing}")

        if profile.avoid_pairings:
            console.print("  [dim]Avoid pairings:[/dim]")
            for p in profile.avoid_pairings:
                console.print(f"    - {p.pairing}")


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
