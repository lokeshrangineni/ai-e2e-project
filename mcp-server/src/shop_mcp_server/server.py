"""MCP Server for shop data - products, orders, customers."""

import asyncio
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .data import ShopData


server = Server("shop-mcp-server")
data = ShopData(os.environ.get("SHOP_DATA_DIR"))


# RBAC configuration
TOOLS_BY_ROLE = {
    "customer": ["get_product", "list_products", "search_products", "get_customer", "get_order", "get_customer_orders"],
    "operator": ["get_product", "list_products", "search_products", "get_customer", "get_order", "get_customer_orders", "list_customers"],
    "admin": ["get_product", "list_products", "search_products", "get_customer", "get_order", "get_customer_orders", "add_product", "update_product", "list_customers"],
}


def check_rbac(tool_name: str, arguments: dict, user_context: dict) -> dict | None:
    """
    Check RBAC permissions. Returns error dict if denied, None if allowed.

    user_context should contain:
      - role: "customer" | "operator" | "admin"
      - user_id: customer ID for customer role (e.g., "cust_001")
    """
    role = user_context.get("role", "customer")
    user_id = user_context.get("user_id")

    # Check if tool is allowed for role
    allowed_tools = TOOLS_BY_ROLE.get(role, [])
    if tool_name not in allowed_tools:
        return {"error": "access_denied", "message": f"Tool '{tool_name}' is not available for role '{role}'"}

    # For customer role, enforce data ownership
    if role == "customer" and user_id:
        # Customer can only access their own data
        if tool_name == "get_customer":
            if arguments.get("customer_id") != user_id:
                return {"error": "access_denied", "message": "You can only view your own profile"}

        if tool_name == "get_order":
            order = data.get_order(arguments.get("order_id"))
            if order and order.get("customer_id") != user_id:
                return {"error": "access_denied", "message": "You can only view your own orders"}

        if tool_name == "get_customer_orders":
            if arguments.get("customer_id") != user_id:
                return {"error": "access_denied", "message": "You can only view your own orders"}

    return None  # Allowed


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_product",
            description="Get a product by its ID. Returns product details including name, category, price, and description.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The product ID (e.g., prod_001)",
                    },
                },
                "required": ["product_id"],
            },
        ),
        Tool(
            name="list_products",
            description="List products, optionally filtered by category. Returns up to 10 products by default.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by category (e.g., Footwear, Electronics, Clothing, Accessories, Home)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of products to return (default: 10)",
                    },
                },
            },
        ),
        Tool(
            name="search_products",
            description="Search products by name or description. Returns matching products.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to match against product name or description",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of products to return (default: 10)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_customer",
            description="Get a customer by their ID. Returns customer details including name, email, and location.",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID (e.g., cust_001)",
                    },
                },
                "required": ["customer_id"],
            },
        ),
        Tool(
            name="get_order",
            description="Get an order by its ID. Returns order details including status, dates, and line items with product info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID (e.g., ord_001)",
                    },
                },
                "required": ["order_id"],
            },
        ),
        Tool(
            name="get_customer_orders",
            description="Get all orders for a customer. Returns list of orders with their line items.",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID (e.g., cust_001)",
                    },
                },
                "required": ["customer_id"],
            },
        ),
        Tool(
            name="list_customers",
            description="List all customers with their details. Restricted to operator and admin roles only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of customers to return (default: 20)",
                    },
                },
            },
        ),
        Tool(
            name="add_product",
            description="Add a new product to the catalog. Admin only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Product name",
                    },
                    "category": {
                        "type": "string",
                        "description": "Product category (e.g., Footwear, Electronics)",
                    },
                    "price": {
                        "type": "number",
                        "description": "Product price in USD",
                    },
                    "description": {
                        "type": "string",
                        "description": "Product description",
                    },
                },
                "required": ["name", "category", "price", "description"],
            },
        ),
        Tool(
            name="update_product",
            description="Update an existing product. Admin only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The product ID to update",
                    },
                    "name": {
                        "type": "string",
                        "description": "New product name (optional)",
                    },
                    "category": {
                        "type": "string",
                        "description": "New product category (optional)",
                    },
                    "price": {
                        "type": "number",
                        "description": "New product price (optional)",
                    },
                    "description": {
                        "type": "string",
                        "description": "New product description (optional)",
                    },
                },
                "required": ["product_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls with RBAC enforcement."""
    import json

    # Extract user context from arguments (passed by BFF)
    user_context = arguments.pop("_user_context", {"role": "customer", "user_id": None})

    # Check RBAC
    rbac_error = check_rbac(name, arguments, user_context)
    if rbac_error:
        return [TextContent(type="text", text=json.dumps(rbac_error, indent=2))]

    result = None

    if name == "get_product":
        result = data.get_product(arguments["product_id"])
        if result is None:
            result = {"error": f"Product {arguments['product_id']} not found"}

    elif name == "list_products":
        result = data.list_products(
            category=arguments.get("category"),
            limit=arguments.get("limit", 10),
        )

    elif name == "search_products":
        result = data.search_products(
            query=arguments["query"],
            limit=arguments.get("limit", 10),
        )

    elif name == "get_customer":
        result = data.get_customer(arguments["customer_id"])
        if result is None:
            result = {"error": f"Customer {arguments['customer_id']} not found"}

    elif name == "get_order":
        result = data.get_order(arguments["order_id"])
        if result is None:
            result = {"error": f"Order {arguments['order_id']} not found"}

    elif name == "get_customer_orders":
        result = data.get_customer_orders(arguments["customer_id"])

    elif name == "list_customers":
        result = data.list_customers(limit=arguments.get("limit", 20))

    elif name == "add_product":
        result = data.add_product(
            name=arguments["name"],
            category=arguments["category"],
            price=arguments["price"],
            description=arguments["description"],
        )

    elif name == "update_product":
        result = data.update_product(
            product_id=arguments["product_id"],
            name=arguments.get("name"),
            category=arguments.get("category"),
            price=arguments.get("price"),
            description=arguments.get("description"),
        )
        if result is None:
            result = {"error": f"Product {arguments['product_id']} not found"}

    else:
        result = {"error": f"Unknown tool: {name}"}

    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


async def run_server():
    """Run the MCP server with stdio transport."""
    from mcp.server.models import InitializationOptions
    from mcp.types import ServerCapabilities

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="shop-mcp-server",
                server_version="0.1.0",
                capabilities=ServerCapabilities(tools={}),
            ),
        )


def main():
    """Run the MCP server."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
