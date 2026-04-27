# Shop MCP Server

MCP (Model Context Protocol) server providing tools for products, orders, and customers.

## Tools

| Tool | Description | RBAC |
|------|-------------|------|
| `get_product` | Get product by ID | All roles |
| `list_products` | List products (optional category filter) | All roles |
| `search_products` | Search products by name/description | All roles |
| `get_customer` | Get customer by ID | Operator, Admin (Customer: own only) |
| `get_order` | Get order by ID with line items | Operator, Admin (Customer: own only) |
| `get_customer_orders` | Get all orders for a customer | Operator, Admin (Customer: own only) |
| `add_product` | Add new product | Admin only |
| `update_product` | Update existing product | Admin only |

## Installation

```bash
cd mcp-server
pip install -e .
```

## Usage

### Standalone (stdio)

```bash
shop-mcp-server
```

### With Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "shop": {
      "command": "shop-mcp-server",
      "env": {
        "SHOP_DATA_DIR": "/path/to/data"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SHOP_DATA_DIR` | Path to data directory containing CSV files | `../data` relative to package |

## Development

```bash
pip install -e ".[dev]"
pytest
```
