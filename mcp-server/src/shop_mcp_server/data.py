"""Data layer for loading and querying shop data."""

import os
from html.parser import HTMLParser
from pathlib import Path
import pandas as pd


class _TextExtractor(HTMLParser):
    """Extract visible text from HTML, skipping style/script blocks."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _parse_kba_html(html: str) -> tuple[str, str]:
    """Return (title, plain_text) from an article HTML string."""
    import re

    # Prefer the <h1> as the canonical title
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if h1:
        title = re.sub(r"<[^>]+>", "", h1.group(1)).strip()
    else:
        t = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = t.group(1).strip() if t else ""

    extractor = _TextExtractor()
    extractor.feed(html)
    return title, extractor.get_text()


_KBA_TAGS: dict[str, list[str]] = {
    "returns-and-refunds": ["Returns", "Refunds"],
    "shipping-policy": ["Shipping", "Delivery"],
    "account-management": ["Account", "Security"],
    "payment-methods": ["Payments", "Billing"],
    "product-warranty": ["Warranty", "Products"],
}


class ShopData:
    """Loads and queries shop data from CSV files."""

    def __init__(self, data_dir: str | Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent.parent / "data"
        self.data_dir = Path(data_dir)
        self._load_data()
        self._load_kba()

    def _load_data(self):
        """Load all CSV files into DataFrames."""
        self.customers = pd.read_csv(self.data_dir / "customers.csv")
        self.products = pd.read_csv(self.data_dir / "products.csv")
        self.orders = pd.read_csv(self.data_dir / "orders.csv")
        self.order_items = pd.read_csv(self.data_dir / "order_items.csv")

    def get_product(self, product_id: str) -> dict | None:
        """Get a product by ID."""
        row = self.products[self.products["product_id"] == product_id]
        if row.empty:
            return None
        return row.iloc[0].to_dict()

    def list_products(self, category: str | None = None, limit: int = 10) -> list[dict]:
        """List products, optionally filtered by category."""
        df = self.products
        if category:
            df = df[df["category"].str.lower() == category.lower()]
        return df.head(limit).to_dict(orient="records")

    def search_products(self, query: str, limit: int = 10) -> list[dict]:
        """Search products by name or description."""
        query_lower = query.lower()
        mask = (
            self.products["name"].str.lower().str.contains(query_lower, na=False) |
            self.products["description"].str.lower().str.contains(query_lower, na=False)
        )
        return self.products[mask].head(limit).to_dict(orient="records")

    def list_customers(self, limit: int = 20) -> list[dict]:
        """List all customers. Intended for operator/admin use only."""
        return self.customers.head(limit).to_dict(orient="records")

    def get_customer(self, customer_id: str) -> dict | None:
        """Get a customer by ID."""
        row = self.customers[self.customers["customer_id"] == customer_id]
        if row.empty:
            return None
        return row.iloc[0].to_dict()

    def get_order(self, order_id: str) -> dict | None:
        """Get an order by ID, including line items."""
        order_row = self.orders[self.orders["order_id"] == order_id]
        if order_row.empty:
            return None

        order = order_row.iloc[0].to_dict()

        items = self.order_items[self.order_items["order_id"] == order_id]
        order["items"] = []

        for _, item in items.iterrows():
            item_dict = item.to_dict()
            product = self.get_product(item["product_id"])
            if product:
                item_dict["product_name"] = product["name"]
            order["items"].append(item_dict)

        return order

    def get_customer_orders(self, customer_id: str) -> list[dict]:
        """Get all orders for a customer."""
        orders = self.orders[self.orders["customer_id"] == customer_id]
        result = []
        for _, order in orders.iterrows():
            order_dict = self.get_order(order["order_id"])
            if order_dict:
                result.append(order_dict)
        return result

    def add_product(self, name: str, category: str, price: float, description: str) -> dict:
        """Add a new product. Returns the created product."""
        max_id = self.products["product_id"].str.extract(r"prod_(\d+)").astype(int).max()[0]
        new_id = f"prod_{max_id + 1:03d}"

        new_product = {
            "product_id": new_id,
            "name": name,
            "category": category,
            "price": price,
            "description": description,
        }

        self.products = pd.concat([self.products, pd.DataFrame([new_product])], ignore_index=True)
        self._save_products()

        return new_product

    def update_product(self, product_id: str, **updates) -> dict | None:
        """Update a product. Returns the updated product or None if not found."""
        idx = self.products[self.products["product_id"] == product_id].index
        if idx.empty:
            return None

        allowed_fields = {"name", "category", "price", "description"}
        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                self.products.loc[idx, field] = value

        self._save_products()
        return self.get_product(product_id)

    def _save_products(self):
        """Save products back to CSV."""
        self.products.to_csv(self.data_dir / "products.csv", index=False)

    # ── Knowledge-base articles ──────────────────────────────────────────────

    def _load_kba(self):
        """Parse all HTML files in data/kba/ into an in-memory article list."""
        self._kba_articles: list[dict] = []
        kba_dir = self.data_dir / "kba"
        if not kba_dir.exists():
            return
        for html_file in sorted(kba_dir.glob("*.html")):
            if html_file.name == "index.html":
                continue
            article_id = html_file.stem
            html_content = html_file.read_text(encoding="utf-8")
            title, text = _parse_kba_html(html_content)
            self._kba_articles.append({
                "article_id": article_id,
                "title": title,
                "content": text,
                "tags": _KBA_TAGS.get(article_id, []),
                "url": f"/docs/{html_file.name}",
            })

    def search_kb_articles(self, query: str, limit: int = 5) -> list[dict]:
        """Keyword search across KB article titles, tags, and content."""
        terms = query.lower().split()
        scored: list[tuple[int, dict]] = []
        for article in self._kba_articles:
            searchable = (
                f"{article['title']} {' '.join(article['tags'])} {article['content']}"
            ).lower()
            score = sum(1 for term in terms if term in searchable)
            if score > 0:
                scored.append((score, article))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for _, article in scored[:limit]:
            summary = article["content"]
            if len(summary) > 400:
                summary = summary[:400] + "…"
            results.append({
                "article_id": article["article_id"],
                "title": article["title"],
                "summary": summary,
                "tags": article["tags"],
                "url": article["url"],
            })
        return results

    def get_kb_article(self, article_id: str) -> dict | None:
        """Return the full content of a KB article by its ID."""
        for article in self._kba_articles:
            if article["article_id"] == article_id:
                return article
        return None

    def list_kb_articles(self) -> list[dict]:
        """Return a summary listing of all KB articles."""
        results = []
        for article in self._kba_articles:
            summary = article["content"]
            if len(summary) > 200:
                summary = summary[:200] + "…"
            results.append({
                "article_id": article["article_id"],
                "title": article["title"],
                "summary": summary,
                "tags": article["tags"],
                "url": article["url"],
            })
        return results
