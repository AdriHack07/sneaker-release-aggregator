"""Tests for the Sneakerjagers parsing helpers (pure functions, no network)."""

from sneaker_aggregator.sources.sneakerjagers import (
    SneakerjagersClient,
    parse_links,
    stylecode_from_slug,
)


# ----- stylecode_from_slug ----------------------------------------------------


def test_stylecode_extracted_and_uppercased():
    assert stylecode_from_slug(
        "a-ma-maniere-x-nike-pegasus-premium-sp-burgundy-crush-im0701-001"
    ) == "IM0701-001"
    assert stylecode_from_slug("nike-air-rift-2-black-iq8006-002") == "IQ8006-002"


def test_stylecode_none_when_absent():
    assert stylecode_from_slug("some-slug-without-a-code") is None
    assert stylecode_from_slug("") is None


# ----- parse_links ------------------------------------------------------------


def _item():
    return {
        "links_raffles": [
            {"id": 111, "shop": "Footpatrol", "prices": {"eur": 205, "native": 175}},
            {"id": 222, "shop": "size?", "prices": {"eur": 200}},
            {"id": 333, "shop": "Footpatrol", "prices": {"eur": 190}},  # cheaper dup
            {"id": 444, "shop": None, "prices": {"eur": 100}},          # no shop -> skip
        ],
        "links_webshops": [
            {"id": 555, "shop": "Nike", "prices": {"eur": 180}},
        ],
    }


def test_parse_links_builds_go_urls_and_eur_price():
    stk = parse_links(_item(), include_webshops=True)
    by = {s.shop_name: s for s in stk}
    assert by["size?"].link == "https://sneakerjagers.com/en/go/222"
    assert by["size?"].price == 200.0
    assert by["Nike"].price == 180.0


def test_parse_links_dedupes_keeping_cheapest():
    stk = parse_links(_item(), include_webshops=False)
    fp = [s for s in stk if s.shop_name == "Footpatrol"]
    assert len(fp) == 1
    assert fp[0].price == 190.0  # cheaper of 205/190
    assert fp[0].link == "https://sneakerjagers.com/en/go/333"


def test_parse_links_skips_entries_without_shop_or_id():
    stk = parse_links(_item(), include_webshops=True)
    assert all(s.shop_name for s in stk)
    assert "https://sneakerjagers.com/en/go/444" not in {s.link for s in stk}


def test_parse_links_excludes_webshops_when_disabled():
    names = {s.shop_name for s in parse_links(_item(), include_webshops=False)}
    assert "Nike" not in names
    assert "Footpatrol" in names


def test_parse_links_sorted_cheapest_first():
    stk = parse_links(_item(), include_webshops=True)
    prices = [s.price for s in stk if s.price is not None]
    assert prices == sorted(prices)


def test_parse_links_empty_item():
    assert parse_links({}, include_webshops=True) == []


def test_parse_links_tags_raffles_vs_webshops():
    item = {
        "links_raffles": [{"id": 1, "shop": "Footpatrol", "prices": {"eur": 200}}],
        "links_webshops": [{"id": 2, "shop": "Nike", "prices": {"eur": 180}}],
    }
    by = {s.shop_name: s for s in parse_links(item, include_webshops=True)}
    assert by["Footpatrol"].is_raffle is True
    assert by["Nike"].is_raffle is False


# ----- find_by_sku / find_by_name (lookup logic, search stubbed) --------------


class _StubClient(SneakerjagersClient):
    """A client whose only network call (_search) is replaced by canned results."""

    def __init__(self, results):
        # Skip the httpx.Client setup in __init__ — we never touch the network.
        self._results = results
        self.calls = []

    def _search(self, query):  # type: ignore[override]
        self.calls.append(query)
        return self._results.get(query, [])


def test_find_by_sku_prefers_stylecode_match():
    items = [
        {"slug": "some-other-shoe", "id": 1},
        {"slug": "air-jordan-1-retro-high-og-lost-found-dz5485-612", "id": 2},
    ]
    c = _StubClient({"DZ5485-612": items})
    assert c.find_by_sku("DZ5485-612") == (
        "air-jordan-1-retro-high-og-lost-found-dz5485-612",
        "2",
    )


def test_find_by_sku_returns_none_when_ambiguous_and_uncoded():
    # >5 hits, none carrying the stylecode -> refuse to guess.
    items = [{"slug": f"shoe-{i}", "id": i} for i in range(6)]
    c = _StubClient({"XX0000-000": items})
    assert c.find_by_sku("XX0000-000") is None


def test_find_by_name_fallback_matches_on_stylecode():
    # SKU search misses; name search returns the coded slug.
    name = "Air Jordan 1 Retro High OG Lost and Found"
    items = [{"slug": "air-jordan-1-retro-high-og-lost-found-dz5485-612", "id": 9}]
    c = _StubClient({name: items})  # note: SKU query not present -> empty
    assert c.find_by_sku("DZ5485-612") is None
    assert c.find_by_name(name, "DZ5485-612") == (
        "air-jordan-1-retro-high-og-lost-found-dz5485-612",
        "9",
    )


def test_get_stockists_falls_back_to_name(monkeypatch):
    name = "Air Max 90 Neon"
    items = [{"slug": "nike-air-max-90-neon-iq0289-010", "id": 5}]
    c = _StubClient({name: items})  # SKU query empty -> triggers name fallback
    captured = {}

    def fake_get_raffles(slug, sid, include_webshops=True):
        captured["args"] = (slug, sid)
        return ["sentinel"]

    monkeypatch.setattr(c, "get_raffles", fake_get_raffles)
    out = c.get_stockists_for_sku("IQ0289-010", name=name)
    assert out == ["sentinel"]
    assert captured["args"] == ("nike-air-max-90-neon-iq0289-010", "5")


def test_find_by_name_empty_name_returns_none():
    c = _StubClient({})
    assert c.find_by_name("", "DZ5485-612") is None
