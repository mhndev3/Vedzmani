"""Owner-authoritative target catalog (13 products), as DATA ONLY.

Source: the owner's complete product specifications in the 2026-10-31 catalog-repair handoff.
This module imports nothing from Django or from the catalog models on purpose: it is the single,
machine-readable statement of what the catalog SHOULD contain, so a future import/update procedure
and the tests can both be checked against the same facts.

Conventions
- Prices are whole toman (Decimal, never float).
- None means NOT SUPPLIED by the owner. It is never zero and must never be displayed as a value.
- Measurement values are Decimal (exact, no rounding/normalising) or the literal text "کش".
- unit=None means the owner did not supply a unit: nothing may label these values as cm.
- Zero-stock sizes are part of the spec on purpose; they must stay represented (never deleted).
- shared measurements apply to every color of the product (product 07); ColorSpec.measurements
  overrides them per color (product 12 must stay color-specific).
- category_slug_hint is what the production snapshot (prod DB dump) shows for that Persian category
  name; it is a lookup hint only. The category must be verified before use, never trusted blindly.
"""

from dataclasses import dataclass, field
from decimal import Decimal

STRETCH = "کش"

TOP_KINDS = ("shoulder", "chest", "length")
BOTTOM_KINDS = ("waist", "hip", "inseam", "rise", "hem", "total_length")
REQUIRED_KINDS = {"top": TOP_KINDS, "bottom": BOTTOM_KINDS, "free": ()}
TOP_SIZES = ("M", "L", "XL", "XXL", "XXXL")


def _d(value):
    return Decimal(str(value))


def _top(**by_size):
    return {s: dict(zip(TOP_KINDS, (_d(v) for v in vals))) for s, vals in by_size.items()}


def _bottom(**by_size):
    return {
        s: dict(zip(BOTTOM_KINDS, (v if v == STRETCH or v is None else _d(v) for v in vals)))
        for s, vals in by_size.items()
    }


@dataclass(frozen=True)
class ColorSpec:
    name: str
    stock: dict
    measurements: dict | None = None


@dataclass(frozen=True)
class ProductSpec:
    code: str
    name: str
    category: str
    category_slug_hint: str
    price: int
    requirement: str
    unit: str | None
    colors: tuple
    shared: dict = field(default_factory=dict)


def _stock(**q):
    return dict(q)


SPECS = (
    ProductSpec("01", "پیراهن فوتر", "پیراهن", "shirts", 5_890_000, "top", "cm",
        (ColorSpec("مشکی", _stock(M=1, L=1, XL=1, XXL=0, XXXL=0)),
         ColorSpec("طوسی", _stock(M=1, L=1, XL=1, XXL=1, XXXL=1))),
        shared=_top(M=(52, 56, 64), L=(53, 59, 64), XL=(56, 62, 64), XXL=(57, 64, 67), XXXL=(60, 66, 69))),
    ProductSpec("02", "دورس دو رنگ", "دورس", "sweatshirts", 5_298_000, "top", "cm",
        (ColorSpec("سبز سفید", _stock(M=0, L=1, XL=1, XXL=1, XXXL=0)),),
        shared=_top(L=(48, 54, 64), XL=(54, 58, 68), XXL=(60, 64, 69))),
    ProductSpec("03", "دورس دو رنگ", "دورس", "sweatshirts", 5_298_000, "top", "cm",
        (ColorSpec("طوسی مشکی", _stock(M=0, L=1, XL=1, XXL=1, XXXL=0)),),
        shared=_top(L=(48, 54, 64), XL=(54, 58, 68))),
    ProductSpec("04", "دورس دو رنگ", "دورس", "sweatshirts", 5_298_000, "top", "cm",
        (ColorSpec("مشکی قرمز", _stock(M=0, L=1, XL=1, XXL=1, XXXL=0)),),
        shared=_top(L=(48, 54, 64), XL=(54, 58, 68))),
    ProductSpec("05", "بافت بیسیک یقه گرد", "بافت", "knitwear", 3_360_000, "free", None,
        (ColorSpec("آبی آسمانی", _stock(FREE=2)), ColorSpec("مشکی", _stock(FREE=1)))),
    ProductSpec("06", "بافت بیسیک یقه دار", "بافت", "knitwear", 2_690_000, "free", None,
        (ColorSpec("سفید", _stock(FREE=2)), ColorSpec("آبی", _stock(FREE=2)), ColorSpec("مشکی", _stock(FREE=2)))),
    ProductSpec("07", "هودی نیم زیپ مندم", "هودی", "hoodies", 7_680_000, "top", "cm",
        (ColorSpec("مشکی", _stock(M=1, L=0, XL=1, XXL=0, XXXL=0)),
         ColorSpec("سرمه‌ای", _stock(M=0, L=1, XL=1, XXL=0, XXXL=0))),
        shared=_top(M=(60.5, 65.5, 63.5), L=(60.5, 67, 67), XL=(66, 73.5, 69.5))),
    ProductSpec("08", "وست جین", "جکت", "jackets", 5_298_000, "top", "cm",
        (ColorSpec("آبی روشن", _stock(M=0, L=0, XL=0, XXL=1, XXXL=0)),
         ColorSpec("ذغالی", _stock(M=0, L=0, XL=1, XXL=0, XXXL=0))),
        shared=_top(XL=(56, 62, 64), XXL=(57, 64, 67))),
    ProductSpec("09", "بامبر جکت چرم زارا", "جکت چرم", "leather-jackets", 6_490_000, "top", "cm",
        (ColorSpec("مشکی", _stock(M=0, L=0, XL=1, XXL=1, XXXL=0)),),
        shared=_top(XL=(57.5, 59.5, 61.5), XXL=(61.5, 65.5, 65.5))),
    ProductSpec("10", "جاگر دمپا کش", "جاگر", "joggers", 4_980_000, "bottom", None,
        (ColorSpec("مشکی", _stock(L=1, XL=1, XXL=1)), ColorSpec("طوسی", _stock(L=1, XL=0, XXL=1))),
        shared=_bottom(L=(STRETCH, 50, 74, 41, 16, 100), XL=(STRETCH, 52, 74, 41, 16, 100), XXL=(STRETCH, 56, 74, 41, 16, 100))),
    ProductSpec("11", "جاگر ESSENTIAL", "جاگر", "joggers", 4_980_000, "bottom", None,
        (ColorSpec("طوسی", _stock(M=1)),),
        shared=_bottom(M=(STRETCH, 48, 74.5, 98.5, 25.5, 107.5))),
    ProductSpec("12", "شلوار جین نیم بگ", "شلوار جین", "jeans", 3_950_000, "bottom", None,
        (ColorSpec("سرمه‌ای", {"31": 1, "32": 0, "33": 0, "34": 1, "36": 1, "38": 0},
            _bottom(**{"31": (40, 49, 49, 40, 22, 114), "32": (40, 49, None, 40, 22, None),
                       "33": (42, 50.5, 76, 40.5, 22, None), "34": (44, 55, 83, 44, 22, 118),
                       "36": (49, 58, 83, 44, 22, 118), "38": (None, None, None, None, 22, None)})),
         ColorSpec("ذغالی", {"31": 0, "32": 1, "33": 1, "34": 1, "36": 0, "38": 0},
            _bottom(**{"31": (40, 49, 49, 40, 22, None), "32": (40, 49, 76, 40, 22, 109.5),
                       "33": (42, 50.5, 76, 40.5, 22, 109.5), "34": (44, 52.5, 77, 44, 22, 109.5),
                       "36": (49, 58, 83, 44, 22, None), "38": (None, None, None, None, 22, None)}))),
    ProductSpec("13", "شلوار پارچه ای مورگان", "شلوار پارچه ای", "trousers", 3_890_000, "bottom", None,
        (ColorSpec("مشکی", {"32": 1, "33": 1}),),
        shared=_bottom(**{"32": (34, 49, 77, 39, 21, 105), "33": (34, 50, 77, 40, 23, 105)})),
)

BY_CODE = {p.code: p for p in SPECS}


def measurements_for(product: ProductSpec, color: ColorSpec, size: str) -> dict:
    table = color.measurements if color.measurements is not None else product.shared
    row = table.get(size, {})
    return {kind: row.get(kind) for kind in REQUIRED_KINDS[product.requirement]}


def is_complete(product: ProductSpec, color: ColorSpec, size: str) -> bool:
    return all(v is not None for v in measurements_for(product, color, size).values())


def is_purchasable(product: ProductSpec, color: ColorSpec, size: str) -> bool:
    return color.stock[size] > 0 and is_complete(product, color, size)
