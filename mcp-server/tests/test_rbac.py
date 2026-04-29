"""Layer 1 tests for MCP server RBAC — no LLM calls, tests access control logic."""

import pytest
from unittest.mock import patch, MagicMock

from shop_mcp_server.server import check_rbac, TOOLS_BY_ROLE


class TestToolsByRole:
    """Verify tool availability per role is correctly configured."""

    def test_customer_tools(self):
        customer_tools = TOOLS_BY_ROLE["customer"]
        assert "get_product" in customer_tools
        assert "list_products" in customer_tools
        assert "get_order" in customer_tools
        assert "get_customer" in customer_tools
        assert "get_customer_orders" in customer_tools
        # Customer should NOT have write or admin tools
        assert "add_product" not in customer_tools
        assert "update_product" not in customer_tools
        assert "list_customers" not in customer_tools

    def test_operator_tools(self):
        operator_tools = TOOLS_BY_ROLE["operator"]
        assert "get_product" in operator_tools
        assert "list_products" in operator_tools
        assert "get_order" in operator_tools
        assert "get_customer" in operator_tools
        assert "list_customers" in operator_tools
        # Operator should NOT have write tools
        assert "add_product" not in operator_tools
        assert "update_product" not in operator_tools

    def test_admin_tools(self):
        admin_tools = TOOLS_BY_ROLE["admin"]
        assert "get_product" in admin_tools
        assert "list_products" in admin_tools
        assert "get_order" in admin_tools
        assert "get_customer" in admin_tools
        assert "list_customers" in admin_tools
        assert "add_product" in admin_tools
        assert "update_product" in admin_tools


class TestRBACToolAccess:
    """Tool-level access control (no data dependency)."""

    def test_customer_cannot_use_list_customers(self):
        ctx = {"role": "customer", "user_id": "cust_001"}
        result = check_rbac("list_customers", {}, ctx)
        assert result is not None
        assert result["error"] == "access_denied"

    def test_customer_cannot_use_add_product(self):
        ctx = {"role": "customer", "user_id": "cust_001"}
        result = check_rbac("add_product", {"name": "Test"}, ctx)
        assert result is not None
        assert result["error"] == "access_denied"

    def test_operator_cannot_use_add_product(self):
        ctx = {"role": "operator", "user_id": "op_001"}
        result = check_rbac("add_product", {"name": "Test"}, ctx)
        assert result is not None
        assert result["error"] == "access_denied"

    def test_operator_can_use_list_customers(self):
        ctx = {"role": "operator", "user_id": "op_001"}
        result = check_rbac("list_customers", {}, ctx)
        assert result is None  # None = allowed

    def test_admin_can_use_add_product(self):
        ctx = {"role": "admin", "user_id": "admin_001"}
        result = check_rbac("add_product", {"name": "Test", "price": 9.99}, ctx)
        assert result is None

    def test_admin_can_use_all_tools(self):
        ctx = {"role": "admin", "user_id": "admin_001"}
        for tool in TOOLS_BY_ROLE["admin"]:
            result = check_rbac(tool, {}, ctx)
            assert result is None, f"Admin should have access to {tool}"

    def test_unknown_role_defaults_to_no_access(self):
        ctx = {"role": "unknown_role", "user_id": "x"}
        result = check_rbac("get_product", {}, ctx)
        assert result is not None
        assert result["error"] == "access_denied"


class TestRBACDataOwnership:
    """Customer role data ownership enforcement."""

    def test_customer_can_access_own_profile(self):
        ctx = {"role": "customer", "user_id": "cust_001"}
        result = check_rbac("get_customer", {"customer_id": "cust_001"}, ctx)
        assert result is None

    def test_customer_cannot_access_other_profile(self):
        ctx = {"role": "customer", "user_id": "cust_001"}
        result = check_rbac("get_customer", {"customer_id": "cust_002"}, ctx)
        assert result is not None
        assert result["error"] == "access_denied"
        assert "own profile" in result["message"]

    def test_customer_can_access_own_orders(self):
        ctx = {"role": "customer", "user_id": "cust_001"}
        result = check_rbac("get_customer_orders", {"customer_id": "cust_001"}, ctx)
        assert result is None

    def test_customer_cannot_access_other_orders(self):
        ctx = {"role": "customer", "user_id": "cust_001"}
        result = check_rbac("get_customer_orders", {"customer_id": "cust_002"}, ctx)
        assert result is not None
        assert result["error"] == "access_denied"

    @patch("shop_mcp_server.server.data")
    def test_customer_cannot_access_other_customer_order(self, mock_data):
        mock_data.get_order.return_value = {"order_id": "ORD-999", "customer_id": "cust_002"}
        ctx = {"role": "customer", "user_id": "cust_001"}
        result = check_rbac("get_order", {"order_id": "ORD-999"}, ctx)
        assert result is not None
        assert result["error"] == "access_denied"
        assert "own orders" in result["message"]

    @patch("shop_mcp_server.server.data")
    def test_customer_can_access_own_order(self, mock_data):
        mock_data.get_order.return_value = {"order_id": "ORD-001", "customer_id": "cust_001"}
        ctx = {"role": "customer", "user_id": "cust_001"}
        result = check_rbac("get_order", {"order_id": "ORD-001"}, ctx)
        assert result is None

    def test_operator_can_access_any_customer(self):
        ctx = {"role": "operator", "user_id": "op_001"}
        result = check_rbac("get_customer", {"customer_id": "cust_999"}, ctx)
        assert result is None

    def test_operator_can_access_any_orders(self):
        ctx = {"role": "operator", "user_id": "op_001"}
        result = check_rbac("get_customer_orders", {"customer_id": "cust_999"}, ctx)
        assert result is None
