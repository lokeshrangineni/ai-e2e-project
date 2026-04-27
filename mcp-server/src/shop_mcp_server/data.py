"""Data layer for loading and querying shop data."""

import os
from pathlib import Path
import pandas as pd


class ShopData:
    """Loads and queries shop data from CSV files."""

    def __init__(self, data_dir: str | Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent.parent / "data"
        self.data_dir = Path(data_dir)
        self._load_data()

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
