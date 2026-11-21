import bisect
import itertools
import math
import random
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

Row = dict[str, Any]

START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 12, 31)

REGIONS: dict[str, list[tuple[str, str]]] = {
    "North America": [
        ("New York", "United States"),
        ("Chicago", "United States"),
        ("Austin", "United States"),
        ("Seattle", "United States"),
        ("Toronto", "Canada"),
        ("Vancouver", "Canada"),
    ],
    "Europe": [
        ("London", "United Kingdom"),
        ("Manchester", "United Kingdom"),
        ("Berlin", "Germany"),
        ("Munich", "Germany"),
        ("Paris", "France"),
        ("Madrid", "Spain"),
        ("Amsterdam", "Netherlands"),
    ],
    "Asia Pacific": [
        ("Singapore", "Singapore"),
        ("Sydney", "Australia"),
        ("Melbourne", "Australia"),
        ("Tokyo", "Japan"),
        ("Bengaluru", "India"),
        ("Mumbai", "India"),
    ],
    "Middle East": [
        ("Dubai", "United Arab Emirates"),
        ("Abu Dhabi", "United Arab Emirates"),
        ("Riyadh", "Saudi Arabia"),
        ("Doha", "Qatar"),
    ],
    "Latin America": [
        ("Sao Paulo", "Brazil"),
        ("Mexico City", "Mexico"),
        ("Buenos Aires", "Argentina"),
        ("Bogota", "Colombia"),
    ],
    "Africa": [
        ("Lagos", "Nigeria"),
        ("Nairobi", "Kenya"),
        ("Cape Town", "South Africa"),
        ("Cairo", "Egypt"),
    ],
}
REGION_WEIGHTS = [0.30, 0.25, 0.20, 0.10, 0.10, 0.05]

FIRST_NAMES = (
    "James Mary Robert Patricia John Jennifer Michael Linda David Elizabeth William Barbara "
    "Richard Susan Joseph Jessica Thomas Sarah Charles Karen Daniel Lisa Matthew Nancy Anthony "
    "Sandra Mark Ashley Aarav Priya Rohan Ananya Arjun Diya Omar Fatima Ahmed Layla Yusuf Noor "
    "Hiro Yuki Kenji Aiko Wei Mei Lucas Sofia Mateo Valentina Gabriel Camila Liam Emma Noah Olivia "
    "Chidi Amara Kwame Zainab Lars Ingrid Pierre Chloe Hans Greta Diego Lucia"
).split()
LAST_NAMES = (
    "Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez Hernandez Lopez "
    "Wilson Anderson Thomas Taylor Moore Jackson Martin Lee Thompson White Harris Clark Lewis "
    "Walker Hall Young Patel Sharma Reddy Iyer Khan Hassan Ali Rahman Tanaka Sato Suzuki Chen "
    "Wang Li Silva Santos Oliveira Costa Okafor Mensah Mwangi Nkosi Muller Schmidt Dubois Moreau "
    "Rossi Bianchi Jansen Visser Novak Kowalski Haddad Nasser"
).split()

SEGMENTS = (("Consumer", 0.62), ("Small Business", 0.25), ("Corporate", 0.13))

CATALOG: dict[str, dict[str, tuple[float, float, list[str]]]] = {
    "Electronics": {
        "Headphones": (
            39,
            349,
            ["Wireless Headphones", "Noise-Cancelling Earbuds", "Studio Headset"],
        ),
        "Smartphones": (199, 1199, ["Smartphone", "Smartphone Pro", "Smartphone Mini"]),
        "Laptops": (549, 2399, ["Ultrabook", "Gaming Laptop", "Laptop 14", "Laptop 16"]),
        "Tablets": (149, 999, ["Tablet 10", "Tablet Pro 12", "E-Reader"]),
        "Smart Home": (
            25,
            249,
            ["Smart Speaker", "Smart Plug 4-Pack", "Video Doorbell", "Thermostat"],
        ),
        "Cameras": (299, 1899, ["Mirrorless Camera", "Action Camera", "Instant Camera"]),
    },
    "Home & Kitchen": {
        "Cookware": (
            19,
            299,
            ["Cast Iron Skillet", "Nonstick Pan Set", "Dutch Oven", "Knife Block"],
        ),
        "Small Appliances": (29, 499, ["Espresso Machine", "Air Fryer", "Blender", "Stand Mixer"]),
        "Bedding": (25, 249, ["Duvet Cover", "Memory Foam Pillow", "Linen Sheet Set"]),
        "Furniture": (89, 1299, ["Desk Chair", "Standing Desk", "Bookshelf", "Sofa Bed"]),
    },
    "Sports & Outdoors": {
        "Fitness": (15, 899, ["Yoga Mat", "Adjustable Dumbbells", "Rowing Machine", "Kettlebell"]),
        "Camping": (25, 449, ["2-Person Tent", "Sleeping Bag", "Camp Stove", "Headlamp"]),
        "Cycling": (19, 1499, ["Road Bike", "Bike Helmet", "Bike Lights", "Commuter E-Bike"]),
    },
    "Clothing": {
        "Men": (19, 199, ["Oxford Shirt", "Chino Pants", "Wool Sweater", "Rain Jacket"]),
        "Women": (19, 229, ["Linen Dress", "Denim Jacket", "Cashmere Scarf", "Trench Coat"]),
        "Kids": (9, 79, ["Kids Hoodie", "Kids Rain Boots", "Kids Pajama Set"]),
        "Footwear": (39, 249, ["Running Shoes", "Leather Boots", "Trail Sneakers"]),
    },
    "Beauty": {
        "Skincare": (9, 119, ["Vitamin C Serum", "Daily Moisturizer", "Sunscreen SPF 50"]),
        "Haircare": (8, 299, ["Repair Shampoo", "Hair Dryer", "Styling Cream"]),
        "Fragrance": (39, 189, ["Eau de Parfum", "Cologne", "Travel Fragrance Set"]),
    },
    "Books": {
        "Fiction": (9, 35, ["Mystery Novel", "Sci-Fi Novel", "Literary Fiction"]),
        "Non-fiction": (12, 45, ["Business Book", "Cookbook", "History Book", "Biography"]),
        "Children": (6, 25, ["Picture Book", "Activity Book", "Young Adult Novel"]),
    },
    "Toys & Games": {
        "Board Games": (15, 89, ["Strategy Board Game", "Party Game", "Family Card Game"]),
        "Building Sets": (19, 249, ["Building Brick Set", "STEM Robot Kit", "Marble Run"]),
    },
}

BRANDS = (
    "Aurora Lumen Kestrel Brightline Oakridge Nimbus Vantage Halcyon Ember Solace Tundra "
    "Meridian Pinecrest Atlas Juniper Harbor"
).split()
MODEL_SUFFIXES = ["", "", " Lite", " Plus", " 2", " X", " Max"]

CATEGORY_SEASON: dict[str, dict[int, float]] = {
    "Toys & Games": {11: 2.2, 12: 3.0},
    "Electronics": {11: 1.8, 12: 1.6},
    "Sports & Outdoors": {5: 1.4, 6: 1.6, 7: 1.6, 8: 1.3, 1: 1.3},
    "Clothing": {3: 1.2, 9: 1.3, 10: 1.3},
    "Beauty": {2: 1.3, 12: 1.4},
}
MONTH_SEASON = {
    1: 0.85,
    2: 0.80,
    3: 0.92,
    4: 0.95,
    5: 1.0,
    6: 1.02,
    7: 0.98,
    8: 1.0,
    9: 0.97,
    10: 1.05,
    11: 1.45,
    12: 1.6,
}

CHANNELS = ("web", "mobile", "store")
PAYMENT_METHODS = ("card", "paypal", "bank_transfer", "gift_card", "cash_on_delivery")


@dataclass(frozen=True)
class SeedConfig:
    seed: int = 42
    customers: int = 4_000
    orders_per_day: float = 26.0
    yearly_growth: float = 0.28


@dataclass
class Dataset:
    regions: list[Row] = field(default_factory=list)
    customers: list[Row] = field(default_factory=list)
    products: list[Row] = field(default_factory=list)
    orders: list[Row] = field(default_factory=list)
    order_items: list[Row] = field(default_factory=list)
    payments: list[Row] = field(default_factory=list)

    def tables(self) -> Iterator[tuple[str, list[Row]]]:
        yield "regions", self.regions
        yield "customers", self.customers
        yield "products", self.products
        yield "orders", self.orders
        yield "order_items", self.order_items
        yield "payments", self.payments


def _weighted(rng: random.Random, options: tuple[tuple[str, float], ...]) -> str:
    return rng.choices([o for o, _ in options], weights=[w for _, w in options])[0]


def _money(value: float) -> float:
    return round(value + 1e-9, 2)


def _price_point(rng: random.Random, low: float, high: float) -> float:
    raw = math.exp(rng.uniform(math.log(low), math.log(high)))
    return float(math.floor(raw)) + 0.99 if raw > 20 else _money(raw)


def _make_regions() -> list[Row]:
    return [{"region_id": i, "name": name} for i, name in enumerate(REGIONS, start=1)]


def _make_customers(rng: random.Random, n: int) -> list[Row]:
    region_names = list(REGIONS)
    signup_start = date(2022, 1, 1)
    signup_span = (END_DATE - timedelta(days=45) - signup_start).days
    rows: list[Row] = []
    seen_emails: set[str] = set()
    for _ in range(n):
        region_idx = rng.choices(range(len(region_names)), weights=REGION_WEIGHTS)[0]
        city, country = rng.choice(REGIONS[region_names[region_idx]])
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        base = f"{first}.{last}".lower()
        email = f"{base}@example.com"
        for suffix in itertools.count(2):
            if email not in seen_emails:
                break
            email = f"{base}{suffix}@example.com"
        seen_emails.add(email)
        # Skew sign-ups towards later dates so the customer base grows over time.
        offset = int(signup_span * (rng.random() ** 0.8))
        rows.append(
            {
                "first_name": first,
                "last_name": last,
                "email": email,
                "city": city,
                "country": country,
                "region_id": region_idx + 1,
                "segment": _weighted(rng, SEGMENTS),
                "signup_date": signup_start + timedelta(days=offset),
            }
        )
    rows.sort(key=lambda r: r["signup_date"])
    for i, row in enumerate(rows, start=1):
        row["customer_id"] = i
    return rows


def _make_products(rng: random.Random) -> list[Row]:
    rows: list[Row] = []
    for category, subcats in CATALOG.items():
        for subcategory, (low, high, names) in subcats.items():
            for base_name in names:
                for brand in rng.sample(BRANDS, k=rng.randint(1, 3)):
                    price = _price_point(rng, low, high)
                    margin = rng.uniform(0.25, 0.55)
                    rows.append(
                        {
                            "product_id": len(rows) + 1,
                            "name": f"{brand} {base_name}{rng.choice(MODEL_SUFFIXES)}",
                            "category": category,
                            "subcategory": subcategory,
                            "brand": brand,
                            "unit_price": price,
                            "unit_cost": _money(price * (1 - margin)),
                        }
                    )
    return rows


def _daily_order_count(rng: random.Random, day: date, cfg: SeedConfig) -> int:
    years = (day - START_DATE).days / 365.25
    trend = (1 + cfg.yearly_growth) ** years
    weekday = 1.12 if day.weekday() >= 5 else 0.96
    promo = 2.4 if day.month == 11 and 24 <= day.day <= 30 else 1.0
    expected = cfg.orders_per_day * trend * MONTH_SEASON[day.month] * weekday * promo
    return max(0, round(rng.gauss(expected, math.sqrt(expected))))


def _order_status(rng: random.Random, day: date) -> str:
    age = (END_DATE - day).days
    if age <= 3:
        return rng.choices(["processing", "shipped"], weights=[0.7, 0.3])[0]
    if age <= 10:
        return rng.choices(["shipped", "delivered", "cancelled"], weights=[0.6, 0.35, 0.05])[0]
    return rng.choices(["delivered", "cancelled", "returned"], weights=[0.88, 0.06, 0.06])[0]


def _channel(rng: random.Random, day: date) -> str:
    mobile_share = 0.26 + 0.12 * (day - START_DATE).days / (END_DATE - START_DATE).days
    return rng.choices(CHANNELS, weights=[0.88 - mobile_share, mobile_share, 0.12])[0]


def _payment_method(rng: random.Random, region_id: int) -> str:
    cod = 0.18 if region_id in (4, 6) else 0.02
    return rng.choices(PAYMENT_METHODS, weights=[0.62, 0.18, 0.08, 0.05, cod])[0]


def generate(cfg: SeedConfig | None = None) -> Dataset:
    cfg = cfg or SeedConfig()
    rng = random.Random(cfg.seed)
    data = Dataset(regions=_make_regions())
    data.customers = _make_customers(rng, cfg.customers)
    data.products = _make_products(rng)

    signups = [c["signup_date"] for c in data.customers]
    # Pareto-ish activity: a minority of customers place most of the orders.
    activity = [rng.paretovariate(1.6) for _ in data.customers]
    cumulative = list(itertools.accumulate(activity))

    popularity = [rng.paretovariate(1.2) for _ in data.products]
    by_category: dict[str, list[int]] = {}
    for idx, p in enumerate(data.products):
        by_category.setdefault(p["category"], []).append(idx)
    categories = list(by_category)

    day = START_DATE
    while day <= END_DATE:
        eligible = bisect.bisect_right(signups, day)
        if eligible == 0:
            day += timedelta(days=1)
            continue
        cat_weights = [CATEGORY_SEASON.get(c, {}).get(day.month, 1.0) for c in categories]
        price_bump = 1.05 if day.year >= 2025 else 1.0
        is_promo = day.month == 11 and 24 <= day.day <= 30

        for _ in range(_daily_order_count(rng, day, cfg)):
            pick = rng.random() * cumulative[eligible - 1]
            customer = data.customers[bisect.bisect_left(cumulative, pick, hi=eligible - 1)]
            order_id = len(data.orders) + 1
            channel = _channel(rng, day)
            status = _order_status(rng, day)

            subtotal = 0.0
            n_items = rng.choices([1, 2, 3, 4, 5], weights=[0.45, 0.28, 0.15, 0.08, 0.04])[0]
            chosen: set[int] = set()
            for _ in range(n_items):
                category = rng.choices(categories, weights=cat_weights)[0]
                pool = by_category[category]
                product_idx = rng.choices(pool, weights=[popularity[i] for i in pool])[0]
                if product_idx in chosen:
                    continue
                chosen.add(product_idx)
                product = data.products[product_idx]
                quantity = rng.choices([1, 2, 3, 4], weights=[0.72, 0.18, 0.07, 0.03])[0]
                if product["unit_price"] > 400:
                    quantity = 1
                discount_rate = 0.35 if is_promo else 0.12
                discount = (
                    rng.choice([0.05, 0.1, 0.15, 0.2, 0.25])
                    if rng.random() < discount_rate
                    else 0.0
                )
                unit_price = _money(product["unit_price"] * price_bump)
                subtotal += quantity * unit_price * (1 - discount)
                data.order_items.append(
                    {
                        "order_item_id": len(data.order_items) + 1,
                        "order_id": order_id,
                        "product_id": product["product_id"],
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "discount": discount,
                    }
                )

            shipping = (
                0.0 if channel == "store" or subtotal >= 75 else rng.choice([4.99, 7.99, 12.99])
            )
            data.orders.append(
                {
                    "order_id": order_id,
                    "customer_id": customer["customer_id"],
                    "order_date": day,
                    "status": status,
                    "channel": channel,
                    "shipping_cost": shipping,
                }
            )
            _add_payments(
                rng, data, order_id, day, status, customer["region_id"], subtotal + shipping
            )
        day += timedelta(days=1)
    return data


def _add_payments(
    rng: random.Random,
    data: Dataset,
    order_id: int,
    day: date,
    status: str,
    region_id: int,
    total: float,
) -> None:
    if status == "cancelled" and rng.random() < 0.5:
        return
    method = _payment_method(rng, region_id)
    paid_on = day + timedelta(days=rng.choice([0, 0, 0, 1, 2]))
    amount = _money(total)
    if rng.random() < 0.03:
        data.payments.append(
            {
                "payment_id": len(data.payments) + 1,
                "order_id": order_id,
                "payment_date": paid_on,
                "method": method,
                "amount": amount,
                "status": "failed",
            }
        )
    final_status = "refunded" if status in ("cancelled", "returned") else "completed"
    data.payments.append(
        {
            "payment_id": len(data.payments) + 1,
            "order_id": order_id,
            "payment_date": paid_on,
            "method": method,
            "amount": amount,
            "status": final_status,
        }
    )
