"""Tests for the Sneakerjagers parsing helpers (pure functions, no network)."""

from sneaker_aggregator.sources.sneakerjagers import (
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
