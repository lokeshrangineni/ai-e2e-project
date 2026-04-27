"""Pytest configuration and fixtures."""

import os
import pytest
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def set_data_dir():
    """Set the data directory for tests."""
    data_dir = Path(__file__).parent.parent.parent / "data"
    os.environ["SHOP_DATA_DIR"] = str(data_dir)


@pytest.fixture
def customer_context():
    """Customer user context (cust_001 = Alice)."""
    return {"role": "customer", "user_id": "cust_001"}


@pytest.fixture
def other_customer_context():
    """Another customer user context (cust_002 = Bob)."""
    return {"role": "customer", "user_id": "cust_002"}


@pytest.fixture
def operator_context():
    """Operator user context."""
    return {"role": "operator", "user_id": "op_001"}


@pytest.fixture
def admin_context():
    """Admin user context."""
    return {"role": "admin", "user_id": "admin_001"}
