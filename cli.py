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
