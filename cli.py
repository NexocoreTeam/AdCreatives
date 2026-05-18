"""AdCreatives CLI — AI-powered ad creative generation for Meta and TikTok."""

from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Force UTF-8 on stdout/stderr before Rich initializes, so glyphs like ✓ render
# safely on Windows consoles that default to cp1252. No-op on POSIX.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def _bootstrap_env_from_dotenv() -> None:
    """Populate os.environ from .env in the project root if keys are missing.

    Runs once at CLI startup so subprocess invocations (e.g. from the
    Streamlit dashboard) inherit API keys even when the parent process was
    launched without sourcing .env. Existing env vars are NOT overridden by
    default — shell-set keys win. No-op if .env is absent.

    Important on Windows: when a shell-set var is EMPTY (`KEY=`), the empty
    value would otherwise win over .env. We treat empty-string env vars as
    absent so .env values fill them in.
    """
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("﻿")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Override empty-string env vars too (common on Windows where the
        # shell sets the name but leaves the value empty).
        existing = os.environ.get(key, "")
        if key and not existing:
            os.environ[key] = value


_bootstrap_env_from_dotenv()
# Belt-and-suspenders: also let python-dotenv look for .env in any parent
# directory (handles worktrees where the .env is at the repo root).
load_dotenv(override=False)

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
@click.option("--max-personas", default=5, type=int,
              help="Maximum number of personas to generate (1-6). Default 5 — "
              "use --max-personas 3 if you want a tighter set.")
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
            client_slug=client,
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


# ─── Persona add / delete (single-persona management) ───────────────────────


@cli.command(name="add-persona")
@click.option("--client", required=True, help="Client slug")
def add_persona_cmd(client: str):
    """Generate ONE new persona that fills a gap in the existing set.

    Loads existing avatars from clients/<slug>/avatars/, summarizes them for
    the LLM, then asks for a single new persona that differs on pains,
    triggers, language, or awareness level. Saves as a new avatar file and
    appends to _index.yaml. Enforces a hard cap of 6 personas per client.
    """
    from models.loader import load_brand, load_all_avatars
    from strategy.personas import (
        MAX_PERSONAS,
        add_persona,
        build_one_persona,
    )

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    existing = load_all_avatars(client)
    if len(existing) >= MAX_PERSONAS:
        names = ", ".join(a.name or "?" for a in existing)
        console.print(
            f"[red]At persona cap ({len(existing)}/{MAX_PERSONAS}). "
            f"Delete one first with `adc delete-persona --client {client} --avatar <slug>`.[/red]"
        )
        console.print(f"[dim]Current personas: {names}[/dim]")
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
        f"\n[bold cyan]Adding one persona for {brand.name}[/bold cyan] "
        f"({len(existing)} → {len(existing) + 1} of {MAX_PERSONAS})"
    )
    with console.status("Generating a distinct new persona with Claude Sonnet 4.6..."):
        try:
            persona = build_one_persona(
                brand=brand,
                brand_context_md=brand_context_md,
                existing_avatars=existing,
                client_slug=client,
            )
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1)

    avatar_path, index_path = add_persona(client, persona)
    console.print(f"\n[green]Created persona:[/green] {persona.get('name', '?')}")
    console.print(f"  - File:  {avatar_path}")
    console.print(f"  - Slug:  {persona['id']}")
    console.print(f"  - Index: {index_path}")
    console.print(
        f"\n[green]Next:[/green] adc profile-psychology --client {client} --avatar {persona['id']}"
    )

    from strategy.cost_tracker import log_cost
    log_cost(client, "adc add-persona", note=f"added {persona['id']}")


@cli.command(name="delete-persona")
@click.option("--client", required=True, help="Client slug")
@click.option("--avatar", "avatar_slug", required=True,
              help="Avatar slug to delete (e.g. 'tertiary' or 'switcher-stacey'). "
              "Matches the filename stem in clients/<slug>/avatars/.")
@click.option("--yes", is_flag=True, default=False,
              help="Skip the confirmation prompt.")
def delete_persona_cmd(client: str, avatar_slug: str, yes: bool):
    """Remove a persona and prune it from the _index.yaml roster.

    Existing briefs that reference this persona by name are NOT touched —
    they keep their persona text baked in. Only the avatar file and the
    index entry are removed.
    """
    from strategy.personas import delete_persona

    avatar_path = Path("clients") / client / "avatars" / f"{avatar_slug}.yaml"
    if not avatar_path.exists():
        console.print(f"[red]Avatar not found: {avatar_path}[/red]")
        raise SystemExit(1)

    if not yes:
        if not click.confirm(
            f"Delete persona '{avatar_slug}' from client '{client}'? "
            f"This removes {avatar_path} permanently."
        ):
            console.print("[yellow]Aborted.[/yellow]")
            return

    ok, removed = delete_persona(client, avatar_slug)
    if not ok:
        console.print(f"[red]Failed to delete: {avatar_path}[/red]")
        raise SystemExit(1)
    console.print(f"[green]Deleted:[/green] {removed}")


# ─── Persona portraits (model library for identity-preserving ad gen) ────────


@cli.command(name="generate-model")
@click.option("--client", required=True, help="Client slug")
@click.option("--avatar", "avatar_slug", default=None,
              help="Avatar slug (e.g. 'primary' or 'burnout-biohacker-brandon'). "
              "Omit to generate portraits for ALL avatars under the client.")
@click.option("--candidates", default=3, type=click.IntRange(1, 6),
              help="How many candidate portraits to generate per persona (default 3).")
@click.option("--force", is_flag=True, default=False,
              help="Regenerate even if candidate portraits already exist.")
def generate_model_cmd(client: str, avatar_slug: str | None, candidates: int, force: bool):
    """Generate canonical headshot portraits for one or all persona(s).

    Each persona gets N candidate headshots saved under
    clients/<slug>/avatars/<persona-slug>/candidate_N.png. After
    generation you'd pick the canonical one (via dashboard, or by
    copying it to <persona-slug>.png manually) and that face is then
    used as an identity reference for every ad targeting the persona.

    Cost: ~$0.25 per persona for 3 candidates (1 Sonnet visual-cues
    call + 3 Nano Banana 2 generate calls).
    """
    from models.avatar import CustomerAvatar
    from models.loader import load_brand
    from strategy.persona_portrait import generate_portraits
    import yaml as _yaml

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    brand = load_brand(client)
    avatars_dir = client_dir / "avatars"

    # Resolve which avatars to process: one or all.
    if avatar_slug:
        targets = [avatars_dir / f"{avatar_slug}.yaml"]
        if not targets[0].exists():
            console.print(f"[red]Avatar not found: {targets[0]}[/red]")
            raise SystemExit(1)
    else:
        targets = sorted(
            p for p in avatars_dir.glob("*.yaml")
            if not p.name.startswith("_") and not p.name.endswith(".bak")
        )
        if not targets:
            console.print(
                f"[red]No avatars under {avatars_dir}. "
                f"Run `adc personas --client {client}` first.[/red]"
            )
            raise SystemExit(1)

    console.print(
        f"\n[bold cyan]Generating portraits[/bold cyan] for "
        f"[green]{len(targets)}[/green] persona(s) "
        f"({candidates} candidate(s) each)\n"
    )

    table = Table(title="Persona portrait generation")
    table.add_column("Persona", style="cyan", max_width=30)
    table.add_column("Slug", style="dim")
    table.add_column("Status", style="green")
    table.add_column("Candidates dir", style="dim")

    for path in targets:
        slug = path.stem
        with open(path, encoding="utf-8") as fh:
            avatar = CustomerAvatar(**_yaml.safe_load(fh))

        try:
            with console.status(f"Generating {candidates} portrait(s) for {avatar.name}..."):
                result = generate_portraits(
                    avatar=avatar,
                    brand=brand,
                    client_slug=client,
                    avatar_slug=slug,
                    num_candidates=candidates,
                    force=force,
                )
        except FileExistsError as e:
            table.add_row(avatar.name or slug, slug, "[yellow]skipped (already exists)[/yellow]", "")
            continue
        except Exception as e:
            table.add_row(avatar.name or slug, slug, f"[red]error: {str(e)[:60]}[/red]", "")
            continue

        candidates_dir = result["candidate_paths"][0].parent
        table.add_row(
            avatar.name or slug,
            slug,
            f"[green]ok — {len(result['candidate_paths'])} files[/green]",
            str(candidates_dir.relative_to(client_dir.parent.parent)),
        )

    console.print(table)
    console.print(
        f"\n[green]Next:[/green] inspect candidates and promote one to canonical:\n"
        f"  - View: open the `candidate_N.png` files under "
        f"`clients/{client}/avatars/<persona-slug>/`\n"
        f"  - Promote (manual): copy your chosen candidate to "
        f"`clients/{client}/avatars/<persona-slug>.png`"
    )

    from strategy.cost_tracker import log_cost
    log_cost(
        client,
        "adc generate-model",
        multiplier=len(targets) * candidates,
        note=f"{len(targets)} persona(s) × {candidates} candidate(s)",
    )


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

    # Load the full persona roster from avatars/ when Stage 2 has run.
    # Falls back to the single legacy avatar.yaml if the roster doesn't exist.
    avatars = [avatar]
    avatars_dir = client_dir / "avatars"
    if avatars_dir.exists():
        import yaml as _yaml
        from models.avatar import CustomerAvatar
        roster: list = []
        for f in sorted(avatars_dir.glob("*.yaml")):
            if f.name.startswith("_") or f.name.endswith(".bak"):
                continue
            try:
                with open(f, encoding="utf-8") as fh:
                    data = _yaml.safe_load(fh)
                roster.append(CustomerAvatar(**data))
            except Exception:
                continue
        if roster:
            avatars = roster

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
            client_slug=client,
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
        discover_product_urls_smart,
        discover_visual_identity_images,
        extract_visual_identity,
        fetch_homepage_html,
        fetch_pages,
        fetch_product_pages,
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

    # Fetch the homepage as RAW HTML (Firecrawl rendered or httpx) so parsers
    # downstream get <head>/<meta>/<script> — Markdown strips those.
    homepage_html = fetch_homepage_html(url)
    if not homepage_html:
        # Last-resort: best-effort guess from whatever fetch_pages collected
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

    # ── Product page (PDP) discovery + fetch ──────────────────────────────
    # Pricing, ingredients, and detailed product copy only live on PDPs —
    # the candidate-path list never visits them. Use Firecrawl /map to
    # discover PDPs, prefer those that appeared as bestsellers, and merge
    # the top 3 into the pages dict before brand-intake compilation.
    pdp_urls_from_map = discover_product_urls_smart(url, limit=12)
    bestseller_pdp_urls: list[str] = []
    for c in bestsellers:
        if c.url and "/products/" in c.url and "menu_drawer" not in c.url:
            if c.url not in bestseller_pdp_urls:
                bestseller_pdp_urls.append(c.url)

    # Ranked PDP list: bestsellers first (preserve their order), then any
    # remaining /map-discovered PDPs not in that set.
    pdp_urls: list[str] = []
    seen: set[str] = set()
    for u in bestseller_pdp_urls + pdp_urls_from_map:
        if u not in seen:
            seen.add(u)
            pdp_urls.append(u)
    pdp_urls = pdp_urls[:3]

    if pdp_urls:
        console.print(f"\n[cyan]Fetching {len(pdp_urls)} product page(s) for pricing + ingredients:[/cyan]")
        for u in pdp_urls:
            console.print(f"  - {u}")
        pdp_pages = fetch_product_pages(pdp_urls)
        if pdp_pages:
            console.print(f"[green]Captured {len(pdp_pages)} PDP(s).[/green]")
            pages.update(pdp_pages)
        else:
            console.print("[yellow]PDP fetch returned nothing.[/yellow]")

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
    "avatar_name",
    default=None,
    help="Specific avatar to use (e.g. 'primary'). Loads from "
    "clients/<slug>/avatars/<name>.yaml. Omit to use primary.yaml then fall "
    "back to legacy clients/<slug>/avatar.yaml.",
)
@click.option(
    "--ignore-psychology",
    is_flag=True,
    default=False,
    help="Skip the avatar's psychology_profile guardrails (filter + prompt block). "
    "Useful for before/after comparison.",
)
@click.option(
    "--no-trending",
    "no_trending",
    is_flag=True,
    default=False,
    help="Skip the trending-format recommender. By default, every brief gets "
    "top-3 trending alternatives attached (from trending_formats.yaml).",
)
def brief(
    client: str,
    product: str,
    angles: int,
    platform: str,
    avatar_name: str | None,
    ignore_psychology: bool,
    no_trending: bool,
):
    """Generate creative briefs with messaging angles for a product.

    Layers automatically applied when present:
      - Psychology profile (if avatar has one) -> filters slots + injects guardrails
      - Competitive gap map (if competitive-gaps.yaml exists) -> biases angles to exploit gaps
    """
    import math
    import yaml as _yaml
    from models.avatar import CustomerAvatar
    from models.loader import (
        load_brand,
        load_product,
        load_avatar as _load_legacy_avatar,
        load_all_avatars,
        load_winning_patterns,
        save_brief,
    )
    from strategy.brief_generator import generate_briefs

    with console.status("Loading client data..."):
        brand = load_brand(client)
        prod = load_product(client, product)
        patterns = load_winning_patterns(client)

        # Resolve avatars:
        #   --avatar X        -> use exactly that one
        #   (no flag)         -> use ALL avatars in clients/<slug>/avatars/,
        #                         distributing the requested brief count across
        #                         them. Falls back to legacy avatar.yaml if no
        #                         avatars/ folder exists.
        avatars: list[CustomerAvatar] = []
        avatar_source = ""
        if avatar_name:
            apath = Path("clients") / client / "avatars" / f"{avatar_name}.yaml"
            if not apath.exists():
                console.print(f"[red]Avatar '{avatar_name}' not found at {apath}[/red]")
                raise SystemExit(1)
            with open(apath, encoding="utf-8") as fh:
                avatars = [CustomerAvatar(**_yaml.safe_load(fh))]
            avatar_source = str(apath)
        else:
            avatars = load_all_avatars(client)
            if avatars:
                names = ", ".join(a.name or "?" for a in avatars)
                avatar_source = f"clients/{client}/avatars/ ({len(avatars)}: {names})"
            else:
                legacy = _load_legacy_avatar(client)
                if legacy:
                    avatars = [legacy]
                    avatar_source = f"clients/{client}/avatar.yaml (legacy)"

    if not avatars:
        console.print(
            f"[yellow]No avatar found for '{client}'. "
            f"Run 'adc mine-voc' or create clients/{client}/avatar.yaml[/yellow]"
        )
        raise SystemExit(1)

    console.print(f"[dim]Avatar source: {avatar_source}[/dim]")
    use_profile = not ignore_psychology

    # Distribute `angles` briefs across avatars as evenly as possible. With
    # 9 angles across 4 avatars: ceil(9/4)=3 per avatar generated, then the
    # combined list is truncated to 9. Extras land on the higher-priority
    # avatars (primary first), which is the order load_all_avatars returns.
    per_avatar = math.ceil(angles / len(avatars))

    briefs: list = []
    for av in avatars:
        if av.psychology_profile and use_profile:
            n_dom = len(av.psychology_profile.dominant_heuristics)
            n_pairings = len(av.psychology_profile.recommended_prompt_pairings)
            console.print(
                f"[dim]  {av.name}: psychology profile applied "
                f"({n_dom} heuristics, {n_pairings} pairings).[/dim]"
            )
        elif av.psychology_profile and ignore_psychology:
            console.print(
                f"[yellow]  {av.name}: profile present but --ignore-psychology was set.[/yellow]"
            )
        else:
            console.print(
                f"[yellow]  {av.name}: no psychology profile. "
                f"Run `adc profile-psychology --client {client} --avatar {av.name}` for heuristic-aware angles.[/yellow]"
            )

        with console.status(f"Generating {per_avatar} brief(s) for {av.name}..."):
            try:
                avatar_briefs = generate_briefs(
                    client_slug=client,
                    product=prod,
                    brand=brand,
                    avatar=av,
                    count=per_avatar,
                    platform=platform,
                    winning_patterns=patterns,
                    use_profile=use_profile,
                    include_trending=not no_trending,
                )
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                raise SystemExit(1)
        briefs.extend(avatar_briefs)

    # Truncate to the requested count so 9 angles across 4 avatars yields
    # exactly 9 briefs, not 12 (4 × ceil(9/4)).
    briefs = briefs[:angles]

    table = Table(title=f"Creative Briefs - {brand.name} / {prod.name}")
    table.add_column("#", style="dim")
    table.add_column("Persona", style="bold magenta", max_width=24)
    table.add_column("Hook", style="cyan", max_width=50)
    table.add_column("Angle", style="green", max_width=30)
    table.add_column("Framework", style="yellow")
    table.add_column("Brief ID", style="dim")

    for i, b in enumerate(briefs, 1):
        save_brief(client, b)
        table.add_row(str(i), b.persona or "—", b.hook, b.angle, b.framework.value, b.brief_id)

    console.print(table)
    console.print(f"\n[green]Saved {len(briefs)} briefs to clients/{client}/briefs/[/green]")
    console.print(f"\n[green]Next:[/green] adc menu --client {client}")

    from strategy.cost_tracker import log_cost
    log_cost(client, "adc brief", note=f"{len(briefs)} briefs across {len(avatars)} avatar(s) for {product}")


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


@cli.command(name="list-templates")
@click.option("--client", required=True, help="Client slug")
@click.option("--category", default=None,
              help="Filter to one category (us-vs-them, testimonial-review, etc.)")
def list_templates(client: str, category: str | None):
    """List extracted templates for a client. Use the template id with
    `adc generate --reference <id>` for single-reference art-directed mode."""
    import yaml as _yaml

    templates_root = Path("clients") / client / "templates"
    if not templates_root.exists():
        console.print(
            f"[yellow]No templates yet for '{client}'. Run "
            f"`adc extract-templates --client {client}` first.[/yellow]"
        )
        raise SystemExit(0)

    rows: list[tuple[str, str, str, str, str]] = []
    for yaml_file in sorted(templates_root.rglob("*.yaml")):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                d = _yaml.safe_load(f) or {}
            tpl = (d.get("template_prompt") or "").strip()
            if len(tpl) < 50:
                continue  # skip empty / broken templates
            cat = d.get("category", "—")
            if category and cat != category:
                continue
            rows.append((
                d.get("id", yaml_file.stem),
                d.get("name", "—")[:30],
                cat,
                ", ".join((d.get("tags") or [])[:4])[:50],
                d.get("source_ad", "—").split("\\")[-1].split("/")[-1][:40],
            ))
        except Exception:
            continue

    if not rows:
        console.print(f"[yellow]No usable templates found for '{client}'"
                      + (f" in category '{category}'" if category else "") + ".[/yellow]")
        raise SystemExit(0)

    table = Table(title=f"Templates — {client}"
                  + (f" / {category}" if category else "")
                  + f" ({len(rows)} usable)")
    table.add_column("Template ID", style="cyan", max_width=50)
    table.add_column("Name", style="green", max_width=30)
    table.add_column("Category", style="yellow", max_width=20)
    table.add_column("Tags", style="dim", max_width=50)
    table.add_column("Source ad", style="dim", max_width=40)
    for r in rows:
        table.add_row(*r)
    console.print(table)
    console.print(
        f"\n[dim]Use any template id with: "
        f"adc generate --client {client} --pick <n> --reference <template-id>[/dim]"
    )


@cli.command(name="extract-templates")
@click.option("--client", required=True, help="Client slug")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Re-extract templates for every ad even if a template YAML already exists.",
)
def extract_templates(client: str, force: bool):
    """Extract Cooper-style prompt templates from the client's reference ads.

    For each ad in clients/<slug>/reference_ads/raw/<category>/, runs vision +
    LLM to produce a structured LibraryPrompt YAML at
    clients/<slug>/templates/<category>/<ad_stem>.yaml. These templates outrank
    Cooper/Nanobana when the prompt engine picks compositional examples for a
    brief.

    Cost: ~$0.02 per ad. Idempotent — re-runs skip ads whose template already
    exists, unless --force.
    """
    from strategy.template_extractor import extract_all_client_templates

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    with console.status(f"Extracting prompt templates for '{client}' via Gemini vision..."):
        try:
            result = extract_all_client_templates(client_slug=client, force=force)
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1)

    console.print(
        f"[green]Templates extracted: {result.new_extractions} new, "
        f"{result.cache_hits} cached, {len(result.skipped)} skipped[/green]"
    )
    if result.skipped:
        for name, reason in result.skipped[:5]:
            console.print(f"  [yellow]skip[/yellow] {name}: {reason}")

    from strategy.cost_tracker import log_cost
    log_cost(client, "adc extract-templates", multiplier=result.new_extractions,
             note=f"{result.new_extractions} templates extracted")


@cli.command(name="analyze-references")
@click.option("--client", required=True, help="Client slug")
@click.option(
    "--local-dir",
    "local_dir",
    default=None,
    help="Path to a LOCAL folder of reference ads (PNG/JPG/WebP/MP4/MOV/WebM). "
    "Bypasses Google Drive entirely — no auth needed. Files are copied to "
    "clients/<slug>/reference_ads/raw/ and analyzed in place.",
)
@click.option(
    "--drive-folder-id",
    "drive_folder_id",
    default=None,
    help="Arbitrary Drive folder ID to ingest. Walks its IMMEDIATE SUBFOLDERS "
    "as style buckets (e.g., editorial/ + ugc/) and preserves that grouping "
    "in clients/<slug>/reference_ads/raw/<style>/. Requires "
    "GOOGLE_APPLICATION_CREDENTIALS + the folder shared with the service "
    "account. Overrides the legacy brand.drive_folder_id / reference-ads "
    "default.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Bypass cache and re-run vision on every reference ad.",
)
def analyze_references(client: str, local_dir: str | None,
                       drive_folder_id: str | None, force: bool):
    """Vision-analyze reference ads.

    Three source modes (in priority order):
      --local-dir <path>         Local folder (no Drive auth needed).
      --drive-folder-id <id>     Arbitrary Drive folder; walks subfolders as styles.
      (default)                  Legacy: brand.drive_folder_id / reference-ads/ subfolder.

    Static images go straight to vision. Videos have a representative frame
    extracted via ffmpeg, then vision runs on that frame. Output lives at
    clients/<slug>/reference_ads/analyses/, with a _summary.yaml index.
    """
    from strategy.reference_ads import (
        analyze_references_from_drive,
        analyze_references_from_drive_folder,
        analyze_references_from_local_dir,
    )

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    if local_dir:
        src_label = f"local folder {local_dir}"
    elif drive_folder_id:
        src_label = f"Drive folder {drive_folder_id} (style-subfolder mode)"
    else:
        src_label = "Drive reference-ads/ (legacy mode)"

    with console.status(f"Analyzing reference ads for '{client}' from {src_label} via Gemini vision..."):
        try:
            if local_dir:
                result = analyze_references_from_local_dir(
                    client_slug=client,
                    local_dir=Path(local_dir),
                    force=force,
                )
                _render_references_summary(client, result)
                from strategy.cost_tracker import log_cost
                log_cost(client, "adc analyze-references", multiplier=result.new_analyses,
                         note=f"{result.new_analyses} new, {result.cache_hits} cached (local-dir)")
                return

            if drive_folder_id:
                result = analyze_references_from_drive_folder(
                    client_slug=client,
                    drive_folder_id=drive_folder_id,
                    force=force,
                )
                _render_references_summary(client, result)
                from strategy.cost_tracker import log_cost
                log_cost(client, "adc analyze-references", multiplier=result.new_analyses,
                         note=f"{result.new_analyses} new, {result.cache_hits} cached (drive-folder)")
                return

            # Fallthrough → Drive legacy path below
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
        f"\n[bold]Next:[/bold] adc brief --client {client} --product <id> --angles 6 "
        "(psychology profile auto-applies)"
    )

    from strategy.cost_tracker import log_cost
    n_profiled = 1 if avatar else len(profiles)
    log_cost(client, "adc profile-psychology", multiplier=n_profiled,
             note=f"{n_profiled} avatar(s) profiled")


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


# ─── Interactive Web Dashboard ──────────────────────────────────────────────


@cli.command()
@click.option("--port", default=8501, type=int, help="Local port (default 8501)")
@click.option("--public", is_flag=True, default=False,
              help="Bind to 0.0.0.0 so other devices on your LAN can reach it. "
              "Default binds to localhost only (safer).")
def dashboard(port: int, public: bool):
    """Launch the interactive web dashboard (Streamlit).

    Opens in your browser at http://localhost:<port>/. Reads the same files
    the `adc status` command reads — no API calls, no data leaves your machine.

    Stop with Ctrl-C.
    """
    import subprocess

    repo_root = Path(__file__).resolve().parent
    app_path = repo_root / "dashboard" / "app.py"
    if not app_path.exists():
        console.print(f"[red]Dashboard app not found at {app_path}[/red]")
        raise SystemExit(1)

    address = "0.0.0.0" if public else "localhost"
    console.print(
        f"[green]Launching dashboard at http://{address}:{port}/[/green]\n"
        f"[dim]Press Ctrl-C to stop.[/dim]\n"
    )
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.port", str(port),
        "--server.address", address,
        "--server.headless", "false",
        "--browser.gatherUsageStats", "false",
    ]
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")


# ─── Client Status Dashboard ────────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option(
    "--save",
    is_flag=True,
    default=False,
    help="Also write the dashboard to clients/<slug>/STATUS.md for sharing.",
)
def status(client: str, save: bool):
    """Dashboard view: what's done for a client, what to run next.

    Pure local-file inspection — free, fast (<1s), no API calls.
    """
    from strategy.status_dashboard import (
        ad_assets_status,
        build_recommendations,
        competitive_research_status,
        strategy_status,
    )

    client_dir = Path("clients") / client
    if not client_dir.exists():
        console.print(f"[red]Client '{client}' not found at {client_dir}[/red]")
        raise SystemExit(1)

    strategy_stages = strategy_status(client)
    competitive_stages = competitive_research_status(client)
    asset_stages = ad_assets_status(client)
    recommendations = build_recommendations(
        client, strategy_stages, competitive_stages, asset_stages
    )

    def _render_section(title: str, stages):
        table = Table(title=title)
        table.add_column(" ", justify="center", style="bold", width=6)
        table.add_column("Stage", style="cyan", min_width=24)
        table.add_column("Details", style="green", max_width=48)
        table.add_column("Age", style="dim", justify="right")
        for s in stages:
            # Use plain words instead of [x]/[ ] — Rich treats square brackets as markup
            check = "[green]OK[/green]" if s.done else "[yellow]--[/yellow]"
            age = ""
            if s.age_days is not None:
                if s.age_days == 0:
                    age = "today"
                elif s.age_days == 1:
                    age = "1 day"
                else:
                    age = f"{s.age_days} days"
            details = s.summary
            if s.notes:
                details += f" -- {'; '.join(s.notes)}"
            table.add_row(check, s.name, details, age)
        console.print(table)

    console.print(f"\n[bold magenta]Status for client: {client}[/bold magenta]\n")
    _render_section("Strategy", strategy_stages)
    _render_section("Competitive Research", competitive_stages)
    _render_section("Ad Assets", asset_stages)

    console.print("\n[bold]Recommended next steps:[/bold]")
    for r in recommendations:
        console.print(f"  -> {r}")
    console.print()

    if save:
        from datetime import datetime as _dt
        md_lines = [
            f"# Status — {client}",
            f"_Generated {_dt.now().strftime('%Y-%m-%d %H:%M')}_",
            "",
        ]

        def _md_section(title: str, stages):
            md_lines.append(f"## {title}\n")
            md_lines.append("| Status | Stage | Details | Age |")
            md_lines.append("|---|---|---|---|")
            for s in stages:
                check = "OK" if s.done else "--"
                age = ""
                if s.age_days is not None:
                    if s.age_days == 0:
                        age = "today"
                    elif s.age_days == 1:
                        age = "1 day"
                    else:
                        age = f"{s.age_days} days"
                details = s.summary
                if s.notes:
                    details += f" — {'; '.join(s.notes)}"
                md_lines.append(
                    f"| {check} | {s.name} | {details} | {age} |"
                )
            md_lines.append("")

        _md_section("Strategy", strategy_stages)
        _md_section("Competitive Research", competitive_stages)
        _md_section("Ad Assets", asset_stages)

        md_lines.append("## Recommended next steps\n")
        for r in recommendations:
            md_lines.append(f"- {r}")

        out_path = client_dir / "STATUS.md"
        out_path.write_text("\n".join(md_lines), encoding="utf-8")
        console.print(f"[green]Saved dashboard to: {out_path}[/green]")


# ─── Competitor Research ────────────────────────────────────────────────────


@cli.command(name="research-competitors")
@click.option("--client", required=True, help="Client slug")
@click.option(
    "--force-refresh",
    is_flag=True,
    default=False,
    help="Re-run Exa queries and re-scrape competitor sites even if cached.",
)
@click.option(
    "--skip-onsite",
    is_flag=True,
    default=False,
    help="Skip competitor on-site review scraping (Exa-only run).",
)
def research_competitors(client: str, force_refresh: bool, skip_onsite: bool):
    """Pull all competitive research: on-site reviews + Exa sentiment-stratified queries."""
    from models.loader import load_brand
    from strategy.competitor_research import (
        cache_competitor_bundle,
        load_competitors,
        pull_competitor_reviews,
    )
    from strategy.exa_research import (
        cache_result,
        competitive_queries_for_brand,
        run_query,
    )

    brand = load_brand(client)
    competitors = load_competitors(client)

    if not competitors:
        console.print(
            f"[red]No competitors.yaml found for {client}.[/red]\n"
            f"[dim]Create clients/{client}/competitors.yaml first.[/dim]"
        )
        raise SystemExit(1)

    console.print(f"[cyan]Competitive research: {brand.name} vs {len(competitors)} competitors[/cyan]")
    for c in competitors:
        console.print(f"  - {c.name} ({c.priority}, {c.type}) -> {c.url}")

    console.print(
        f"\n[yellow]This run includes:[/yellow] Exa web sentiment (Reddit, Trustpilot, news) "
        f"+ on-site reviews via Firecrawl.\n"
        f"[yellow]NOT included:[/yellow] Amazon reviews. Run separately with: "
        f"[cyan]adc research-amazon --client {client}[/cyan]\n"
    )

    # 1) On-site competitor review scraping
    onsite_table = Table(title="On-site Reviews via Firecrawl")
    onsite_table.add_column("Competitor", style="cyan")
    onsite_table.add_column("Vendor", style="yellow")
    onsite_table.add_column("Reviews", justify="right", style="green")
    onsite_table.add_column("Pages tried", justify="right", style="dim")
    onsite_table.add_column("Notes", style="dim", max_width=40)

    if not skip_onsite:
        onsite_cache = Path("clients") / client / "research" / "competitor-reviews"
        for competitor in competitors:
            cache_path = onsite_cache / f"{competitor.slug}.json"
            if cache_path.exists() and not force_refresh:
                import json as _json
                data = _json.loads(cache_path.read_text(encoding="utf-8"))
                onsite_table.add_row(
                    competitor.name,
                    data.get("vendor", "?"),
                    str(len(data.get("reviews", []))),
                    str(len(data.get("scraped_pages", []))),
                    "(cached)",
                )
                continue

            with console.status(f"Scraping {competitor.name}..."):
                bundle = pull_competitor_reviews(competitor)
            cache_competitor_bundle(client, bundle)
            onsite_table.add_row(
                competitor.name,
                bundle.vendor,
                str(len(bundle.reviews)),
                str(len(bundle.scraped_pages)),
                bundle.notes[:80],
            )
        console.print(onsite_table)

    # 2) Exa sentiment-stratified queries
    queries = competitive_queries_for_brand(
        own_brand=brand.name,
        competitor_names=[c.name for c in competitors],
    )

    exa_table = Table(title="Exa Web Sentiment")
    exa_table.add_column("#", justify="right", style="dim")
    exa_table.add_column("Label", style="cyan")
    exa_table.add_column("Category", style="yellow")
    exa_table.add_column("Hits", justify="right", style="green")
    exa_table.add_column("Top domain", style="dim")

    exa_cache = Path("clients") / client / "research" / "exa" / "raw"
    for i, q in enumerate(queries, 1):
        from strategy.exa_research import _slugify
        cache_path = exa_cache / f"{_slugify(q.label)}.json"
        if cache_path.exists() and not force_refresh:
            import json as _json
            data = _json.loads(cache_path.read_text(encoding="utf-8"))
            top_domain = data["results"][0]["domain"] if data.get("results") else "-"
            exa_table.add_row(
                str(i), q.label, q.category, str(len(data.get("results", []))), top_domain
            )
            continue

        try:
            with console.status(f"Exa: {q.label}..."):
                result = run_query(q)
            cache_result(client, result)
            top_domain = result.results[0].domain if result.results else "-"
            exa_table.add_row(
                str(i), q.label, q.category, str(len(result.results)), top_domain
            )
        except Exception as e:
            exa_table.add_row(
                str(i), q.label, q.category, "ERROR", str(e)[:40]
            )

    console.print(exa_table)
    console.print(
        f"\n[green]Cached competitor reviews: clients/{client}/research/competitor-reviews/[/green]\n"
        f"[green]Cached Exa results: clients/{client}/research/exa/raw/[/green]\n\n"
        f"[bold]Recommended next steps:[/bold]\n"
        f"  - [cyan]adc research-amazon --client {client}[/cyan]   "
        f"(pull Amazon reviews; ~$1-5)\n"
        f"  - [cyan]adc analyze-gaps --client {client}[/cyan]      "
        f"(synthesize what's cached so far; ~$1.50)"
    )

    from strategy.cost_tracker import log_cost
    log_cost(client, "adc research-competitors",
             note=f"{len(competitors)} competitor(s), {len(queries)} Exa queries")


@cli.command(name="research-amazon")
@click.option("--client", required=True, help="Client slug")
@click.option(
    "--max-reviews", default=100, type=int,
    help="Max reviews per Amazon product per star tier (default 100). "
    "On the Apify free tier, each call is capped at ~8 reviews anyway.",
)
@click.option(
    "--stars", default="5,3,1",
    help="Comma-separated star tiers to pull (default '5,3,1' matching the gap "
    "analysis framework). Use '5,4,3,2,1' for full stratification, or '0' for "
    "no filter (returns recent reviews only).",
)
@click.option(
    "--force-refresh", is_flag=True, default=False,
    help="Re-scrape Amazon even if cached.",
)
def research_amazon(client: str, max_reviews: int, stars: str, force_refresh: bool):
    """Scrape Amazon reviews stratified by star rating for each competitor.

    Reads amazon_urls from clients/<slug>/competitors.yaml. Each star tier is a
    separate Apify call — on the free plan this multiplies per-product review
    yield by the number of tiers (typically 3 = 5/3/1 star).
    """
    from strategy.apify_amazon import (
        DEFAULT_STAR_FILTERS,
        STAR_FILTER_SHORT_NAMES,
        _extract_asin,
        cache_amazon_bundle,
        scrape_amazon_reviews,
    )
    from strategy.competitor_research import load_competitors

    # Map user input to Apify's filter values
    star_map = {
        "5": "five_star", "4": "four_star", "3": "three_star",
        "2": "two_star", "1": "one_star", "0": "all_stars",
    }
    star_filters: list[str] = []
    for s in stars.split(","):
        s = s.strip()
        if s in star_map:
            star_filters.append(star_map[s])
        else:
            console.print(f"[red]Invalid star value: '{s}'. Use 1-5 or 0 for no filter.[/red]")
            raise SystemExit(1)
    if not star_filters:
        star_filters = DEFAULT_STAR_FILTERS

    competitors = load_competitors(client)
    if not competitors:
        console.print(f"[red]No competitors.yaml found for {client}.[/red]")
        raise SystemExit(1)

    targets = [(c, url) for c in competitors for url in (c.amazon_urls or [])]
    if not targets:
        console.print(
            f"[yellow]No amazon_urls set in clients/{client}/competitors.yaml.[/yellow]\n"
            f"[dim]Add an `amazon_urls:` list to each competitor with 1-3 product URLs, then re-run.[/dim]"
        )
        raise SystemExit(1)

    total_calls = len(targets) * len(star_filters)
    console.print(
        f"[cyan]Amazon Reviews via Apify[/cyan] — {len(targets)} product(s) "
        f"x {len(star_filters)} star tier(s) = {total_calls} call(s)"
    )
    console.print(
        f"[dim]Actor: junglee/amazon-reviews-scraper. Star tiers: "
        f"{', '.join(star_filters)}. Free tier yields ~8 reviews/call (~{8 * total_calls} total).[/dim]\n"
    )

    cache_dir = Path("clients") / client / "research" / "amazon-reviews"
    table = Table(title="Amazon Review Scraping (Stratified)")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Competitor", style="cyan")
    table.add_column("ASIN", style="yellow")
    table.add_column("Tier", style="magenta")
    table.add_column("Reviews", style="green", justify="right")
    table.add_column("Notes", style="dim", max_width=40)

    call_num = 0
    for competitor, url in targets:
        asin = _extract_asin(url)
        asin_part = asin or re.sub(r"[^a-zA-Z0-9]+", "-", url)[:20]
        for star_filter in star_filters:
            call_num += 1
            short = STAR_FILTER_SHORT_NAMES.get(star_filter, star_filter)
            cache_path = cache_dir / f"{competitor.slug}-{asin_part}-{short}.json"

            if cache_path.exists() and not force_refresh:
                import json as _json
                data = _json.loads(cache_path.read_text(encoding="utf-8"))
                table.add_row(
                    str(call_num),
                    competitor.name,
                    asin or "?",
                    short,
                    str(len(data.get("reviews", []))),
                    "(cached)",
                )
                continue

            with console.status(
                f"Scraping {competitor.name} {short} ({asin or 'no-ASIN'})..."
            ):
                bundle = scrape_amazon_reviews(
                    product_url=url,
                    competitor_slug=competitor.slug,
                    competitor_name=competitor.name,
                    max_reviews=max_reviews,
                    star_filter=star_filter,
                )
            cache_amazon_bundle(client, bundle)
            table.add_row(
                str(call_num),
                competitor.name,
                bundle.asin or "?",
                short,
                str(len(bundle.reviews)),
                (bundle.notes or "OK")[:40],
            )

    console.print(table)

    # Tally totals per competitor
    from collections import defaultdict
    totals: dict[str, int] = defaultdict(int)
    for path in cache_dir.glob("*.json"):
        try:
            import json as _json
            d = _json.loads(path.read_text(encoding="utf-8"))
            totals[d.get("competitor_name", "?")] += len(d.get("reviews", []))
        except Exception:
            continue
    total_all = sum(totals.values())

    console.print(
        f"\n[green]Cached to: clients/{client}/research/amazon-reviews/[/green]"
    )
    console.print(f"[bold]Review totals per competitor:[/bold]")
    for name, n in sorted(totals.items(), key=lambda x: -x[1]):
        console.print(f"  {name}: {n}")
    console.print(f"  [bold]TOTAL: {total_all} reviews[/bold]\n")
    console.print(
        f"[dim]Next: adc analyze-gaps --client {client} "
        f"(will include Amazon data, stratified by star)[/dim]"
    )

    from strategy.cost_tracker import log_cost
    log_cost(client, "adc research-amazon", multiplier=call_num,
             note=f"{call_num} call(s), {total_all} review(s)")


@cli.command(name="analyze-gaps")
@click.option("--client", required=True, help="Client slug")
@click.option("--synthesis-only", is_flag=True, default=False,
              help="Re-run only the cross-competitor synthesis using existing per-brand analyses")
def analyze_gaps(client: str, synthesis_only: bool):
    """Run competitive gap analysis on cached research. Produces competitive-gaps.md/.yaml."""
    from models.loader import load_brand
    from strategy.gap_analyzer import analyze_competitive_gaps

    brand = load_brand(client)
    if synthesis_only:
        console.print(f"[cyan]Re-synthesizing competitive gaps for {brand.name}...[/cyan]\n")
    else:
        console.print(f"[cyan]Analyzing competitive gaps for {brand.name}...[/cyan]")
        console.print("[dim]This runs ~5-6 Claude passes (~$1-2 total). Hold tight.[/dim]\n")

    output = analyze_competitive_gaps(client, brand.name, synthesis_only=synthesis_only)

    syn = output.get("synthesis", {})
    if syn.get("summary"):
        console.print(f"[green]TL;DR:[/green] {syn['summary']}\n")

    if syn.get("exploitable_gaps"):
        table = Table(title="Exploitable Gaps")
        table.add_column("Opportunity", style="cyan", max_width=40)
        table.add_column("Competitors failing", style="yellow", max_width=25)
        table.add_column("Ad angle", style="green", max_width=50)
        for g in syn["exploitable_gaps"]:
            table.add_row(
                str(g.get("opportunity", ""))[:60],
                ", ".join(g.get("competitors_failing", []))[:30],
                str(g.get("ad_angle", ""))[:80],
            )
        console.print(table)

    console.print(
        f"\n[green]Saved:[/green]\n"
        f"  clients/{client}/research/competitive-gaps.md\n"
        f"  clients/{client}/research/competitive-gaps.yaml"
    )

    from strategy.cost_tracker import log_cost
    cmd_name = "adc analyze-gaps-synthesis" if synthesis_only else "adc analyze-gaps"
    log_cost(client, cmd_name,
             note="synthesis only" if synthesis_only else "full per-brand + synthesis")


# ─── Exa Web Research ───────────────────────────────────────────────────────


@cli.command(name="research-web")
@click.option("--client", required=True, help="Client slug")
@click.option(
    "--competitors",
    default=None,
    help="Comma-separated competitor brand names (e.g. 'poppi,Health-Ade')",
)
@click.option(
    "--category",
    default=None,
    help="Comma-separated category terms for discussion queries "
    "(e.g. 'prebiotic soda,gut health drinks')",
)
@click.option(
    "--force-refresh",
    is_flag=True,
    default=False,
    help="Re-run queries even if cached. Default: skip cached (free re-runs).",
)
def research_web(client: str, competitors: str | None, category: str | None,
                 force_refresh: bool):
    """Run Exa web research for a client — Reddit + comparison + reviews + category."""
    from models.loader import load_brand
    from strategy.exa_research import run_research_bundle

    brand = load_brand(client)
    comp_list = [c.strip() for c in competitors.split(",")] if competitors else None
    cat_list = [c.strip() for c in category.split(",")] if category else None

    console.print(f"[cyan]Running Exa research for {brand.name}...[/cyan]")
    if comp_list:
        console.print(f"  Competitors: {', '.join(comp_list)}")
    if cat_list:
        console.print(f"  Category terms: {', '.join(cat_list)}")

    results = run_research_bundle(
        client_slug=client,
        brand_name=brand.name,
        competitors=comp_list,
        category_terms=cat_list,
        skip_cached=not force_refresh,
    )

    table = Table(title=f"Exa Research - {brand.name}")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Label", style="cyan")
    table.add_column("Category", style="yellow")
    table.add_column("Hits", style="green", justify="right")
    table.add_column("Top domain", style="dim")

    for i, r in enumerate(results, 1):
        top_domain = r.results[0].domain if r.results else "-"
        table.add_row(
            str(i),
            r.query.label,
            r.query.category,
            str(len(r.results)),
            top_domain,
        )

    console.print(table)
    out_dir = Path("clients") / client / "research" / "exa" / "raw"
    console.print(f"\n[green]Cached to: {out_dir}/[/green]")
    console.print(
        f"[dim]Total queries: {len(results)} | "
        f"Re-run free (cached) | --force-refresh to override[/dim]"
    )


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


@cli.command(name="scrape-classifications")
@click.option("--library", required=True,
              help="Library to scrape Content Style for (e.g. 'standard')")
@click.option("--max-per-brand", default=30, type=int,
              help="Cap on ads scraped per brand. Default 30.")
@click.option("--no-resume", is_flag=True,
              help="Re-scrape brands that are already in the cache.")
@click.option("--start-at", default=None,
              help="Brand_id to start at (skip earlier brands; useful for resuming).")
@click.option("--connect-url", default=None,
              help="Connect to a running Chrome via CDP (e.g. http://localhost:9222). "
                   "Reuses your existing login. Skip this to launch a dedicated Chrome.")
def scrape_classifications(library: str, max_per_brand: int, no_resume: bool,
                           start_at: str | None, connect_url: str | None):
    """Drive Chrome via Playwright to scrape Foreplay's Content Style classifications.

    Opens a visible browser using a dedicated profile (~/.foreplay-scraper-profile).
    First run requires manual Foreplay login. Subsequent runs auto-authenticate.
    Cache lands at references/swipe/<library>/_classifications-cache.json and is
    written after each brand so the run is resumable.
    """
    from strategy.foreplay_browser_scraper import scrape_all

    cache = scrape_all(
        library,
        max_per_brand=max_per_brand,
        resume=not no_resume,
        start_at=start_at,
        connect_url=connect_url,
    )
    n_brands = len(cache.get("brands") or {})
    n_records = sum(len(b.get("records") or []) for b in (cache.get("brands") or {}).values())
    n_useful = sum(
        1 for b in (cache.get("brands") or {}).values()
        for r in (b.get("records") or [])
        if r.get("content_style")
    )
    console.print(
        f"[green]Done. {n_brands} brands, {n_records} total ads scraped, "
        f"{n_useful} with content_style.[/green]"
    )
    console.print(
        f"[dim]Cache: references/swipe/{library}/_classifications-cache.json[/dim]"
    )


@cli.command(name="swipe-sync")
@click.option("--library", required=True,
              help="Swipe library to sync: psychology, standard, trending")
@click.option("--category", default=None,
              help="Expert libraries only: optional single category. Omit to sync all.")
@click.option("--max-per-category", default=10, type=int,
              help="Expert libraries: cap on ads pulled per board. Default 10.")
@click.option("--max-per-niche", default=30, type=int,
              help="Discovery libraries: ads fetched per niche before bucketing. Default 30.")
@click.option("--force/--no-force", default=False,
              help="Re-download ads that already exist on disk.")
def swipe_sync(library: str, category: str | None, max_per_category: int,
               max_per_niche: int, force: bool):
    """Sync ads from Foreplay into references/swipe/<library>/<category>/."""
    from strategy.foreplay_sync import sync_library

    def progress(stats, ad, msg):
        prefix = f"[{stats.library}/{stats.category}]"
        console.print(f"[dim]{prefix}[/dim] {msg}")

    cats = [category] if category else None
    results = sync_library(
        library,
        categories=cats,
        max_per_category=max_per_category,
        max_per_niche=max_per_niche,
        force=force,
        on_progress=progress,
    )

    table = Table(title=f"swipe-sync: {library}")
    table.add_column("Category", style="cyan")
    table.add_column("Fetched", justify="right")
    table.add_column("Downloaded", justify="right", style="green")
    table.add_column("Skipped", justify="right", style="yellow")
    table.add_column("Errors", justify="right", style="red")
    for s in results:
        table.add_row(s.category, str(s.fetched), str(s.downloaded),
                      str(s.skipped), str(s.errors))
    console.print(table)


# ─── AI Ad Creation: Menu + Prompts ─────────────────────────────────────────


AI_ADS_DIR = Path("ai-ads")


def _truncate(s: str, n: int) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 3] + "..."


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--product", default=None, help="Optional: filter to a single product slug")
def menu(client: str, product: str | None):
    """Show all briefs for a client as a pickable menu."""
    from models.loader import load_all_briefs

    briefs = load_all_briefs(client)
    if product:
        briefs = [b for b in briefs if b.product == product]

    if not briefs:
        msg = f"No briefs found for '{client}'"
        if product:
            msg += f" / product '{product}'"
        console.print(f"[yellow]{msg}.[/yellow]")
        console.print(f"[dim]Run: adc brief --client {client} --product <product-slug>[/dim]")
        return

    table = Table(title=f"Brief Menu — {client}" + (f" / {product}" if product else ""))
    table.add_column("#", style="bold cyan", justify="right")
    table.add_column("Product", style="green", max_width=20)
    table.add_column("Slot", style="yellow", justify="right")
    table.add_column("Hook", style="white", max_width=60)
    table.add_column("Angle", style="magenta", max_width=35)
    table.add_column("Mechanic", style="blue", max_width=30)
    table.add_column("Format", style="dim", max_width=30)
    table.add_column("ID", style="dim")

    for i, b in enumerate(briefs, 1):
        table.add_row(
            str(i),
            b.product,
            str(b.slot) if b.slot else "—",
            _truncate(b.hook, 60),
            _truncate(b.angle, 35),
            _truncate(b.creative_mechanic, 30),
            _truncate(b.visual_format, 30),
            b.brief_id[-6:],
        )

    console.print(table)
    console.print(
        f"\n[green]Pick the ones you want and run:[/green]\n"
        f"  adc prompts --client {client} --pick 1,3,5"
    )


def _format_notes_header(
    brief: "CreativeBrief", product: "Product", aspect_ratio: str, image_refs: list[str]
) -> str:
    lines = [
        "***** NOTES *****",
        f"Brief:           {brief.brief_id}",
        f"Product:         {product.name}",
        f"Slot:            {brief.slot or '—'} / {brief.hook_type or 'unspecified'}",
        f"Mechanic:        {brief.creative_mechanic or '—'}",
        f"Format:          {brief.visual_format or '—'}",
        f"Aspect ratio:    {aspect_ratio}",
        f"Model:           fal-ai/nano-banana-2/edit",
        f"Platform:        {brief.target_platform}",
    ]
    if image_refs:
        lines.append(f"Product images:  {image_refs[0]}")
        for ref in image_refs[1:]:
            lines.append(f"                 {ref}")
    else:
        lines.append("Product images:  (none — add image_url or image_path to the product YAML)")
    lines.append(f"Generated:       {date.today().isoformat()}")
    if getattr(brief, "campaign_name", ""):
        lines.append(f"Campaign name:   {brief.campaign_name}")
    lines.append("***** END NOTES *****")
    return "\n".join(lines)


def _collect_product_image_refs(product, client_slug: str) -> list[str]:
    refs: list[str] = []
    if product.image_url:
        refs.append(product.image_url)
    if product.image_path:
        local = Path("clients") / client_slug / product.image_path
        refs.append(str(local) if local.exists() else product.image_path)
    refs.extend(product.additional_images or [])
    return refs


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--pick", required=True, help="Comma-separated menu numbers from `adc menu`, e.g. 1,3,5")
@click.option("--product", default=None, help="Optional: scope to a single product (must match `adc menu --product`)")
@click.option(
    "--creative-direction",
    default="",
    help="Optional pre-generation creative directive applied to every brief. "
    "Example: 'two callouts in primary brand color + accent, text bubble at top'. "
    "Becomes the highest-priority constraint in the NB2 prompt-writer.",
)
@click.option(
    "--offer",
    default="NONE",
    show_default=True,
    help="Offer code for the Meta ad naming taxonomy (slot 9). E.g. FREESHIP, "
    "BFCM25, 20OFF. Alphanumeric only, capped at 12 chars. Default NONE.",
)
def prompts(client: str, pick: str, product: str | None, creative_direction: str, offer: str):
    """Generate fal.ai prompts for the briefs you picked off `adc menu`."""
    from models.loader import (
        load_all_briefs,
        load_brand,
        load_product_by_name,
        load_avatar,
    )
    from generators.prompt_engine import prompt_from_brief, infer_aspect_ratio

    try:
        picks = [int(x.strip()) for x in pick.split(",") if x.strip()]
    except ValueError:
        console.print("[red]Invalid --pick. Use comma-separated integers, e.g. 1,3,5[/red]")
        raise SystemExit(1)

    briefs = load_all_briefs(client)
    if product:
        briefs = [b for b in briefs if b.product == product]
    if not briefs:
        console.print(f"[yellow]No briefs found for '{client}'.[/yellow]")
        raise SystemExit(1)

    bad = [n for n in picks if n < 1 or n > len(briefs)]
    if bad:
        console.print(f"[red]Out-of-range picks: {bad}. Menu has {len(briefs)} briefs.[/red]")
        raise SystemExit(1)

    selected = [briefs[n - 1] for n in picks]

    out_dir = AI_ADS_DIR / client / "prompts"
    out_dir.mkdir(parents=True, exist_ok=True)

    brand = load_brand(client)
    avatar = load_avatar(client)
    product_cache: dict[str, object] = {}

    for brief in selected:
        if brief.product not in product_cache:
            product_cache[brief.product] = load_product_by_name(client, brief.product)
        prod = product_cache[brief.product]

        aspect_ratio = infer_aspect_ratio(brief)
        image_refs = _collect_product_image_refs(prod, client)

        # Build campaign_name eagerly so it lands in the notes header and a sidecar.
        if not brief.campaign_name:
            try:
                from strategy.naming import build_campaign_name
                brief.campaign_name = build_campaign_name(
                    brief,
                    brand,
                    offer=offer,
                    iteration=1,
                    source="AI",
                )
            except (ValueError, Exception):
                pass  # brand.code missing → continue without name

        with console.status(f"Writing prompt for slot {brief.slot} — {brief.brief_id[-6:]}..."):
            prompt_text = prompt_from_brief(
                brief=brief,
                brand=brand,
                product=prod,
                avatar=avatar,
                aspect_ratio=aspect_ratio,
                creative_direction=creative_direction,
            )

        notes = _format_notes_header(brief, prod, aspect_ratio, image_refs)
        out_path = out_dir / f"{brief.brief_id}.txt"
        out_path.write_text(notes + "\n\n" + prompt_text + "\n", encoding="utf-8")
        # Sidecar for easy copy/paste into Meta Ads Manager.
        if brief.campaign_name:
            (out_dir / f"{brief.brief_id}_campaign.txt").write_text(
                brief.campaign_name + "\n", encoding="utf-8"
            )
        console.print(f"[green]\\[OK][/green] {out_path}")

    console.print(
        f"\n[green]Wrote {len(selected)} prompt(s) to {out_dir}/[/green]\n"
        f"[dim]Paste each .txt into fal.ai along with the product images listed in its NOTES block.[/dim]"
    )

    from strategy.cost_tracker import log_cost
    log_cost(client, "adc prompts", multiplier=len(selected),
             note=f"{len(selected)} prompt(s)")


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--pick", required=True, help="Comma-separated menu numbers from `adc menu`, e.g. 1,3,5")
@click.option("--product", default=None, help="Optional: scope to a single product")
@click.option("--num-images", default=1, type=int, help="How many image variations per pick (default 1)")
@click.option("--aspect-ratio", default=None, help="Override aspect ratio (default: inferred from brief)")
@click.option("--thinking", default="disabled", help="NB2 thinking level: disabled, low, medium, high")
@click.option(
    "--include-alternates",
    is_flag=True,
    default=False,
    help="Generate the primary visual_format PLUS each visual_format_alternatives "
    "entry (3 images per brief instead of 1). Same psychological mechanic, "
    "different production styles — useful for A/B/C variance testing.",
)
@click.option(
    "--reference",
    "reference_template_id",
    default=None,
    help="ART-DIRECTED single-reference mode. Pass a template id from "
    "`adc list-templates` (e.g. 'us-vs-them-price-comparison-panels'). "
    "Generation uses ONLY that one template + its source reference image — "
    "no swipe library, no Nanobana, no averaging. Output is grounded in one "
    "specific hand-picked ad. Cleanest path when you want to mimic a "
    "specific aesthetic.",
)
@click.option(
    "--creative-direction",
    default="",
    help="Optional pre-generation creative directive applied to every brief. "
    "Example: 'two callouts in primary brand color + accent, text bubble at top'. "
    "Becomes the highest-priority constraint in the NB2 prompt-writer.",
)
@click.option(
    "--offer",
    default="NONE",
    show_default=True,
    help="Offer code for the Meta ad naming taxonomy (slot 9). E.g. FREESHIP, "
    "BFCM25, 20OFF. Alphanumeric only, capped at 12 chars. Default NONE.",
)
@click.option(
    "--engine",
    type=click.Choice(["nb2", "higgsfield-soul"]),
    default="nb2",
    show_default=True,
    help=(
        "Image-generation engine. "
        "'nb2' = fal.ai Nano Banana 2 (existing, product-aware, multi-image). "
        "'higgsfield-soul' = Higgs Field soul_2 with each persona's trained "
        "Soul Character + PIL text overlay (identity-locked face, phone-camera "
        "aesthetic). Requires HF_CREDENTIALS in .env and a 'ready' Soul on each "
        "persona's avatar YAML. Ignores --reference and the product image — "
        "soul_2 doesn't accept multi-image edits."
    ),
)
@click.option(
    "--fallback-engine",
    type=click.Choice(["nb2"]),
    default=None,
    help=(
        "If --engine higgsfield-soul fails because of missing API credits, "
        "automatically retry the run with this engine instead of aborting. "
        "Useful when the dashboard wants graceful degradation."
    ),
)
def generate(client: str, pick: str, product: str | None, num_images: int,
             aspect_ratio: str | None, thinking: str,
             include_alternates: bool, reference_template_id: str | None,
             creative_direction: str, offer: str,
             engine: str, fallback_engine: str | None):
    """Generate finished ad images for picked briefs — writes prompts AND calls fal.ai."""
    from models.loader import (
        load_all_briefs,
        load_brand,
        load_product_by_name,
        load_avatar,
    )
    from generators.image_generator import generate_from_brief, generate_from_brief_and_template
    from generators.prompt_engine import infer_aspect_ratio

    try:
        picks = [int(x.strip()) for x in pick.split(",") if x.strip()]
    except ValueError:
        console.print("[red]Invalid --pick. Use comma-separated integers, e.g. 1,3,5[/red]")
        raise SystemExit(1)

    briefs = load_all_briefs(client)
    if product:
        briefs = [b for b in briefs if b.product == product]
    if not briefs:
        console.print(f"[yellow]No briefs found for '{client}'.[/yellow]")
        raise SystemExit(1)

    bad = [n for n in picks if n < 1 or n > len(briefs)]
    if bad:
        console.print(f"[red]Out-of-range picks: {bad}. Menu has {len(briefs)} briefs.[/red]")
        raise SystemExit(1)

    selected = [briefs[n - 1] for n in picks]

    prompts_dir = AI_ADS_DIR / client / "prompts"
    images_dir = AI_ADS_DIR / client / "images"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    brand = load_brand(client)
    avatar = load_avatar(client)
    product_cache: dict[str, object] = {}

    # Build the list of (brief, format_label, format_value, variant_suffix) tuples to
    # generate. Without --include-alternates, each brief produces ONE generation
    # using its primary visual_format. With --include-alternates, each brief
    # produces (1 + len(alternates)) generations, one per visual format option.
    generation_jobs: list[tuple[object, str, str, str]] = []
    for brief in selected:
        primary_fmt = brief.visual_format or ""
        generation_jobs.append((brief, "primary", primary_fmt, ""))
        if include_alternates:
            alts = list(brief.visual_format_alternatives or [])
            for i, alt_fmt in enumerate(alts, 1):
                generation_jobs.append((brief, f"alt{i}", alt_fmt, f"_alt{i}"))

    total_jobs = len(generation_jobs)
    total_images_estimate = total_jobs * num_images
    if include_alternates:
        console.print(
            f"[dim]--include-alternates: generating {total_jobs} variant(s) "
            f"across {len(selected)} brief(s) × {num_images} image(s) each "
            f"= {total_images_estimate} total image(s)[/dim]"
        )

    for brief, variant_label, variant_format, variant_suffix in generation_jobs:
        if brief.product not in product_cache:
            product_cache[brief.product] = load_product_by_name(client, brief.product)
        prod = product_cache[brief.product]

        # For alternate generations, clone the brief with the alternate format
        # substituted into visual_format. The mechanic stays the same — that's
        # the whole point of variance testing.
        active_brief = brief
        if variant_label != "primary" and variant_format:
            active_brief = brief.model_copy(update={"visual_format": variant_format})

        ar = aspect_ratio or infer_aspect_ratio(active_brief)
        image_refs = _collect_product_image_refs(prod, client)

        # Filename gets the variant suffix so each generation is distinct
        # on disk even though they share a brief_id.
        original_id = brief.brief_id
        if variant_suffix:
            active_brief = active_brief.model_copy(
                update={"brief_id": f"{original_id}{variant_suffix}"}
            )

        # Resolve the reference image path for art-directed mode by walking
        # the templates dir to find the matching id, then mapping to its
        # raw/ source image.
        reference_image_path = None
        if reference_template_id:
            import yaml as _yaml
            templates_root = Path("clients") / client / "templates"
            for yaml_file in templates_root.rglob("*.yaml"):
                try:
                    with open(yaml_file, encoding="utf-8") as f:
                        td = _yaml.safe_load(f) or {}
                    if td.get("id") == reference_template_id:
                        # Stem maps to raw/<category>/<stem>.<ext>
                        category = yaml_file.parent.name
                        stem = yaml_file.stem
                        raw_dir = Path("clients") / client / "reference_ads" / "raw" / category
                        for ext in (".png", ".jpg", ".jpeg", ".webp"):
                            candidate = raw_dir / f"{stem}{ext}"
                            if candidate.exists():
                                reference_image_path = candidate
                                break
                        if reference_image_path:
                            break
                except Exception:
                    continue
            if not reference_image_path:
                console.print(
                    f"[red]Reference template '{reference_template_id}' not found. "
                    f"Run `adc list-templates --client {client}` to see available ids.[/red]"
                )
                raise SystemExit(1)

        with console.status(
            f"Slot {brief.slot} ({original_id[-6:]}) {variant_label} "
            f"— writing prompt + generating {num_images} image(s)"
            f" via [bold]{engine}[/bold]..."
        ):
            # Higgs Field Soul mode ignores --reference (soul_2 doesn't take
            # template images the way NB2 does). Route everything through
            # generate_from_brief() — its dispatcher handles the HF path +
            # credit-error fallback.
            if engine == "higgsfield-soul":
                if reference_template_id:
                    console.print(
                        f"[yellow]Note: --reference is ignored when --engine "
                        f"higgsfield-soul. The trained Soul Character supplies "
                        f"the persona identity; templates aren't applicable.[/yellow]"
                    )
                prompt_text, results = generate_from_brief(
                    brief=active_brief,
                    brand=brand,
                    product=prod,
                    avatar=avatar,
                    client_slug=client,
                    output_dir=images_dir,
                    num_images=num_images,
                    aspect_ratio=ar,
                    thinking_level=thinking,
                    creative_direction=creative_direction,
                    offer=offer,
                    engine=engine,
                    fallback_engine=fallback_engine,
                )
            elif reference_template_id:
                from generators.image_generator import generate_from_brief_and_template
                prompt_text, results = generate_from_brief_and_template(
                    brief=active_brief,
                    template_id=reference_template_id,
                    reference_image_path=reference_image_path,
                    brand=brand,
                    product=prod,
                    avatar=avatar,
                    client_slug=client,
                    output_dir=images_dir,
                    num_images=num_images,
                    aspect_ratio=ar,
                    thinking_level=thinking,
                    creative_direction=creative_direction,
                    offer=offer,
                )
            else:
                prompt_text, results = generate_from_brief(
                    brief=active_brief,
                    brand=brand,
                    product=prod,
                    avatar=avatar,
                    client_slug=client,
                    output_dir=images_dir,
                    num_images=num_images,
                    aspect_ratio=ar,
                    thinking_level=thinking,
                    creative_direction=creative_direction,
                    offer=offer,
                    engine=engine,
                    fallback_engine=fallback_engine,
                )

        local_paths = [str(r.local_path) for r in results if r.local_path]
        seed = results[0].seed if results else None

        notes = _format_notes_header(active_brief, prod, ar, image_refs)
        # Annotate the variant in the notes header so disk artifacts are self-documenting
        notes = f"# VARIANT: {variant_label} ({variant_format[:80]})\n" + notes
        if local_paths:
            extra = ["", "***** GENERATED *****"]
            extra.append(f"Seed:            {seed}")
            extra.append(f"Output image(s): {local_paths[0]}")
            for p in local_paths[1:]:
                extra.append(f"                 {p}")
            extra.append("***** END GENERATED *****")
            notes = notes + "\n" + "\n".join(extra)

        prompt_path = prompts_dir / f"{active_brief.brief_id}.txt"
        prompt_path.write_text(notes + "\n\n" + prompt_text + "\n", encoding="utf-8")

        console.print(f"[green]\\[OK][/green] {prompt_path}")
        for p in local_paths:
            console.print(f"       {p}")

    console.print(
        f"\n[green]Generated {total_jobs} variant(s) × {num_images} image(s) "
        f"= {total_images_estimate} image(s) to {images_dir}/[/green]"
    )

    from strategy.cost_tracker import log_cost
    log_cost(client, "adc generate", multiplier=total_images_estimate,
             note=f"{total_images_estimate} image(s)"
             + (f" ({total_jobs} variants, alternates included)" if include_alternates else ""))


# ─── Ad Remix ───────────────────────────────────────────────────────────────


@cli.command()
@click.option("--client", required=True, help="Client slug")
@click.option("--product", required=True, help="Product slug or display name")
@click.option(
    "--reference",
    "ref_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Local path to a reference ad image (PNG/JPG/WEBP)",
)
@click.option(
    "--foreplay-url",
    default=None,
    help="Foreplay ad URL, e.g. https://app.foreplay.co/ad/12345",
)
@click.option(
    "--foreplay-id",
    default=None,
    help="Raw Foreplay numeric ad ID",
)
@click.option(
    "--variations",
    default=5,
    type=int,
    show_default=True,
    help="How many remix variations to generate",
)
@click.option(
    "--high-fidelity",
    default=2,
    type=int,
    show_default=True,
    help="How many variations should mimic the reference visual style closely "
    "(same setting/person/typography). Rest go to medium then low.",
)
@click.option(
    "--medium-fidelity",
    default=2,
    type=int,
    show_default=True,
    help="How many variations get small persona-tuned variation. "
    "Remaining variations are 'low' fidelity (creative re-imagining).",
)
@click.option(
    "--creative-direction",
    default="",
    help="Optional pre-generation creative directive applied to every variation. "
    "Example: 'two callouts in primary brand color + accent, text bubble at top'. "
    "Becomes the highest-priority constraint in the NB2 prompt-writer.",
)
@click.option(
    "--offer",
    default="NONE",
    show_default=True,
    help="Offer code for the Meta ad naming taxonomy (slot 9). E.g. FREESHIP, "
    "BFCM25, 20OFF. Alphanumeric only, capped at 12 chars. Default NONE.",
)
@click.option(
    "--no-trending",
    "no_trending",
    is_flag=True,
    default=False,
    help="Skip the trending-format recommender. By default each variation "
    "brief gets top-3 trending alternatives attached.",
)
@click.option(
    "--mode",
    type=click.Choice(["strategic", "differential"]),
    default="strategic",
    show_default=True,
    help=(
        "Prompt-writing mode. "
        "'strategic' (default) generates verbose ~1500-word prompts that "
        "DESCRIBE a new ad inspired by the reference — best for fresh-brief "
        "generation where psychology drives a different visual. "
        "'differential' vision-extracts the reference's text inventory, "
        "asks Claude to map each source phrase to a target phrase based on "
        "the brief, and produces a SHORT surgical-edit prompt (\"swap "
        "product, swap text, preserve everything else\"). Best for layout-"
        "faithful remixes like us-vs-them comparison ads. The "
        "--creative-direction flag becomes the ONLY allowed deviation "
        "(e.g. \"change background to spring grassy field\")."
    ),
)
def remix(
    client: str,
    product: str,
    ref_path: str | None,
    foreplay_url: str | None,
    foreplay_id: str | None,
    variations: int,
    high_fidelity: int,
    medium_fidelity: int,
    creative_direction: str,
    offer: str,
    no_trending: bool,
    mode: str,
):
    """Reverse-engineer a reference ad and remix it for your product.

    Provide exactly one of --reference (local file), --foreplay-url, or
    --foreplay-id. The remixer extracts the ad's strategic DNA (ad-type,
    psychological levers, framework, creative mechanic, visual format),
    locks that structure, and generates N variations across your client's
    personas × psychology heuristics. Each variation produces a CreativeBrief
    plus a Nano Banana 2 prompt under clients/<slug>/remixes/<timestamp>/.
    """
    from strategy.ad_remixer import remix as run_remix
    from strategy.cost_tracker import log_cost

    sources = [s for s in (ref_path, foreplay_url, foreplay_id) if s]
    if len(sources) != 1:
        console.print(
            "[red]Provide exactly one of --reference, --foreplay-url, or --foreplay-id.[/red]"
        )
        raise SystemExit(1)
    if variations < 1:
        console.print("[red]--variations must be at least 1.[/red]")
        raise SystemExit(1)

    foreplay_ref = foreplay_url or foreplay_id

    console.print(
        f"[cyan]Remixing[/cyan] {variations} variation(s) for "
        f"[bold]{client}[/bold] / [bold]{product}[/bold] "
        f"([dim]mode={mode}[/dim])..."
    )
    result = run_remix(
        client_slug=client,
        product_ref=product,
        reference=ref_path,
        foreplay_url_or_id=foreplay_ref,
        variations=variations,
        high_fidelity=high_fidelity,
        medium_fidelity=medium_fidelity,
        creative_direction=creative_direction,
        offer=offer,
        include_trending=not no_trending,
        mode=mode,
    )

    analysis = result["analysis"]
    out_dir = result["out_dir"]
    briefs = result["briefs"]
    pairs = result["pairs"]
    fidelity_tiers = result.get("fidelity_tiers") or ["medium"] * len(briefs)

    console.print("\n[bold cyan]Reference analysis[/bold cyan]")
    console.print(
        f"  ad_type:           [green]{analysis.ad_type}[/green] "
        f"([dim]conf {analysis.ad_type_confidence:.2f}[/dim])"
    )
    console.print(
        f"  psych_levers:      {', '.join(analysis.psych_levers) or '[dim]—[/dim]'}"
    )
    console.print(f"  framework:         {analysis.framework}")
    console.print(f"  creative_mechanic: {analysis.creative_mechanic or '[dim]—[/dim]'}")
    console.print(f"  visual_format:     {analysis.visual_format or '[dim]—[/dim]'}")
    console.print(f"  awareness:         {analysis.awareness_level}")
    if analysis.enemy:
        console.print(f"  enemy:             {analysis.enemy}")
    if analysis.pain_attacked:
        console.print(f"  pain_attacked:     {analysis.pain_attacked}")

    table = Table(title=f"Remix variations ({len(briefs)})")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Fidelity", style="yellow")
    table.add_column("Persona", style="cyan")
    table.add_column("Lever", style="magenta")
    table.add_column("Hook", style="green")
    for i, (brief, (_avatar, lever), tier) in enumerate(
        zip(briefs, pairs, fidelity_tiers), 1
    ):
        table.add_row(
            str(i),
            tier,
            brief.persona[:32],
            lever,
            (brief.hook or "—")[:55],
        )
    console.print(table)

    console.print(f"\n[green]Wrote {len(briefs)} brief(s) + prompt(s) to:[/green]")
    console.print(f"  {out_dir}/")
    console.print("    analysis.yaml")
    console.print("    briefs.yaml")
    console.print("    reference.<ext>")
    console.print(f"    prompts/  ({len(briefs)} .txt files)")

    console.print(
        "\n[dim]Next steps:[/dim]\n"
        "  - Review prompts/*.txt and paste into fal.ai (Nano Banana 2), OR\n"
        f"  - Drop briefs into your menu and run `adc generate --client {client} --pick ...`"
    )

    log_cost(
        client,
        "adc remix",
        multiplier=variations,
        note=f"{variations} remix variation(s) from {analysis.source_type}",
    )


@cli.command(name="remix-images")
@click.option(
    "--remix-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to a remix directory (e.g. clients/<slug>/remixes/<timestamp>)",
)
@click.option(
    "--num-images",
    default=1,
    type=int,
    show_default=True,
    help="How many image variations per brief",
)
@click.option(
    "--thinking",
    default="disabled",
    help="NB2 thinking level: disabled, low, medium, high",
)
@click.option(
    "--aspect-ratio",
    default="1:1",
    show_default=True,
    help="Aspect ratio for all generated images",
)
@click.option(
    "--engine",
    type=click.Choice(["nb2", "higgsfield-soul"]),
    default="nb2",
    show_default=True,
    help=(
        "Image-generation engine. "
        "'nb2' = fal.ai Nano Banana 2 (existing, product-aware). "
        "'higgsfield-soul' = Higgs Field soul_2 using each persona's trained "
        "soul_id (identity-locked face, phone-camera aesthetic). Requires "
        "HF_CREDENTIALS in .env and a 'ready' Soul Character on each avatar."
    ),
)
@click.option(
    "--fallback-engine",
    type=click.Choice(["nb2"]),
    default=None,
    help=(
        "If --engine higgsfield-soul fails because of missing API credits, "
        "automatically retry the run with this engine instead of aborting. "
        "Useful when the dashboard wants graceful degradation."
    ),
)
@click.option(
    "--staged",
    is_flag=True,
    default=False,
    help=(
        "Split the differential edit into 3 sequential passes — product "
        "swap, then text swap, then optional model/character swap via "
        "Higgsfield Soul. Each pass has ONE job, mirroring the operator's "
        "manual workflow that produced the cleanest results. Requires a "
        "differential-mode remix run (the mappings/ directory). Costs ~3x "
        "more API calls per brief. Intermediate stage images are saved."
    ),
)
def remix_images(
    remix_dir: str,
    num_images: int,
    thinking: str,
    aspect_ratio: str,
    engine: str,
    fallback_engine: str | None,
    staged: bool,
):
    """Generate ad images for an existing remix directory.

    Reads briefs.yaml + prompts/*.txt from the directory, fires the selected
    engine for each, and saves images to <remix-dir>/images/.

    Use --engine higgsfield-soul to route through Higgs Field with each
    persona's trained Soul Character — gives identity-locked output. Use the
    default --engine nb2 for the existing fal.ai Nano Banana 2 pipeline.

    Pass --staged for differential runs to use the 3-pass product → text →
    model workflow (mirrors the manual Higgsfield process).
    """
    from strategy.ad_remixer import generate_remix_images
    from strategy.cost_tracker import log_cost

    rd = Path(remix_dir)
    client_slug = ""
    if "clients" in rd.parts:
        idx = rd.parts.index("clients")
        if idx + 1 < len(rd.parts):
            client_slug = rd.parts[idx + 1]

    engine_label = (
        "Higgs Field soul_2 (identity-locked)"
        if engine == "higgsfield-soul"
        else "fal.ai Nano Banana 2"
    )
    staged_label = " · STAGED 3-pass" if staged else ""
    fallback_label = f" (fallback: {fallback_engine})" if fallback_engine else ""
    with console.status(
        f"Generating {num_images} image(s) per brief — firing "
        f"{engine_label}{staged_label}{fallback_label}..."
    ):
        paths = generate_remix_images(
            remix_dir=remix_dir,
            num_images=num_images,
            thinking_level=thinking,
            aspect_ratio=aspect_ratio,
            engine=engine,
            fallback_engine=fallback_engine,
            staged=staged,
        )

    if paths:
        console.print(f"\n[green]Generated {len(paths)} image(s) via {engine_label}:[/green]")
        for p in paths:
            console.print(f"  {p}")
    else:
        console.print(
            f"\n[red]Generated 0 image(s).[/red] "
            f"{engine_label} produced no output and the fallback "
            f"({fallback_engine or 'none configured'}) did not recover. "
            f"Check the per-brief errors above for the root cause."
        )

    if client_slug:
        log_cost(
            client_slug,
            "adc remix-images",
            multiplier=len(paths),
            note=f"{len(paths)} image(s) from {rd.name} via {engine}"
            + (f" (fallback: {fallback_engine})" if fallback_engine else ""),
        )


@cli.command(name="remix-refine")
@click.option(
    "--remix-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to a remix directory (e.g. clients/<slug>/remixes/<timestamp>)",
)
@click.option(
    "--brief",
    "brief_id",
    required=True,
    help="Brief ID to refine, e.g. secondkind-remix-74c0e5",
)
@click.option(
    "--feedback",
    required=True,
    help="What you want changed about the image (natural language)",
)
@click.option(
    "--num-images",
    default=1,
    type=int,
    show_default=True,
    help="How many refined variations to generate (each costs ~$0.08)",
)
@click.option(
    "--aspect-ratio",
    default="1:1",
    show_default=True,
    help="Aspect ratio for the refined image",
)
@click.option(
    "--thinking",
    default="disabled",
    help="NB2 thinking level: disabled, low, medium, high",
)
@click.option(
    "--from-image",
    "from_image",
    default=None,
    help="Specific image filename to refine FROM (e.g. brief-id_1x1.png to start "
    "from the original instead of the latest version). Default: latest version.",
)
@click.option(
    "--engine",
    type=click.Choice(["nb2", "higgsfield-soul"]),
    default="nb2",
    show_default=True,
    help=(
        "Refinement engine. "
        "'nb2' = fal.ai NB2 edit endpoint (Claude rewrites the prompt + uses "
        "product image and previous output as refs). "
        "'higgsfield-soul' = Higgs Field soul_2 iterative refinement using "
        "the persona's trained Soul Character + the previous SCENE image as "
        "a composition reference. Mirrors the manual HF workflow (generate → "
        "use as reference → generate next). Requires HF_CREDENTIALS and a "
        "'ready' Soul on the brief's persona."
    ),
)
@click.option(
    "--fallback-engine",
    type=click.Choice(["nb2"]),
    default=None,
    help=(
        "If --engine higgsfield-soul fails because of missing API credits, "
        "automatically retry the refinement with this engine instead of "
        "aborting. Used by the dashboard for graceful degradation."
    ),
)
def remix_refine(
    remix_dir: str,
    brief_id: str,
    feedback: str,
    num_images: int,
    aspect_ratio: str,
    thinking: str,
    from_image: str | None,
    engine: str,
    fallback_engine: str | None,
):
    """Refine an existing remix image with natural-language feedback.

    Default engine is NB2 (fal.ai edit endpoint with Claude prompt rewrite).
    Pass `--engine higgsfield-soul` for iterative HF refinement using each
    persona's trained Soul Character + the previous scene as a composition
    reference — mirrors the user's manual stage-by-stage HF workflow.

    Saves new images as <brief-id>_v<N>.png (single) or
    <brief-id>_v<N>_<letter>.png (multiple) alongside the original. HF mode
    also writes a <brief-id>_v<N>_scene.png alongside (text-free version).

    Each refinement is logged to refinement_log.yaml in the remix folder.
    """
    from strategy.ad_remixer import refine_image
    from strategy.cost_tracker import log_cost

    if num_images < 1:
        console.print("[red]--num-images must be at least 1[/red]")
        raise SystemExit(1)
    if not feedback.strip():
        console.print("[red]--feedback must be non-empty[/red]")
        raise SystemExit(1)

    rd = Path(remix_dir)
    client_slug = ""
    if "clients" in rd.parts:
        idx = rd.parts.index("clients")
        if idx + 1 < len(rd.parts):
            client_slug = rd.parts[idx + 1]

    with console.status(
        f"Refining `{brief_id}` ({num_images} variation(s)) via "
        f"[bold]{engine}[/bold] — feedback: {feedback[:60]}..."
    ):
        paths = refine_image(
            remix_dir=remix_dir,
            brief_id=brief_id,
            feedback=feedback,
            num_images=num_images,
            aspect_ratio=aspect_ratio,
            thinking_level=thinking,
            base_image=from_image,
            engine=engine,
            fallback_engine=fallback_engine,
        )

    console.print(f"\n[green]Generated {len(paths)} refined image(s):[/green]")
    for p in paths:
        console.print(f"  {p}")

    if client_slug:
        log_cost(
            client_slug,
            "adc remix-refine",
            multiplier=len(paths),
            note=f"{len(paths)} refinement(s) for {brief_id}",
        )


@cli.command(name="remix-rebuild-prompts")
@click.option(
    "--remix-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to a differential-mode remix directory (e.g. clients/<slug>/remixes/<timestamp>)",
)
@click.option(
    "--brief",
    "brief_id",
    default=None,
    help="Optional: rebuild only this brief's prompt. Default: rebuild all.",
)
@click.option(
    "--creative-direction",
    default=None,
    help=(
        "Override the run's saved creative_directive.txt. Leave empty to use "
        "whatever was saved at remix time (or none if the operator skipped it). "
        "Useful when iterating on the setting / style delta without re-running "
        "the whole remix."
    ),
)
def remix_rebuild_prompts(
    remix_dir: str,
    brief_id: str | None,
    creative_direction: str | None,
):
    """Re-read mappings/*.yaml and rebuild differential prompts.

    Use case: Claude's source→target mapping was 90% right but one or two
    lines need a manual nudge. Edit `mappings/<brief_id>.yaml` by hand,
    then run this to regenerate just the prompts. No new LLM calls; no
    image generation. After rebuilding, re-fire image generation via
    `adc remix-images --remix-dir <dir>`.

    Requires the remix run to have been generated in differential mode
    (the `mappings/` directory only exists for that mode)."""
    from generators.prompt_engine import infer_aspect_ratio
    from strategy.ad_remixer import _build_differential_prompt, _format_remix_notes
    from models.brief import CreativeBrief

    rd = Path(remix_dir)
    mappings_dir = rd / "mappings"
    if not mappings_dir.exists():
        console.print(
            f"[red]No mappings/ directory in {rd}.[/red] "
            f"This command only works on differential-mode runs. "
            f"Re-run the original remix with `--mode differential` first."
        )
        raise SystemExit(1)

    briefs_path = rd / "briefs.yaml"
    if not briefs_path.exists():
        console.print(f"[red]No briefs.yaml in {rd}[/red]")
        raise SystemExit(1)

    import yaml as _yaml
    briefs_data = _yaml.safe_load(briefs_path.read_text(encoding="utf-8")) or []

    # Resolve the client slug from the run path so we can load brand + analysis.
    client_slug = ""
    if "clients" in rd.parts:
        idx = rd.parts.index("clients")
        if idx + 1 < len(rd.parts):
            client_slug = rd.parts[idx + 1]

    # Determine the creative direction to use:
    #   1. --creative-direction flag (explicit override) → use as-is
    #   2. Saved creative_directive.txt in the run → use that
    #   3. Empty (no operator delta) → omit SETTING/STYLE block in the prompt
    if creative_direction is None:
        cd_file = rd / "creative_directive.txt"
        cd = cd_file.read_text(encoding="utf-8").strip() if cd_file.exists() else ""
    else:
        cd = creative_direction.strip()

    # Load product for the swap line.
    product = None
    if briefs_data and client_slug:
        try:
            from strategy.ad_remixer import _load_product_flexible
            first_product_name = briefs_data[0].get("product", "")
            if first_product_name:
                product = _load_product_flexible(
                    client_slug, first_product_name.lower().replace(" ", "-")
                )
        except Exception:
            product = None
    if product is None:
        console.print(
            f"[yellow]Could not load product for {client_slug}; using placeholder name in prompt.[/yellow]"
        )

    prompts_dir = rd / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    rebuilt = 0
    skipped = 0
    for brief_dict in briefs_data:
        bid = brief_dict.get("brief_id", "")
        if brief_id and bid != brief_id:
            continue

        mapping_path = mappings_dir / f"{bid}.yaml"
        if not mapping_path.exists():
            console.print(f"[yellow]Skip {bid}: no mapping file at {mapping_path}[/yellow]")
            skipped += 1
            continue

        try:
            mapping_data = _yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
            mapping = mapping_data.get("mapping") or []
            if not isinstance(mapping, list):
                raise ValueError("mapping field is not a list")
        except Exception as e:
            console.print(f"[red]Skip {bid}: bad mapping YAML ({e})[/red]")
            skipped += 1
            continue

        try:
            brief_obj = CreativeBrief(**brief_dict)
        except Exception as e:
            console.print(f"[red]Skip {bid}: bad brief schema ({e})[/red]")
            skipped += 1
            continue

        aspect = infer_aspect_ratio(brief_obj)
        # Use a placeholder product name if we couldn't load one — keeps the
        # rebuild non-blocking even if product YAML drifted since the remix.
        from types import SimpleNamespace
        prod_for_prompt = product or SimpleNamespace(name=brief_dict.get("product", "this product"))

        prompt_text = _build_differential_prompt(
            brief=brief_obj,
            product=prod_for_prompt,
            mapping=mapping,
            creative_direction=cd,
            aspect_ratio=aspect,
        )

        notes = (
            f"***** REMIX NOTES (rebuilt from mapping YAML) *****\n"
            f"Brief:           {bid}\n"
            f"Product:         {brief_dict.get('product', '?')}\n"
            f"Persona:         {brief_dict.get('persona', '?')}\n"
            f"Aspect ratio:    {aspect}\n"
            f"***** END NOTES *****"
        )
        notes = f"# MODE: differential (rebuilt from mapping YAML)\n" + notes

        out_path = prompts_dir / f"{bid}.txt"
        out_path.write_text(notes + "\n\n" + prompt_text + "\n", encoding="utf-8")
        console.print(f"[green]\\[OK][/green] {out_path}")
        rebuilt += 1

    console.print(
        f"\n[green]Rebuilt {rebuilt} prompt(s).[/green] "
        + (f"[yellow]Skipped {skipped}.[/yellow]" if skipped else "")
    )
    console.print(
        f"[dim]Re-fire image generation: "
        f"adc remix-images --remix-dir {remix_dir}[/dim]"
    )


if __name__ == "__main__":
    cli()
