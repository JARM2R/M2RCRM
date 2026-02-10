"""
M2R CRM Database Schema Analyzer
================================
Analyzes the Access database schema for CRM app design.
"""

import pyodbc
import sys
from typing import List, Dict, Any, Optional

DB_PATH = r"C:\Users\jeann\Work\M2 Reporter\M2R CRM\M2R 2021 CRM.accdb"

def get_connection_string(db_path: str) -> str:
    """Get ODBC connection string for Access database."""
    drivers = [d for d in pyodbc.drivers() if 'Access' in d]

    if not drivers:
        raise RuntimeError("No Access ODBC driver found.")

    for driver in drivers:
        try:
            conn_str = f'DRIVER={{{driver}}};DBQ={db_path};'
            conn = pyodbc.connect(conn_str, timeout=5)
            conn.close()
            return conn_str
        except pyodbc.Error:
            continue

    raise RuntimeError("Could not connect with any available driver.")

def get_tables(conn_str: str) -> List[str]:
    """Get list of user tables."""
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    tables = []
    for row in cursor.tables(tableType='TABLE'):
        table_name = row.table_name
        if not table_name.startswith('MSys') and not table_name.startswith('~'):
            tables.append(table_name)

    cursor.close()
    conn.close()
    return sorted(tables)

def get_columns_info(conn_str: str, table_name: str) -> List[Dict[str, Any]]:
    """Get detailed column information for a table."""
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    columns = []
    for row in cursor.columns(table=table_name):
        col_info = {
            'name': row.column_name,
            'type': row.type_name,
            'size': row.column_size,
            'nullable': row.nullable,
            'ordinal': row.ordinal_position
        }
        columns.append(col_info)

    cursor.close()
    conn.close()
    return columns

def get_row_count(conn_str: str, table_name: str) -> int:
    """Get row count for a table."""
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        count = cursor.fetchone()[0]
    except:
        count = -1

    cursor.close()
    conn.close()
    return count

def get_sample_data(conn_str: str, table_name: str, limit: int = 3) -> List[Dict]:
    """Get sample rows from a table."""
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT TOP {limit} * FROM [{table_name}]")
        columns = [col[0] for col in cursor.description]
        rows = []
        for row in cursor.fetchall():
            row_dict = {}
            for i, val in enumerate(row):
                # Mask potentially sensitive data
                col_name = columns[i].lower()
                if val is not None:
                    if any(s in col_name for s in ['ssn', 'social', 'password', 'credit', 'card']):
                        row_dict[columns[i]] = '***MASKED***'
                    elif any(s in col_name for s in ['email', 'phone', 'address', 'street']):
                        # Show structure but mask specific data
                        str_val = str(val)
                        if len(str_val) > 4:
                            row_dict[columns[i]] = str_val[:2] + '...' + str_val[-2:]
                        else:
                            row_dict[columns[i]] = '...'
                    else:
                        row_dict[columns[i]] = val
                else:
                    row_dict[columns[i]] = None
            rows.append(row_dict)
    except Exception as e:
        print(f"  Error getting sample: {e}")
        rows = []

    cursor.close()
    conn.close()
    return rows

def analyze_field_purposes(columns: List[Dict]) -> Dict[str, List[str]]:
    """Categorize fields by likely purpose."""
    categories = {
        'Serial/Account Numbers': [],
        'Contact Info': [],
        'Address Fields': [],
        'Dates (Paid Through, etc.)': [],
        'Subscription/Status': [],
        'Notes/Comments': [],
        'Identity/Names': [],
        'Other': []
    }

    for col in columns:
        name_lower = col['name'].lower()
        matched = False

        # Serial/Account Numbers
        if any(s in name_lower for s in ['serial', 'account', 'acct', 'license', 'key', 'registration']):
            categories['Serial/Account Numbers'].append(col['name'])
            matched = True

        # Contact Info
        elif any(s in name_lower for s in ['email', 'phone', 'fax', 'mobile', 'cell', 'tel']):
            categories['Contact Info'].append(col['name'])
            matched = True

        # Address
        elif any(s in name_lower for s in ['address', 'street', 'city', 'state', 'zip', 'postal', 'country']):
            categories['Address Fields'].append(col['name'])
            matched = True

        # Dates
        elif any(s in name_lower for s in ['date', 'paid', 'through', 'thru', 'expir', 'renew', 'subscri']):
            categories['Dates (Paid Through, etc.)'].append(col['name'])
            matched = True

        # Status
        elif any(s in name_lower for s in ['status', 'active', 'type', 'level', 'tier']):
            categories['Subscription/Status'].append(col['name'])
            matched = True

        # Notes
        elif any(s in name_lower for s in ['note', 'comment', 'memo', 'remark', 'description']):
            categories['Notes/Comments'].append(col['name'])
            matched = True

        # Names
        elif any(s in name_lower for s in ['name', 'first', 'last', 'company', 'business', 'contact']):
            categories['Identity/Names'].append(col['name'])
            matched = True

        if not matched:
            categories['Other'].append(col['name'])

    return categories

def main():
    print("=" * 70)
    print("M2R CRM DATABASE SCHEMA ANALYSIS")
    print("=" * 70)
    print(f"\nDatabase: {DB_PATH}\n")

    try:
        conn_str = get_connection_string(DB_PATH)
        print("Successfully connected to database.\n")
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    # Get all tables
    tables = get_tables(conn_str)
    print(f"Found {len(tables)} user tables:\n")

    for i, table in enumerate(tables, 1):
        print(f"  {i}. {table}")

    print("\n" + "=" * 70)
    print("DETAILED TABLE ANALYSIS")
    print("=" * 70)

    # Track likely main tables
    likely_contacts_tables = []

    for table in tables:
        print(f"\n{'='*70}")
        print(f"TABLE: {table}")
        print("=" * 70)

        # Get row count
        row_count = get_row_count(conn_str, table)
        print(f"Row Count: {row_count}")

        # Get columns
        columns = get_columns_info(conn_str, table)
        print(f"Column Count: {len(columns)}")

        print("\nCOLUMNS:")
        print("-" * 60)
        print(f"{'#':<4} {'Column Name':<30} {'Type':<15} {'Size':<8} {'Null?':<6}")
        print("-" * 60)

        for col in columns:
            nullable = 'Yes' if col['nullable'] else 'No'
            size = col['size'] if col['size'] else '-'
            print(f"{col['ordinal']:<4} {col['name']:<30} {col['type']:<15} {str(size):<8} {nullable:<6}")

        # Categorize fields
        categories = analyze_field_purposes(columns)

        print("\nFIELD CATEGORIES:")
        print("-" * 40)
        for category, fields in categories.items():
            if fields:
                print(f"\n{category}:")
                for f in fields:
                    print(f"  - {f}")

        # Check if this looks like a main contacts table
        has_names = bool(categories['Identity/Names'])
        has_contact = bool(categories['Contact Info'])
        is_large = row_count > 10

        if has_names and has_contact and is_large:
            likely_contacts_tables.append((table, row_count))

        # Get sample data (structure only, sensitive data masked)
        print("\nSAMPLE DATA (sensitive fields masked):")
        print("-" * 40)
        samples = get_sample_data(conn_str, table)
        for i, row in enumerate(samples, 1):
            print(f"\nRecord {i}:")
            for key, val in row.items():
                # Truncate long values for display
                if val is not None:
                    str_val = str(val)
                    if len(str_val) > 50:
                        str_val = str_val[:47] + "..."
                else:
                    str_val = "NULL"
                print(f"  {key}: {str_val}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY AND RECOMMENDATIONS")
    print("=" * 70)

    print("\nLIKELY MAIN CONTACTS/CUSTOMERS TABLE(S):")
    if likely_contacts_tables:
        for table, count in sorted(likely_contacts_tables, key=lambda x: -x[1]):
            print(f"  - {table} ({count} records)")
    else:
        print("  No obvious contacts table identified")

    print("\nKEY FIELDS TO LOOK FOR (across all tables):")

    all_columns = []
    for table in tables:
        cols = get_columns_info(conn_str, table)
        for col in cols:
            col['table'] = table
            all_columns.append(col)

    # Find specific field types
    print("\n  Serial/Account Number Fields:")
    for col in all_columns:
        if any(s in col['name'].lower() for s in ['serial', 'account', 'acct', 'license', 'key', 'registration']):
            print(f"    - {col['table']}.{col['name']} ({col['type']})")

    print("\n  Paid Through / Date Fields:")
    for col in all_columns:
        if any(s in col['name'].lower() for s in ['paid', 'through', 'thru', 'expir', 'renew']):
            print(f"    - {col['table']}.{col['name']} ({col['type']})")

    print("\n  Notes/Comments Fields:")
    for col in all_columns:
        if any(s in col['name'].lower() for s in ['note', 'comment', 'memo', 'remark']):
            print(f"    - {col['table']}.{col['name']} ({col['type']})")

    print("\n  Status/Subscription Fields:")
    for col in all_columns:
        if any(s in col['name'].lower() for s in ['status', 'subscription', 'subscribed', 'active']):
            print(f"    - {col['table']}.{col['name']} ({col['type']})")

    print("\n" + "=" * 70)
    print("END OF ANALYSIS")
    print("=" * 70)

if __name__ == "__main__":
    main()
