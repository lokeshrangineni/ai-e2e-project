"""Tests for the data layer."""

import pytest
from shop_mcp_server.data import ShopData


@pytest.fixture
def shop_data():
    """Create a ShopData instance."""
    import os
    return ShopData(os.environ["SHOP_DATA_DIR"])


class TestProducts:
    """Tests for product operations."""

    def test_get_product_exists(self, shop_data):
        """Get an existing product."""
        product = shop_data.get_product("prod_001")
        assert product is not None
        assert product["product_id"] == "prod_001"
        assert product["name"] == "Nike Air Max 90"
        assert product["price"] == 129.99
        assert product["category"] == "Footwear"

    def test_get_product_not_found(self, shop_data):
        """Get a non-existent product."""
        product = shop_data.get_product("prod_999")
        assert product is None

    def test_list_products_all(self, shop_data):
        """List all products with default limit."""
        products = shop_data.list_products()
        assert len(products) == 10  # default limit
        assert all("product_id" in p for p in products)

    def test_list_products_by_category(self, shop_data):
        """List products filtered by category."""
        products = shop_data.list_products(category="Footwear")
        assert len(products) > 0
        assert all(p["category"] == "Footwear" for p in products)

    def test_list_products_with_limit(self, shop_data):
        """List products with custom limit."""
        products = shop_data.list_products(limit=3)
        assert len(products) == 3

    def test_search_products(self, shop_data):
        """Search products by name."""
        products = shop_data.search_products("Nike")
        assert len(products) > 0
        assert all("Nike" in p["name"] for p in products)

    def test_search_products_by_description(self, shop_data):
        """Search products by description."""
        products = shop_data.search_products("wireless")
        assert len(products) > 0


class TestCustomers:
    """Tests for customer operations."""

    def test_get_customer_exists(self, shop_data):
        """Get an existing customer."""
        customer = shop_data.get_customer("cust_001")
        assert customer is not None
        assert customer["customer_id"] == "cust_001"
        assert customer["name"] == "Alice Johnson"
        assert customer["email"] == "alice.johnson@email.com"

    def test_get_customer_not_found(self, shop_data):
        """Get a non-existent customer."""
        customer = shop_data.get_customer("cust_999")
        assert customer is None


class TestOrders:
    """Tests for order operations."""

    def test_get_order_exists(self, shop_data):
        """Get an existing order with line items."""
        order = shop_data.get_order("ord_001")
        assert order is not None
        assert order["order_id"] == "ord_001"
        assert order["customer_id"] == "cust_001"
        assert order["status"] == "delivered"
        assert "items" in order
        assert len(order["items"]) > 0
        assert all("product_name" in item for item in order["items"])

    def test_get_order_not_found(self, shop_data):
        """Get a non-existent order."""
        order = shop_data.get_order("ord_999")
        assert order is None

    def test_get_customer_orders(self, shop_data):
        """Get all orders for a customer."""
        orders = shop_data.get_customer_orders("cust_001")
        assert len(orders) == 3  # Alice has 3 orders
        assert all(o["customer_id"] == "cust_001" for o in orders)
