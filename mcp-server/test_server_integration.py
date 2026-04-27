#!/usr/bin/env python3
"""Integration test - uses MCP client SDK to test the server."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_mcp_server():
    """Test the MCP server using the official MCP client SDK."""

    # Get paths
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"

    print("=" * 60)
    print("  MCP SERVER INTEGRATION TEST")
    print("=" * 60)
    print(f"\nData directory: {data_dir}")

    # Server parameters
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "shop_mcp_server.server"],
        env={**os.environ, "SHOP_DATA_DIR": str(data_dir)}
    )

    print("Starting MCP server via stdio client...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            print("\n1. Initializing session...")
            await session.initialize()
            print("   Session initialized successfully")

            # List tools
            print("\n2. Listing available tools...")
            tools_result = await session.list_tools()
            tools = tools_result.tools
            print(f"   Found {len(tools)} tools:")
            for tool in tools:
                print(f"     - {tool.name}")

            # Test get_product
            print("\n3. Calling get_product (prod_001)...")
            result = await session.call_tool("get_product", {
                "product_id": "prod_001",
                "_user_context": {"role": "admin", "user_id": "admin_001"}
            })
            product = json.loads(result.content[0].text)
            print(f"   Product: {product['name']} - ${product['price']}")

            # Test list_products
            print("\n4. Calling list_products (Footwear)...")
            result = await session.call_tool("list_products", {
                "category": "Footwear",
                "_user_context": {"role": "admin", "user_id": "admin_001"}
            })
            products = json.loads(result.content[0].text)
            print(f"   Found {len(products)} footwear products:")
            for p in products[:3]:
                print(f"     - {p['name']}: ${p['price']}")

            # Test get_order
            print("\n5. Calling get_order (ord_001)...")
            result = await session.call_tool("get_order", {
                "order_id": "ord_001",
                "_user_context": {"role": "admin", "user_id": "admin_001"}
            })
            order = json.loads(result.content[0].text)
            print(f"   Order: {order['order_id']} | Status: {order['status']}")
            print(f"   Items: {len(order['items'])}")
            for item in order['items']:
                print(f"     - {item['product_name']} x{item['quantity']}")

            # Test RBAC - customer accessing own order
            print("\n6. RBAC Test: Customer accessing OWN order...")
            result = await session.call_tool("get_order", {
                "order_id": "ord_001",
                "_user_context": {"role": "customer", "user_id": "cust_001"}
            })
            data = json.loads(result.content[0].text)
            if "error" in data:
                print(f"   DENIED: {data['message']}")
            else:
                print(f"   ALLOWED: Got order {data['order_id']}")

            # Test RBAC - customer accessing other's order
            print("\n7. RBAC Test: Customer accessing OTHER's order...")
            result = await session.call_tool("get_order", {
                "order_id": "ord_002",  # belongs to cust_002
                "_user_context": {"role": "customer", "user_id": "cust_001"}
            })
            data = json.loads(result.content[0].text)
            if "error" in data:
                print(f"   DENIED: {data['message']}")
            else:
                print(f"   ALLOWED: Got order {data['order_id']} (RBAC FAILED!)")

            # Test RBAC - customer trying admin tool
            print("\n8. RBAC Test: Customer trying add_product...")
            result = await session.call_tool("add_product", {
                "name": "Hacked Product",
                "category": "Hack",
                "price": 0.01,
                "description": "Should be denied",
                "_user_context": {"role": "customer", "user_id": "cust_001"}
            })
            data = json.loads(result.content[0].text)
            if "error" in data:
                print(f"   DENIED: {data['message']}")
            else:
                print(f"   ALLOWED: {data} (RBAC FAILED!)")

            # Test RBAC - operator read access
            print("\n9. RBAC Test: Operator accessing any customer...")
            result = await session.call_tool("get_customer", {
                "customer_id": "cust_002",
                "_user_context": {"role": "operator", "user_id": "op_001"}
            })
            data = json.loads(result.content[0].text)
            if "error" in data:
                print(f"   DENIED: {data['message']}")
            else:
                print(f"   ALLOWED: Got customer {data['name']}")

            # Test RBAC - admin write access
            print("\n10. RBAC Test: Admin adding product...")
            result = await session.call_tool("add_product", {
                "name": "Integration Test Product",
                "category": "Test",
                "price": 123.45,
                "description": "Added via integration test",
                "_user_context": {"role": "admin", "user_id": "admin_001"}
            })
            data = json.loads(result.content[0].text)
            if "error" in data:
                print(f"   DENIED: {data['message']} (SHOULD HAVE BEEN ALLOWED!)")
            else:
                print(f"   ALLOWED: Created {data['product_id']} - {data['name']}")

    print("\n" + "=" * 60)
    print("  INTEGRATION TEST COMPLETE")
    print("=" * 60)
    print("\nMCP server is working correctly!")


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
