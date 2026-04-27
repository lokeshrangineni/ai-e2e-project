# Sample Data

Synthetic e-commerce dataset for the shopping chatbot demo.

## Files

| File | Records | Description |
|------|---------|-------------|
| `customers.csv` | 20 | Customer profiles |
| `products.csv` | 25 | Product catalog |
| `orders.csv` | 30 | Order records |
| `order_items.csv` | 47 | Line items (links orders to products) |

## Schema

### customers.csv
| Field | Type | Description |
|-------|------|-------------|
| customer_id | string | Primary key (cust_XXX) |
| name | string | Full name |
| email | string | Email address |
| city | string | City |
| state | string | US state abbreviation |

### products.csv
| Field | Type | Description |
|-------|------|-------------|
| product_id | string | Primary key (prod_XXX) |
| name | string | Product name |
| category | string | Category (Footwear, Electronics, etc.) |
| price | decimal | Price in USD |
| description | string | Product description |

### orders.csv
| Field | Type | Description |
|-------|------|-------------|
| order_id | string | Primary key (ord_XXX) |
| customer_id | string | Foreign key to customers |
| status | string | delivered, shipped, processing, cancelled |
| order_date | date | When order was placed |
| delivered_date | date | When delivered (null if not yet) |

### order_items.csv
| Field | Type | Description |
|-------|------|-------------|
| order_item_id | string | Primary key (item_XXX) |
| order_id | string | Foreign key to orders |
| product_id | string | Foreign key to products |
| quantity | integer | Quantity ordered |
| unit_price | decimal | Price at time of order |

## Relationships

```
customers (1) ──< orders (1) ──< order_items (N) >── products (1)
```

## Sample Queries

- Customer cust_001 (Alice Johnson) has 3 orders: ord_001, ord_004, ord_019
- Order ord_001 contains 2 items: Nike Air Max 90 + Nike Dri-FIT T-Shirt (x2)
- Most expensive product: Sony WH-1000XM5 ($349.99)

## License

Synthetic data - no license restrictions.
