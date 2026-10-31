"""Spec-level tests for the owner-authoritative catalog data (no database, no Django models)."""

from decimal import Decimal

import pytest

from apps.catalog import owner_spec as S

D = Decimal
P = S.BY_CODE


def color(code, name):
    return next(c for c in P[code].colors if c.name == name)


def test_exactly_13_products_with_unique_target_codes():
    assert [p.code for p in S.SPECS] == [f"{n:02d}" for n in range(1, 14)]
    assert len({p.code for p in S.SPECS}) == 13


def test_persian_text_is_stored_as_real_unicode_not_mojibake():
    assert P["01"].name == "\u067e\u06cc\u0631\u0627\u0647\u0646 \u0641\u0648\u062a\u0631"
    assert S.STRETCH == "\u06a9\u0634"
    assert P["07"].colors[1].name == "\u0633\u0631\u0645\u0647\u200c\u0627\u06cc"


def test_totals_match_the_previous_reconciliation_counts():
    rows = [(p, c, s) for p in S.SPECS for c in p.colors for s in c.stock]
    assert len(rows) == 76
    assert sum(1 for p, c, s in rows if c.stock[s] == 0) == 32
    supplied = 0
    for p in S.SPECS:
        if p.requirement == "free":
            continue
        if any(c.measurements is not None for c in p.colors):
            for c in p.colors:
                supplied += sum(v is not None for t in c.measurements.values() for v in t.values())
        else:
            supplied += sum(v is not None for t in p.shared.values() for v in t.values())
    assert supplied == 150


@pytest.mark.parametrize(
    "code,price,category",
    [
        ("01", 5_890_000, "پیراهن"), ("02", 5_298_000, "دورس"),
        ("03", 5_298_000, "دورس"), ("04", 5_298_000, "دورس"),
        ("05", 3_360_000, "بافت"), ("06", 2_690_000, "بافت"),
        ("07", 7_680_000, "هودی"), ("08", 5_298_000, "جکت"),
        ("09", 6_490_000, "جکت چرم"), ("10", 4_980_000, "جاگر"),
        ("11", 4_980_000, "جاگر"), ("12", 3_950_000, "شلوار جین"),
        ("13", 3_890_000, "شلوار پارچه ای"),
    ],
)
def test_price_and_category(code, price, category):
    assert P[code].price == price and P[code].category == category


def test_combined_colors_are_single_options():
    for code in ("02", "03", "04"):
        assert len(P[code].colors) == 1 and " " in P[code].colors[0].name


def test_product_02_missing_sizes_stay_missing():
    p, c = P["02"], P["02"].colors[0]
    assert S.measurements_for(p, c, "M") == {"shoulder": None, "chest": None, "length": None}
    assert S.measurements_for(p, c, "XXXL") == {"shoulder": None, "chest": None, "length": None}
    assert S.measurements_for(p, c, "XXL") == {"shoulder": D(60), "chest": D(64), "length": D(69)}


@pytest.mark.parametrize("code", ["03", "04"])
def test_products_03_04_xxl_has_stock_but_is_not_purchasable(code):
    p, c = P[code], P[code].colors[0]
    assert c.stock["XXL"] == 1
    assert S.measurements_for(p, c, "XXL") == {"shoulder": None, "chest": None, "length": None}
    assert not S.is_purchasable(p, c, "XXL")
    assert S.is_purchasable(p, c, "L") and S.is_purchasable(p, c, "XL")


def test_products_05_06_free_size_purchasable_when_in_stock():
    assert {s for c in P["05"].colors for s in c.stock} == {"FREE"}
    assert [c.stock["FREE"] for c in P["05"].colors] == [2, 1]
    assert [c.stock["FREE"] for c in P["06"].colors] == [2, 2, 2]
    assert all(S.is_purchasable(P[k], c, "FREE") for k in ("05", "06") for c in P[k].colors)


def test_product_07_hoodie_stock_and_shared_measurements():
    p = P["07"]
    black, navy = p.colors
    assert black.stock == {"M": 1, "L": 0, "XL": 1, "XXL": 0, "XXXL": 0}
    assert navy.stock == {"M": 0, "L": 1, "XL": 1, "XXL": 0, "XXXL": 0}
    assert S.measurements_for(p, black, "M") == S.measurements_for(p, navy, "M")
    assert S.measurements_for(p, navy, "XL") == {"shoulder": D("66"), "chest": D("73.5"), "length": D("69.5")}
    assert S.measurements_for(p, black, "M")["shoulder"] == D("60.5")


def test_product_08_is_a_jacket_not_a_shirt():
    p = P["08"]
    assert p.category_slug_hint == "jackets" and p.category_slug_hint != "shirts"
    light, charcoal = p.colors
    assert light.stock["XXL"] == 1 and charcoal.stock["XL"] == 1
    assert sum(light.stock.values()) == 1 and sum(charcoal.stock.values()) == 1
    assert S.measurements_for(p, charcoal, "XL") == {"shoulder": D(56), "chest": D(62), "length": D(64)}
    assert S.is_purchasable(p, light, "XXL") and S.is_purchasable(p, charcoal, "XL")


def test_product_09_is_the_leather_jacket_category():
    p = P["09"]
    assert p.category_slug_hint == "leather-jackets"
    assert p.category == "جکت چرم"
    assert S.measurements_for(p, p.colors[0], "XL") == {"shoulder": D("57.5"), "chest": D("59.5"), "length": D("61.5")}


def test_product_10_keeps_stretch_text_and_has_no_unit():
    p = P["10"]
    assert p.unit is None
    black, gray = p.colors
    assert black.stock == {"L": 1, "XL": 1, "XXL": 1} and gray.stock == {"L": 1, "XL": 0, "XXL": 1}
    for size, hip in (("L", 50), ("XL", 52), ("XXL", 56)):
        m = S.measurements_for(p, black, size)
        assert m["waist"] == S.STRETCH and isinstance(m["waist"], str)
        assert m == {"waist": S.STRETCH, "hip": D(hip), "inseam": D(74), "rise": D(41), "hem": D(16), "total_length": D(100)}
    assert S.measurements_for(p, gray, "XL")["hip"] == D(52)
    assert not S.is_purchasable(p, gray, "XL")


def test_product_11_rise_is_exactly_98_5():
    p, c = P["11"], P["11"].colors[0]
    assert p.unit is None and c.stock == {"M": 1}
    m = S.measurements_for(p, c, "M")
    assert m["rise"] == D("98.5") and str(m["rise"]) == "98.5"
    assert m == {"waist": S.STRETCH, "hip": D(48), "inseam": D("74.5"), "rise": D("98.5"), "hem": D("25.5"), "total_length": D("107.5")}


def test_product_12_measurements_are_color_specific():
    p = P["12"]
    navy, charcoal = p.colors
    assert p.shared == {} and navy.measurements is not None and charcoal.measurements is not None
    assert S.measurements_for(p, navy, "34")["hip"] == D(55)
    assert S.measurements_for(p, charcoal, "34")["hip"] == D("52.5")
    assert S.measurements_for(p, navy, "34")["inseam"] == D(83)
    assert S.measurements_for(p, charcoal, "34")["inseam"] == D(77)


def test_product_12_stock_and_missing_values_stay_missing_not_zero():
    p = P["12"]
    navy, charcoal = p.colors
    assert navy.stock == {"31": 1, "32": 0, "33": 0, "34": 1, "36": 1, "38": 0}
    assert charcoal.stock == {"31": 0, "32": 1, "33": 1, "34": 1, "36": 0, "38": 0}
    assert S.measurements_for(p, navy, "32")["inseam"] is None
    assert S.measurements_for(p, navy, "32")["total_length"] is None
    assert S.measurements_for(p, navy, "33")["total_length"] is None
    assert S.measurements_for(p, charcoal, "31")["total_length"] is None
    assert S.measurements_for(p, charcoal, "36")["total_length"] is None
    for color in (navy, charcoal):
        for size in color.stock:
            assert 0 not in S.measurements_for(p, color, size).values()


def test_product_12_size_38_only_hem_and_is_not_purchasable():
    p = P["12"]
    for color in p.colors:
        m = S.measurements_for(p, color, "38")
        assert m["hem"] == D(22)
        assert [key for key, value in m.items() if value is None] == ["waist", "hip", "inseam", "rise", "total_length"]
        assert color.stock["38"] == 0 and not S.is_purchasable(p, color, "38")


def test_product_12_purchasable_matrix():
    p = P["12"]
    navy, charcoal = p.colors
    assert {s for s in navy.stock if S.is_purchasable(p, navy, s)} == {"31", "34", "36"}
    assert {s for s in charcoal.stock if S.is_purchasable(p, charcoal, s)} == {"32", "33", "34"}


def test_product_13_waist_is_exactly_34_for_both_sizes():
    p, c = P["13"], P["13"].colors[0]
    assert p.unit is None and c.stock == {"32": 1, "33": 1}
    assert S.measurements_for(p, c, "32") == {"waist": D(34), "hip": D(49), "inseam": D(77), "rise": D(39), "hem": D(21), "total_length": D(105)}
    assert S.measurements_for(p, c, "33") == {"waist": D(34), "hip": D(50), "inseam": D(77), "rise": D(40), "hem": D(23), "total_length": D(105)}


def test_units_are_cm_only_for_products_01_to_09():
    assert [p.unit for p in S.SPECS if p.requirement != "free"] == ["cm"] * 7 + [None] * 4
    assert P["10"].unit is P["11"].unit is P["12"].unit is P["13"].unit is None


def test_every_zero_stock_row_is_unpurchasable_and_every_blocked_in_stock_row_is_known():
    blocked = []
    for product in S.SPECS:
        for color in product.colors:
            for size, quantity in color.stock.items():
                if quantity == 0:
                    assert not S.is_purchasable(product, color, size)
                elif not S.is_purchasable(product, color, size):
                    blocked.append((product.code, color.name, size))
    assert [(code, size) for code, _name, size in blocked] == [("03", "XXL"), ("04", "XXL")]
