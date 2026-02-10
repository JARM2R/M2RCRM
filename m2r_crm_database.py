"""
M2R CRM Database Module
=======================
SQLite database operations for the M2R CRM application.
"""

import sqlite3
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from m2r_crm_paths import APP_DIR

# Database file location (writable directory — exe folder when frozen, source folder in dev)
DB_PATH = APP_DIR / "m2r_crm.db"

# Starting account number for new accounts
STARTING_ACCOUNT_NUMBER = 10534000


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database():
    """Initialize the database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create customers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT UNIQUE NOT NULL,
            company_name TEXT,
            contact_name TEXT,
            email TEXT,
            email_ap TEXT,
            email_user TEXT,
            email_it TEXT,
            phone TEXT,
            phone_extension TEXT,
            address_street TEXT,
            address_city TEXT,
            address_state TEXT,
            address_zip TEXT,
            license_type TEXT,
            software_version TEXT,
            company_id TEXT,
            bureau_id TEXT,
            bureau_equifax TEXT,
            bureau_experian TEXT,
            bureau_transunion TEXT,
            auth_date DATE,
            paid_through_date DATE,
            subscription_status TEXT DEFAULT 'NO',
            support_amount REAL,
            is_retired INTEGER DEFAULT 0,
            no_support INTEGER DEFAULT 0,
            support_invoice INTEGER DEFAULT 0,
            no_invoice INTEGER DEFAULT 0,
            note_to_customer TEXT,
            memo_to_self TEXT,
            last_invoice_date DATE,
            last_invoice_past_due DATE,
            last_csv_create_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migrate: add new email columns if they don't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN email_ap TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN email_user TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN email_it TEXT")
    except sqlite3.OperationalError:
        pass

    # Migrate existing email data to email_ap if email_ap is empty
    cursor.execute("""
        UPDATE customers SET email_ap = email
        WHERE email IS NOT NULL AND email != ''
        AND (email_ap IS NULL OR email_ap = '')
    """)

    # Migrate: add company_id and bureau sub-fields if they don't exist
    for col in ('company_id', 'bureau_equifax', 'bureau_experian', 'bureau_transunion'):
        try:
            cursor.execute(f"ALTER TABLE customers ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    # Migrate existing bureau_id data to bureau_equifax if bureau_equifax is empty
    cursor.execute("""
        UPDATE customers SET bureau_equifax = bureau_id
        WHERE bureau_id IS NOT NULL AND bureau_id != ''
        AND (bureau_equifax IS NULL OR bureau_equifax = '')
    """)

    # Create notes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            note_text TEXT,
            note_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)

    # Create settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Initialize next_account_number if not exists
    cursor.execute("SELECT value FROM settings WHERE key = 'next_account_number'")
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO settings (key, value) VALUES ('next_account_number', ?)",
            (str(STARTING_ACCOUNT_NUMBER),)
        )

    # Create indexes for common searches
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_account ON customers(account_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_company ON customers(company_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_contact ON customers(contact_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_retired ON customers(is_retired)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_customer ON notes(customer_id)")

    conn.commit()
    conn.close()


def get_next_account_number() -> str:
    """Get the next available account number."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM settings WHERE key = 'next_account_number'")
    row = cursor.fetchone()
    next_num = int(row['value']) if row else STARTING_ACCOUNT_NUMBER

    conn.close()
    return str(next_num)


def increment_account_number():
    """Increment the next account number counter."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM settings WHERE key = 'next_account_number'")
    row = cursor.fetchone()
    current = int(row['value']) if row else STARTING_ACCOUNT_NUMBER

    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'next_account_number'",
        (str(current + 1),)
    )

    conn.commit()
    conn.close()


def is_account_number_unique(account_number: str, exclude_id: Optional[int] = None) -> bool:
    """Check if an account number is unique."""
    conn = get_connection()
    cursor = conn.cursor()

    if exclude_id:
        cursor.execute(
            "SELECT id FROM customers WHERE account_number = ? AND id != ?",
            (account_number, exclude_id)
        )
    else:
        cursor.execute(
            "SELECT id FROM customers WHERE account_number = ?",
            (account_number,)
        )

    result = cursor.fetchone() is None
    conn.close()
    return result


def create_customer(data: Dict[str, Any]) -> int:
    """Create a new customer record. Returns the new customer ID."""
    conn = get_connection()
    cursor = conn.cursor()

    columns = [
        'account_number', 'company_name', 'contact_name', 'email',
        'email_ap', 'email_user', 'email_it',
        'phone', 'phone_extension', 'address_street', 'address_city',
        'address_state', 'address_zip', 'license_type', 'software_version',
        'company_id', 'bureau_id', 'bureau_equifax', 'bureau_experian',
        'bureau_transunion', 'auth_date', 'paid_through_date', 'subscription_status',
        'support_amount', 'is_retired', 'no_support', 'support_invoice',
        'no_invoice', 'note_to_customer', 'memo_to_self', 'last_invoice_date',
        'last_invoice_past_due', 'last_csv_create_date'
    ]

    # Filter to only include columns that are in the data
    values = []
    cols_to_insert = []
    for col in columns:
        if col in data:
            cols_to_insert.append(col)
            values.append(data[col])

    placeholders = ','.join(['?' for _ in cols_to_insert])
    col_names = ','.join(cols_to_insert)

    cursor.execute(
        f"INSERT INTO customers ({col_names}) VALUES ({placeholders})",
        values
    )

    customer_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return customer_id


def update_customer(customer_id: int, data: Dict[str, Any]) -> bool:
    """Update a customer record."""
    conn = get_connection()
    cursor = conn.cursor()

    # Add updated_at timestamp
    data['updated_at'] = datetime.now().isoformat()

    set_clause = ','.join([f"{key} = ?" for key in data.keys()])
    values = list(data.values()) + [customer_id]

    cursor.execute(
        f"UPDATE customers SET {set_clause} WHERE id = ?",
        values
    )

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def delete_customer(customer_id: int) -> bool:
    """Delete a customer record (and associated notes via CASCADE)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


def get_customer(customer_id: int) -> Optional[Dict[str, Any]]:
    """Get a single customer by ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    row = cursor.fetchone()

    conn.close()

    if row:
        return dict(row)
    return None


def get_customer_by_account(account_number: str) -> Optional[Dict[str, Any]]:
    """Get a customer by account number."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM customers WHERE account_number = ?", (account_number,))
    row = cursor.fetchone()

    conn.close()

    if row:
        return dict(row)
    return None


def search_customers(
    search_term: str = "",
    filter_status: str = "Active",
    order_by: str = "company_name",
    order_dir: str = "ASC"
) -> List[Dict[str, Any]]:
    """
    Search customers with optional filtering.

    Args:
        search_term: Search in account_number, company_name, contact_name, email
        filter_status: "Active", "Retired", or "All"
        order_by: Column to sort by
        order_dir: "ASC" or "DESC"
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM customers WHERE 1=1"
    params = []

    # Apply search filter
    if search_term:
        search_pattern = f"%{search_term}%"
        query += """ AND (
            account_number LIKE ? OR
            company_name LIKE ? OR
            contact_name LIKE ? OR
            email LIKE ? OR
            email_ap LIKE ? OR
            email_user LIKE ? OR
            email_it LIKE ?
        )"""
        params.extend([search_pattern] * 7)

    # Apply status filter
    if filter_status == "Active":
        query += " AND is_retired = 0"
    elif filter_status == "Retired":
        query += " AND is_retired = 1"
    # "All" shows everything

    # Validate and apply ordering
    valid_columns = [
        'account_number', 'company_name', 'contact_name', 'email',
        'paid_through_date', 'subscription_status', 'created_at'
    ]
    if order_by not in valid_columns:
        order_by = 'company_name'
    if order_dir.upper() not in ('ASC', 'DESC'):
        order_dir = 'ASC'

    query += f" ORDER BY {order_by} {order_dir}"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_customer_count(filter_status: str = "All") -> int:
    """Get the count of customers."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT COUNT(*) as count FROM customers"

    if filter_status == "Active":
        query += " WHERE is_retired = 0"
    elif filter_status == "Retired":
        query += " WHERE is_retired = 1"

    cursor.execute(query)
    row = cursor.fetchone()

    conn.close()

    return row['count'] if row else 0


# Notes operations

def create_note(customer_id: int, note_text: str) -> int:
    """Create a new note for a customer. Returns the note ID."""
    conn = get_connection()
    cursor = conn.cursor()

    # Use local time instead of UTC
    local_time = datetime.now().isoformat()

    cursor.execute(
        "INSERT INTO notes (customer_id, note_text, note_date) VALUES (?, ?, ?)",
        (customer_id, note_text, local_time)
    )

    note_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return note_id


def get_notes(customer_id: int) -> List[Dict[str, Any]]:
    """Get all notes for a customer, ordered by date descending."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM notes WHERE customer_id = ? ORDER BY note_date DESC",
        (customer_id,)
    )
    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]


def delete_note(note_id: int) -> bool:
    """Delete a note."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return success


# Export operations

def get_customers_for_export(
    paid_from: Optional[date] = None,
    paid_to: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Get customers for Excel export with optional date filtering.

    Args:
        paid_from: Filter by paid_through_date >= this date
        paid_to: Filter by paid_through_date <= this date
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            contact_name,
            company_name,
            email,
            email_ap,
            email_user,
            email_it,
            phone,
            address_street,
            address_city,
            address_state,
            address_zip,
            account_number,
            company_id,
            bureau_equifax,
            bureau_experian,
            bureau_transunion,
            subscription_status,
            paid_through_date,
            support_amount
        FROM customers
        WHERE is_retired = 0
    """
    params = []

    if paid_from:
        query += " AND paid_through_date >= ?"
        params.append(paid_from.isoformat())

    if paid_to:
        query += " AND paid_through_date <= ?"
        params.append(paid_to.isoformat())

    query += " ORDER BY company_name ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]


# Bulk import operations

def bulk_import_customers(customers: List[Dict[str, Any]]) -> Tuple[int, int, List[str]]:
    """
    Bulk import customers from Access database.

    Returns:
        Tuple of (imported_count, skipped_count, list of error messages)
    """
    conn = get_connection()
    cursor = conn.cursor()

    imported = 0
    skipped = 0
    errors = []

    columns = [
        'account_number', 'company_name', 'contact_name', 'email',
        'email_ap', 'email_user', 'email_it',
        'phone', 'phone_extension', 'address_street', 'address_city',
        'address_state', 'address_zip', 'license_type', 'software_version',
        'company_id', 'bureau_id', 'bureau_equifax', 'bureau_experian',
        'bureau_transunion', 'auth_date', 'paid_through_date', 'subscription_status',
        'support_amount', 'is_retired', 'no_support', 'support_invoice',
        'no_invoice', 'note_to_customer', 'memo_to_self', 'last_invoice_date',
        'last_invoice_past_due', 'last_csv_create_date'
    ]

    for customer in customers:
        try:
            # Check for duplicate account number
            account_num = customer.get('account_number', '')
            if account_num:
                cursor.execute(
                    "SELECT id FROM customers WHERE account_number = ?",
                    (account_num,)
                )
                if cursor.fetchone():
                    skipped += 1
                    continue

            # Build insert statement
            cols_to_insert = []
            values = []
            for col in columns:
                if col in customer and customer[col] is not None:
                    cols_to_insert.append(col)
                    values.append(customer[col])

            if cols_to_insert:
                placeholders = ','.join(['?' for _ in cols_to_insert])
                col_names = ','.join(cols_to_insert)

                cursor.execute(
                    f"INSERT INTO customers ({col_names}) VALUES ({placeholders})",
                    values
                )
                imported += 1

        except Exception as e:
            errors.append(f"Error importing {customer.get('account_number', 'unknown')}: {str(e)}")
            skipped += 1

    conn.commit()
    conn.close()

    return imported, skipped, errors


def bulk_import_notes(notes: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
    """
    Bulk import notes from Access database.

    Each note dict should have: account_number, note_text, note_date

    Returns:
        Tuple of (imported_count, list of error messages)
    """
    conn = get_connection()
    cursor = conn.cursor()

    imported = 0
    errors = []

    for note in notes:
        try:
            account_num = note.get('account_number')
            if not account_num:
                continue

            # Find customer by account number
            cursor.execute(
                "SELECT id FROM customers WHERE account_number = ?",
                (account_num,)
            )
            row = cursor.fetchone()

            if row:
                customer_id = row['id']
                note_text = note.get('note_text', '')
                note_date = note.get('note_date')

                if note_date:
                    cursor.execute(
                        "INSERT INTO notes (customer_id, note_text, note_date) VALUES (?, ?, ?)",
                        (customer_id, note_text, note_date)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO notes (customer_id, note_text) VALUES (?, ?)",
                        (customer_id, note_text)
                    )
                imported += 1

        except Exception as e:
            errors.append(f"Error importing note for {note.get('account_number', 'unknown')}: {str(e)}")

    conn.commit()
    conn.close()

    return imported, errors


def update_next_account_number(new_value: int):
    """Update the next account number setting."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'next_account_number'",
        (str(new_value),)
    )

    conn.commit()
    conn.close()


def get_highest_account_number() -> Optional[int]:
    """Get the highest account number currently in the database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT account_number FROM customers
        WHERE account_number GLOB '[0-9]*'
        ORDER BY CAST(account_number AS INTEGER) DESC
        LIMIT 1
    """)
    row = cursor.fetchone()

    conn.close()

    if row:
        try:
            return int(row['account_number'])
        except ValueError:
            return None
    return None


# Initialize database on module import
init_database()
