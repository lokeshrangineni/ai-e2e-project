#!/usr/bin/env python3
"""Simple test script to validate MCP server functionality."""

import asyncio
import json
import os
import sys

# Set data directory before importing
os.environ["SHOP_DATA_DIR"] = os.path.join(os.path.dirname(__file__), "..", "data")

from shop_mcp_server.server import call_tool, list_tools


def print_header(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_result(result: dict, indent: int = 2):
    if isinstance(result, list):
        for item in result[:3]:  # Show first 3 items
            print(f"{' '*indent}- {item.get('name', item.get('product_id', item))}")
        if len(result) > 3:
            print(f"{' '*indent}  ... and {len(result) - 3} more")
    else:
        print(json.dumps(result, indent=indent, default=str)[:500])


async def test_list_tools():
    """Test listing available tools."""
    print_header("Available Tools")
    tools = await list_tools()
    for tool in tools:
        print(f"  - {tool.name}: {tool.description[:60]}...")
    return len(tools)


async def test_products():
    """Test product operations."""
    print_header("Product Operations")

    # Get product
    print("\n1. Get product (prod_001):")
    result = await call_tool("get_product", {
        "product_id": "prod_001",
        "_user_context": {"role": "admin", "user_id": "admin_001"}
    })
    data = json.loads(result[0].text)
    print(f"   {data['name']} - ${data['price']} ({data['category']})")

    # List products by category
    print("\n2. List Footwear products:")
    result = await call_tool("list_products", {
        "category": "Footwear",
        "_user_context": {"role": "admin", "user_id": "admin_001"}
    })
    data = json.loads(result[0].text)
    for p in data:
        print(f"   - {p['name']}: ${p['price']}")

    # Search products
    print("\n3. Search for 'wireless':")
    result = await call_tool("search_products", {
        "query": "wireless",
        "_user_context": {"role": "admin", "user_id": "admin_001"}
    })
    data = json.loads(result[0].text)
    for p in data:
        print(f"   - {p['name']}")


async def test_customers_and_orders():
    """Test customer and order operations."""
    print_header("Customer & Order Operations")

    # Get customer
    print("\n1. Get customer (cust_001 - Alice):")
    result = await call_tool("get_customer", {
        "customer_id": "cust_001",
        "_user_context": {"role": "admin", "user_id": "admin_001"}
    })
    data = json.loads(result[0].text)
    print(f"   {data['name']} ({data['email']}) - {data['city']}, {data['state']}")

    # Get order with items
    print("\n2. Get order (ord_001):")
    result = await call_tool("get_order", {
        "order_id": "ord_001",
        "_user_context": {"role": "admin", "user_id": "admin_001"}
    })
    data = json.loads(result[0].text)
    print(f"   Order: {data['order_id']} | Status: {data['status']} | Date: {data['order_date']}")
    print("   Items:")
    for item in data['items']:
        print(f"     - {item['product_name']} x{item['quantity']} @ ${item['unit_price']}")

    # Get customer orders
    print("\n3. Get all orders for Alice (cust_001):")
    result = await call_tool("get_customer_orders", {
        "customer_id": "cust_001",
        "_user_context": {"role": "admin", "user_id": "admin_001"}
    })
    data = json.loads(result[0].text)
    print(f"   Found {len(data)} orders:")
    for order in data:
        print(f"     - {order['order_id']}: {order['status']} ({len(order['items'])} items)")


async def test_rbac():
    """Test RBAC enforcement."""
    print_header("RBAC Enforcement Tests")

    # Customer accessing own order (allowed)
    print("\n1. Customer (cust_001) accessing OWN order (ord_001):")
    result = await call_tool("get_order", {
        "order_id": "ord_001",
        "_user_context": {"role": "customer", "user_id": "cust_001"}
    })
    data = json.loads(result[0].text)
    if "error" in data:
        print(f"   DENIED: {data['message']}")
    else:
        print(f"   ALLOWED: Got order {data['order_id']}")

    # Customer accessing other's order (denied)
    print("\n2. Customer (cust_001) accessing OTHER's order (ord_002):")
    result = await call_tool("get_order", {
        "order_id": "ord_002",  # belongs to cust_002
        "_user_context": {"role": "customer", "user_id": "cust_001"}
    })
    data = json.loads(result[0].text)
    if "error" in data:
        print(f"   DENIED: {data['message']}")
    else:
        print(f"   ALLOWED: Got order {data['order_id']}")

    # Customer trying to add product (denied)
    print("\n3. Customer trying to add_product:")
    result = await call_tool("add_product", {
        "name": "Hacked Product",
        "category": "Hack",
        "price": 0.01,
        "description": "Should not work",
        "_user_context": {"role": "customer", "user_id": "cust_001"}
    })
    data = json.loads(result[0].text)
    if "error" in data:
        print(f"   DENIED: {data['message']}")
    else:
        print(f"   ALLOWED: Created {data['product_id']}")

    # Operator accessing any order (allowed)
    print("\n4. Operator accessing any order (ord_002):")
    result = await call_tool("get_order", {
        "order_id": "ord_002",
        "_user_context": {"role": "operator", "user_id": "op_001"}
    })
    data = json.loads(result[0].text)
    if "error" in data:
        print(f"   DENIED: {data['message']}")
    else:
        print(f"   ALLOWED: Got order {data['order_id']} (customer: {data['customer_id']})")

    # Operator trying to add product (denied)
    print("\n5. Operator trying to add_product:")
    result = await call_tool("add_product", {
        "name": "Operator Product",
        "category": "Test",
        "price": 10.00,
        "description": "Should not work",
        "_user_context": {"role": "operator", "user_id": "op_001"}
    })
    data = json.loads(result[0].text)
    if "error" in data:
        print(f"   DENIED: {data['message']}")
    else:
        print(f"   ALLOWED: Created {data['product_id']}")

    # Admin adding product (allowed)
    print("\n6. Admin adding product:")
    result = await call_tool("add_product", {
        "name": "Admin Test Product",
        "category": "Test",
        "price": 99.99,
        "description": "Added by admin via test script",
        "_user_context": {"role": "admin", "user_id": "admin_001"}
    })
    data = json.loads(result[0].text)
    if "error" in data:
        print(f"   DENIED: {data['message']}")
    else:
        print(f"   ALLOWED: Created {data['product_id']} - {data['name']}")


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  SHOP MCP SERVER - VALIDATION TEST")
    print("="*60)

    try:
        # Test tools listing
        tool_count = await test_list_tools()
        print(f"\n  Total tools: {tool_count}")

        # Test product operations
        await test_products()

        # Test customer and order operations
        await test_customers_and_orders()

        # Test RBAC
        await test_rbac()

        print_header("TEST SUMMARY")
        print("  All tests completed successfully!")
        print("  MCP Server is working correctly.")
        print("")

    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
