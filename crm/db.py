"""
crm/db.py
---------
SQLite database management for the CRM module.
Contains customers and stores tables with seed data for testing function calling.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "crm.db"


def init_db() -> None:
    """Initialize the SQLite database and create CRM tables if they don't exist."""
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Customers Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                phone_number TEXT PRIMARY KEY,
                name TEXT,
                account_status TEXT,
                balance REAL
            )
            """
        )
        
        # Stores Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stores (
                location TEXT PRIMARY KEY,
                open_time TEXT,
                close_time TEXT
            )
            """
        )
        conn.commit()
        
    seed_data()


def seed_data() -> None:
    """Populate the database with dummy data for testing."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Seed Customers
        customers = [
            ("1234567890", "John Doe", "Active", 150.00),
            ("5555559999", "Jane Smith", "Suspended - Unpaid Dues", -45.50),
            ("9876543210", "Raj Patel", "Active", 0.00)
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO customers (phone_number, name, account_status, balance) VALUES (?, ?, ?, ?)",
            customers
        )
        
        # Seed Stores
        stores = [
            ("Hyderabad", "9:00 AM", "9:00 PM"),
            ("Vijayawada", "10:00 AM", "8:00 PM"),
            ("Vizag", "9:30 AM", "8:30 PM")
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO stores (location, open_time, close_time) VALUES (?, ?, ?)",
            stores
        )
        
        conn.commit()


def get_customer_status(phone_number: str) -> dict | None:
    """Retrieve customer account status by phone number."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE phone_number = ?", (phone_number,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_store_info(location: str) -> dict | None:
    """Retrieve store operating hours by location."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Case insensitive substring match for location
        cursor.execute("SELECT * FROM stores WHERE location LIKE ?", (f"%{location}%",))
        row = cursor.fetchone()
        return dict(row) if row else None


# Ensure the DB is ready on import
init_db()
