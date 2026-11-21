from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
)

metadata = MetaData()

regions = Table(
    "regions",
    metadata,
    Column("region_id", Integer, primary_key=True),
    Column("name", String(40), nullable=False, unique=True),
)

customers = Table(
    "customers",
    metadata,
    Column("customer_id", Integer, primary_key=True),
    Column("first_name", String(60), nullable=False),
    Column("last_name", String(60), nullable=False),
    Column("email", String(120), nullable=False, unique=True),
    Column("city", String(60), nullable=False),
    Column("country", String(60), nullable=False),
    Column("region_id", Integer, ForeignKey("regions.region_id"), nullable=False),
    Column("segment", String(20), nullable=False),
    Column("signup_date", Date, nullable=False),
)

products = Table(
    "products",
    metadata,
    Column("product_id", Integer, primary_key=True),
    Column("name", String(120), nullable=False),
    Column("category", String(40), nullable=False),
    Column("subcategory", String(40), nullable=False),
    Column("brand", String(40), nullable=False),
    Column("unit_price", Numeric(10, 2), nullable=False),
    Column("unit_cost", Numeric(10, 2), nullable=False),
)

orders = Table(
    "orders",
    metadata,
    Column("order_id", Integer, primary_key=True),
    Column("customer_id", Integer, ForeignKey("customers.customer_id"), nullable=False),
    Column("order_date", Date, nullable=False),
    Column("status", String(20), nullable=False),
    Column("channel", String(20), nullable=False),
    Column("shipping_cost", Numeric(10, 2), nullable=False),
    Index("ix_orders_order_date", "order_date"),
    Index("ix_orders_customer_id", "customer_id"),
)

order_items = Table(
    "order_items",
    metadata,
    Column("order_item_id", Integer, primary_key=True),
    Column("order_id", Integer, ForeignKey("orders.order_id"), nullable=False),
    Column("product_id", Integer, ForeignKey("products.product_id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("unit_price", Numeric(10, 2), nullable=False),
    Column("discount", Numeric(4, 2), nullable=False),
    Index("ix_order_items_order_id", "order_id"),
    Index("ix_order_items_product_id", "product_id"),
)

payments = Table(
    "payments",
    metadata,
    Column("payment_id", Integer, primary_key=True),
    Column("order_id", Integer, ForeignKey("orders.order_id"), nullable=False),
    Column("payment_date", Date, nullable=False),
    Column("method", String(20), nullable=False),
    Column("amount", Numeric(10, 2), nullable=False),
    Column("status", String(20), nullable=False),
    Index("ix_payments_order_id", "order_id"),
)

LOAD_ORDER = (regions, customers, products, orders, order_items, payments)
