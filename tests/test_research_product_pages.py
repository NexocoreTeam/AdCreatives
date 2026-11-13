"""Product-page handling in `adc research` on stores that are not Shopify.

Three gaps on WordPress + WooCommerce stores (found 2026-11-13):
  - product pages live at /product/<slug>/ and discovery only kept /products/,
    so research read none of the store's real product pages
  - WordPress redirects /about -> /about/ and Firecrawl keys its results by the
    FINAL url, so every page asked for without the trailing slash was dropped
  - on a store with many products the operator had no way to name the page
    to read
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

import strategy.researcher as researcher
from strategy.researcher import (
    MAX_PRODUCT_PAGES,
    ProductCard,
    discover_product_urls_smart,
    fetch_pages,
    fetch_product_pages,
    is_product_page_path,
    select_product_page_urls,
    validate_product_urls,
)

BASE = "https://shop.example"


# ─── Which paths are product pages ───────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/products/turt-plush",
        "/collections/all/products/turt-plush",
        "/product/focus-blend/",
        "/product/focus-blend",
        "/en/products/turt-plush",
        "/Product/Focus-Blend/",
    ],
)
def test_product_page_paths_are_recognised(path):
    assert is_product_page_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "/product-category/brand/house-brand/",
        "/product-tag/mushroom/",
        "/products",
        "/products/",
        "/product/",
        "/shop/",
        "/blog/best-products-of-2026/",
        "/",
        "",
    ],
)
def test_listing_and_other_paths_are_not_product_pages(path):
    assert not is_product_page_path(path)


# ─── Discovery from the site map ─────────────────────────────────────────────


def test_discovery_keeps_woocommerce_product_pages(monkeypatch):
    mapped = [
        f"{BASE}/product/focus-blend/",
        f"{BASE}/product-category/brand/house-brand/",
        f"{BASE}/product/gut-blend/",
        f"{BASE}/shop/",
        f"{BASE}/product/focus-blend",
        "https://other.example/product/elsewhere/",
        f"{BASE}/product/energy-caps/?attribute_size=30",
    ]
    monkeypatch.setattr(researcher, "firecrawl_map_urls", lambda url, limit=200: mapped)

    assert discover_product_urls_smart(BASE, limit=12) == [
        f"{BASE}/product/focus-blend",
        f"{BASE}/product/gut-blend",
        f"{BASE}/product/energy-caps",
    ]


def test_discovery_still_handles_shopify(monkeypatch):
    mapped = [
        f"{BASE}/products",
        f"{BASE}/products/a",
        f"{BASE}/collections/all/products/b",
        f"{BASE}/pages/about",
    ]
    monkeypatch.setattr(researcher, "firecrawl_map_urls", lambda url, limit=200: mapped)

    assert discover_product_urls_smart(BASE) == [
        f"{BASE}/products/a",
        f"{BASE}/collections/all/products/b",
    ]


def test_discovery_accepts_the_www_spelling_of_the_same_site(monkeypatch):
    mapped = [
        "https://www.shop.example/product/focus-blend/",
        "https://notshop.example/product/elsewhere/",
        "https://[broken/product/x/",
    ]
    monkeypatch.setattr(researcher, "firecrawl_map_urls", lambda url, limit=200: mapped)

    assert discover_product_urls_smart("https://Shop.Example") == [
        "https://www.shop.example/product/focus-blend"
    ]


def test_discovery_respects_limit_and_empty_map(monkeypatch):
    mapped = [f"{BASE}/product/p-{i}/" for i in range(5)]
    monkeypatch.setattr(researcher, "firecrawl_map_urls", lambda url, limit=200: mapped)
    assert discover_product_urls_smart(BASE, limit=2) == [
        f"{BASE}/product/p-0",
        f"{BASE}/product/p-1",
    ]

    monkeypatch.setattr(researcher, "firecrawl_map_urls", lambda url, limit=200: [])
    assert discover_product_urls_smart(BASE) == []


# ─── Which product pages get read, and in what order ─────────────────────────


def test_operator_named_pages_come_first_then_bestsellers_then_discovered():
    chosen = select_product_page_urls(
        explicit=[f"{BASE}/product/named/"],
        bestsellers=[f"{BASE}/products/best-1", f"{BASE}/products/best-2"],
        discovered=[f"{BASE}/product/found-1", f"{BASE}/product/found-2"],
    )
    assert chosen == [
        f"{BASE}/product/named/",
        f"{BASE}/products/best-1",
        f"{BASE}/products/best-2",
    ]


def test_named_pages_keep_their_order_and_count_toward_the_cap():
    named = [f"{BASE}/product/n-{i}/" for i in range(MAX_PRODUCT_PAGES + 1)]
    chosen = select_product_page_urls(
        explicit=named, bestsellers=[f"{BASE}/products/best"], discovered=[]
    )
    assert chosen == named[:MAX_PRODUCT_PAGES]


def test_same_page_with_and_without_trailing_slash_is_read_once():
    chosen = select_product_page_urls(
        explicit=[f"{BASE}/product/named/"],
        bestsellers=[],
        discovered=[f"{BASE}/product/named", f"{BASE}/product/other"],
    )
    assert chosen == [f"{BASE}/product/named/", f"{BASE}/product/other"]


def test_a_variant_link_and_its_product_page_are_read_once():
    chosen = select_product_page_urls(
        explicit=[f"{BASE}/products/a?variant=41234567"],
        bestsellers=[],
        discovered=[f"{BASE}/products/a", f"{BASE}/products/b"],
    )
    assert chosen == [f"{BASE}/products/a?variant=41234567", f"{BASE}/products/b"]


def test_without_named_pages_order_is_unchanged():
    chosen = select_product_page_urls(
        explicit=[],
        bestsellers=[f"{BASE}/products/best"],
        discovered=[f"{BASE}/products/best", f"{BASE}/products/found"],
    )
    assert chosen == [f"{BASE}/products/best", f"{BASE}/products/found"]


# ─── Validating operator-named pages ─────────────────────────────────────────


def test_named_pages_on_the_same_site_are_accepted():
    urls = (f"{BASE}/product/a/", " https://www.shop.example/product/b/ ")
    assert validate_product_urls(BASE, urls) == [
        f"{BASE}/product/a/",
        "https://www.shop.example/product/b/",
    ]


def test_host_spelling_does_not_matter_for_the_same_site_check():
    urls = ("https://SHOP.Example/product/a/", "https://shop.example:443/product/b/")
    assert validate_product_urls("shop.example", urls) == list(urls)


def test_no_named_pages_means_no_checks_at_all():
    assert validate_product_urls(BASE, ()) == []
    assert validate_product_urls("https://[broken", ()) == []


@pytest.mark.parametrize(
    "other_site",
    [
        "https://other.example/product/a/",
        "https://evilshop.example/product/a/",
        "https://shop.example.evil.test/product/a/",
    ],
)
def test_named_page_on_another_site_is_rejected(other_site):
    with pytest.raises(ValueError) as excinfo:
        validate_product_urls(BASE, (other_site,))
    message = str(excinfo.value)
    assert other_site in message
    assert "shop.example" in message


def test_every_named_page_is_checked_not_just_the_first():
    with pytest.raises(ValueError, match="other.example"):
        validate_product_urls(BASE, (f"{BASE}/product/a/", "https://other.example/product/b/"))


@pytest.mark.parametrize(
    "bad", ["/product/a/", "shop.example/product/a/", "ftp://shop.example/a", "https://[broken/a"]
)
def test_named_page_must_be_a_full_web_address(bad):
    with pytest.raises(ValueError, match="http"):
        validate_product_urls(BASE, (bad,))


def test_naming_more_pages_than_the_cap_is_rejected():
    too_many = tuple(f"{BASE}/product/n-{i}/" for i in range(MAX_PRODUCT_PAGES + 1))
    with pytest.raises(ValueError, match=f"at most {MAX_PRODUCT_PAGES}"):
        validate_product_urls(BASE, too_many)


def test_a_broken_brand_url_is_reported_as_such():
    with pytest.raises(ValueError, match="--url"):
        validate_product_urls("https://[broken", (f"{BASE}/product/a/",))


# ─── Pages that redirect are still found ─────────────────────────────────────


def test_fetch_pages_finds_pages_that_redirect_to_a_trailing_slash(monkeypatch):
    scraped = {
        f"{BASE}/shop/": "shop page",
        f"{BASE}/about/": "about page",
        f"{BASE}/": "home",
    }
    monkeypatch.setattr(researcher, "firecrawl_scrape_markdown", lambda urls, **kw: scraped)

    pages = fetch_pages(BASE, paths=["/", "/about", "/shop", "/faq"])

    assert list(pages.items()) == [
        (f"{BASE}/", "home"),
        (f"{BASE}/about", "about page"),
        (f"{BASE}/shop", "shop page"),
    ]


def test_fetch_product_pages_finds_redirected_pages_in_the_order_asked(monkeypatch):
    scraped = {
        "https://www.shop.example/product/b/": "product b",
        f"{BASE}/product/a/": "product a",
    }
    monkeypatch.setattr(researcher, "firecrawl_scrape_markdown", lambda urls, **kw: scraped)

    pages = fetch_product_pages([f"{BASE}/product/a", f"{BASE}/product/b"])

    assert list(pages.items()) == [
        (f"{BASE}/product/a", "product a"),
        (f"{BASE}/product/b", "product b"),
    ]


def test_a_page_that_redirected_somewhere_else_is_not_matched(monkeypatch):
    scraped = {
        f"{BASE}/product/a/": "product a",
        f"{BASE}/robot-check/?r=%2Fproduct%2Fb%2F": "Checking your browser",
        f"{BASE}/product/c/?step=2": "a different page on the same path",
    }
    monkeypatch.setattr(researcher, "firecrawl_scrape_markdown", lambda urls, **kw: scraped)

    pages = fetch_product_pages(
        [f"{BASE}/product/a/", f"{BASE}/product/b/", f"{BASE}/product/c/"]
    )

    assert pages == {f"{BASE}/product/a/": "product a"}


def test_empty_or_unparseable_scraper_entries_do_not_hide_a_real_page(monkeypatch):
    scraped = {
        f"{BASE}/about": "",
        "https://[broken/about/": "junk",
        f"{BASE}/about/": "about page",
    }
    monkeypatch.setattr(researcher, "firecrawl_scrape_markdown", lambda urls, **kw: scraped)

    assert fetch_pages(BASE, paths=["/about"]) == {f"{BASE}/about": "about page"}


# ─── The CLI option ──────────────────────────────────────────────────────────


def _fail_if_called(*args, **kwargs):
    raise AssertionError("this must not run")


def test_research_rejects_a_product_url_on_another_site_before_doing_anything(
    monkeypatch, tmp_path
):
    from cli import cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(researcher, "fetch_pages", _fail_if_called)
    monkeypatch.setattr(researcher, "firecrawl_map_urls", _fail_if_called)

    res = CliRunner().invoke(
        cli,
        ["research", "--client", "acme", "--url", BASE,
         "--product-url", f"{BASE}/product/a/",
         "--product-url", "https://other.example/product/b/"],
    )

    assert res.exit_code != 0
    assert "--product-url" in res.output
    assert "other.example" in res.output
    assert not (tmp_path / "clients").exists()


class _StopAfterProductFetchError(Exception):
    pass


INTAKE = "\n".join(["Acme", "all", "full brand", "skip", "skip", "skip", "skip"]) + "\n"


def _patch_site(monkeypatch, tmp_path, *, bestseller_urls=()):
    """A store whose pages are all canned, with three discovered product pages."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "clients" / "acme").mkdir(parents=True)
    monkeypatch.setattr(researcher, "fetch_pages", lambda url: {f"{BASE}/": "home"})
    monkeypatch.setattr(researcher, "fetch_homepage_html", lambda url: "<html></html>")
    monkeypatch.setattr(
        researcher,
        "discover_product_urls_smart",
        lambda url, limit=8: [f"{BASE}/product/found-{i}" for i in range(3)],
    )
    cards = [ProductCard(name=f"Best {i}", url=u) for i, u in enumerate(bestseller_urls)]
    monkeypatch.setattr(researcher, "is_shopify_site", lambda html: bool(cards))
    monkeypatch.setattr(
        researcher, "fetch_shopify_bestsellers", lambda url, page_count=3: [(url, "<html>")]
    )
    monkeypatch.setattr(researcher, "parse_shopify_product_cards", lambda html, url: cards)


def test_research_reads_named_then_bestseller_then_discovered_pages(monkeypatch, tmp_path):
    from cli import cli

    _patch_site(monkeypatch, tmp_path, bestseller_urls=[f"{BASE}/products/best"])
    requested: list[str] = []

    def record_and_stop(urls):
        requested.extend(urls)
        raise _StopAfterProductFetchError

    monkeypatch.setattr(researcher, "fetch_product_pages", record_and_stop)

    res = CliRunner().invoke(
        cli,
        ["research", "--client", "acme", "--url", BASE, "--auto",
         "--product-url", f"{BASE}/product/named/"],
        input=INTAKE,
    )

    assert isinstance(res.exception, _StopAfterProductFetchError), res.output
    assert requested == [
        f"{BASE}/product/named/",
        f"{BASE}/products/best",
        f"{BASE}/product/found-0",
    ]


def test_research_stops_when_a_named_page_could_not_be_read(monkeypatch, tmp_path):
    from cli import cli

    _patch_site(monkeypatch, tmp_path)
    monkeypatch.setattr(
        researcher,
        "fetch_product_pages",
        lambda urls: {u: "page" for u in urls if "named" not in u},
    )
    monkeypatch.setattr(researcher, "run_brand_intake", _fail_if_called)

    res = CliRunner().invoke(
        cli,
        ["research", "--client", "acme", "--url", BASE, "--auto",
         "--product-url", f"{BASE}/product/named/"],
        input=INTAKE,
    )

    assert res.exit_code == 1, res.output
    assert f"{BASE}/product/named/" in res.output
    assert "--product-url" in res.output
    assert not (tmp_path / "clients" / "acme" / "brand-context.md").exists()


def test_onboard_passes_product_urls_to_research(monkeypatch):
    import cli as cli_module

    seen: dict = {}
    monkeypatch.setattr(cli_module.research, "callback", lambda **kwargs: seen.update(kwargs))

    res = CliRunner().invoke(
        cli_module.cli,
        ["onboard", "--client", "acme", "--url", BASE,
         "--product-url", f"{BASE}/product/named/",
         "--skip", "product-deep-dive", "--skip", "personas",
         "--skip", "offers", "--skip", "strategy-matrix"],
    )

    assert res.exit_code == 0, res.output
    assert seen["product_url"] == (f"{BASE}/product/named/",)
    assert seen["url"] == BASE


def test_onboard_rejects_a_bad_product_url_before_any_stage(monkeypatch):
    import cli as cli_module

    monkeypatch.setattr(cli_module.research, "callback", _fail_if_called)

    res = CliRunner().invoke(
        cli_module.cli,
        ["onboard", "--client", "acme", "--url", BASE,
         "--product-url", "https://other.example/product/a/",
         "--skip", "research", "--skip", "product-deep-dive", "--skip", "personas",
         "--skip", "offers", "--skip", "strategy-matrix"],
    )

    assert res.exit_code != 0
    assert "--product-url" in res.output
    assert "other.example" in res.output
