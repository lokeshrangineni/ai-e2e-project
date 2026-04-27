"""Tests for RBAC enforcement."""

import json
import pytest
from shop_mcp_server.server import call_tool, check_rbac


class TestRBACCheck:
    """Tests for the check_rbac function."""

    def test_customer_allowed_tools(self, customer_context):
        """Customer can access read-only tools."""
        allowed_tools = ["get_product", "list_products", "search_products"]
        for tool in allowed_tools:
            result = check_rbac(tool, {}, customer_context)
            assert result is None, f"Customer should be allowed to use {tool}"

    def test_customer_denied_admin_tools(self, customer_context):
        """Customer cannot access admin tools."""
        denied_tools = ["add_product", "update_product"]
        for tool in denied_tools:
            result = check_rbac(tool, {}, customer_context)
            assert result is not None
            assert result["error"] == "access_denied"

    def test_customer_own_data_allowed(self, customer_context):
        """Customer can access their own data."""
        result = check_rbac("get_customer", {"customer_id": "cust_001"}, customer_context)
        assert result is None

    def test_customer_other_data_denied(self, customer_context):
        """Customer cannot access other customer's data."""
        result = check_rbac("get_customer", {"customer_id": "cust_002"}, customer_context)
        assert result is not None
        assert result["error"] == "access_denied"

    def test_operator_any_customer_allowed(self, operator_context):
        """Operator can access any customer's data."""
        result = check_rbac("get_customer", {"customer_id": "cust_002"}, operator_context)
        assert result is None

    def test_operator_denied_write_tools(self, operator_context):
        """Operator cannot access write tools."""
        result = check_rbac("add_product", {}, operator_context)
        assert result is not None
        assert result["error"] == "access_denied"

    def test_admin_all_tools_allowed(self, admin_context):
        """Admin can access all tools."""
        all_tools = ["get_product", "list_products", "search_products",
                     "get_customer", "get_order", "get_customer_orders",
                     "add_product", "update_product"]
        for tool in all_tools:
            result = check_rbac(tool, {}, admin_context)
            assert result is None, f"Admin should be allowed to use {tool}"


class TestToolCallsWithRBAC:
    """Tests for tool calls with RBAC enforcement."""

    @pytest.mark.asyncio
    async def test_customer_get_own_order(self, customer_context):
        """Customer can get their own order."""
        result = await call_tool("get_order", {
            "order_id": "ord_001",
            "_user_context": customer_context
        })
        response = json.loads(result[0].text)
        assert "error" not in response
        assert response["order_id"] == "ord_001"

    @pytest.mark.asyncio
    async def test_customer_denied_other_order(self, customer_context):
        """Customer cannot get another customer's order."""
        result = await call_tool("get_order", {
            "order_id": "ord_002",  # belongs to cust_002
            "_user_context": customer_context
        })
        response = json.loads(result[0].text)
        assert response["error"] == "access_denied"

    @pytest.mark.asyncio
    async def test_customer_denied_add_product(self, customer_context):
        """Customer cannot add products."""
        result = await call_tool("add_product", {
            "name": "Hacked Product",
            "category": "Hack",
            "price": 0.01,
            "description": "Should not work",
            "_user_context": customer_context
        })
        response = json.loads(result[0].text)
        assert response["error"] == "access_denied"

    @pytest.mark.asyncio
    async def test_operator_get_any_order(self, operator_context):
        """Operator can get any customer's order."""
        result = await call_tool("get_order", {
            "order_id": "ord_002",
            "_user_context": operator_context
        })
        response = json.loads(result[0].text)
        assert "error" not in response
        assert response["order_id"] == "ord_002"

    @pytest.mark.asyncio
    async def test_operator_get_any_customer(self, operator_context):
        """Operator can get any customer."""
        result = await call_tool("get_customer", {
            "customer_id": "cust_002",
            "_user_context": operator_context
        })
        response = json.loads(result[0].text)
        assert "error" not in response
        assert response["customer_id"] == "cust_002"

    @pytest.mark.asyncio
    async def test_admin_add_product(self, admin_context):
        """Admin can add products."""
        result = await call_tool("add_product", {
            "name": "Test Product",
            "category": "Test",
            "price": 49.99,
            "description": "Test description",
            "_user_context": admin_context
        })
        response = json.loads(result[0].text)
        assert "error" not in response
        assert response["name"] == "Test Product"
        assert "product_id" in response


class TestToolCallsBasic:
    """Tests for basic tool functionality (without RBAC focus)."""

    @pytest.mark.asyncio
    async def test_get_product(self, admin_context):
        """Get product returns correct data."""
        result = await call_tool("get_product", {
            "product_id": "prod_001",
            "_user_context": admin_context
        })
        response = json.loads(result[0].text)
        assert response["name"] == "Nike Air Max 90"

    @pytest.mark.asyncio
    async def test_list_products(self, admin_context):
        """List products returns array."""
        result = await call_tool("list_products", {
            "limit": 5,
            "_user_context": admin_context
        })
        response = json.loads(result[0].text)
        assert isinstance(response, list)
        assert len(response) == 5

    @pytest.mark.asyncio
    async def test_search_products(self, admin_context):
        """Search products returns matches."""
        result = await call_tool("search_products", {
            "query": "Nike",
            "_user_context": admin_context
        })
        response = json.loads(result[0].text)
        assert isinstance(response, list)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_get_customer_orders(self, admin_context):
        """Get customer orders returns all orders."""
        result = await call_tool("get_customer_orders", {
            "customer_id": "cust_001",
            "_user_context": admin_context
        })
        response = json.loads(result[0].text)
        assert isinstance(response, list)
        assert len(response) == 3  # Alice has 3 orders
