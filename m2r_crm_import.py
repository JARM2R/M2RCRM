"""
M2R CRM Import Module
=====================
Import functionality for migrating data from Access database to SQLite.
"""

import os
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple, Callable

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

import m2r_crm_database as db


# Field mappings from Access to SQLite
# Access field name -> SQLite field name
ACCESS_FIELD_MAPPINGS = {
    # Account/ID fields
    'PRSERIALNO': 'account_number',
    'SerialNo': 'account_number',
    'AccountNumber': 'account_number',
    'Account_Number': 'account_number',

    # Company/Contact info
    'CONAME': 'company_name',
    'CompanyName': 'company_name',
    'Company': 'company_name',
    'CONTACT': 'contact_name',
    'ContactName': 'contact_name',
    'Contact': 'contact_name',
    'EMAIL': 'email_ap',
    'Email': 'email_ap',
    'E-mail': 'email_ap',
    'EMAILAP': 'email_ap',
    'EmailAP': 'email_ap',
    'AP_EMAIL': 'email_ap',
    'APEmail': 'email_ap',
    'AP Email': 'email_ap',
    'EMAILUSER': 'email_user',
    'EmailUser': 'email_user',
    'USER_EMAIL': 'email_user',
    'UserEmail': 'email_user',
    'User Email': 'email_user',
    'EMAILIT': 'email_it',
    'EmailIT': 'email_it',
    'IT_EMAIL': 'email_it',
    'ITEmail': 'email_it',
    'IT Email': 'email_it',
    'PHONENO': 'phone',
    'PhoneNo': 'phone',
    'Phone': 'phone',
    'EXTENSION': 'phone_extension',
    'Extension': 'phone_extension',
    'Ext': 'phone_extension',

    # Address fields
    'ADDSTREET': 'address_street',
    'Address': 'address_street',
    'Street': 'address_street',
    'StreetAddress': 'address_street',
    'ADDCITY': 'address_city',
    'City': 'address_city',
    'ADDSTATE': 'address_state',
    'State': 'address_state',
    'ADDZIP': 'address_zip',
    'Zip': 'address_zip',
    'ZipCode': 'address_zip',
    'PostalCode': 'address_zip',

    # License/Software info
    'M2RLICENSE': 'license_type',
    'License': 'license_type',
    'LicenseType': 'license_type',
    'VERSION': 'software_version',
    'Version': 'software_version',
    'SoftwareVersion': 'software_version',
    'COMPANYID': 'company_id',
    'CompanyID': 'company_id',
    'Company_ID': 'company_id',
    'BUREAUID': 'bureau_equifax',
    'BureauID': 'bureau_equifax',
    'Bureau': 'bureau_equifax',
    'EQUIFAXID': 'bureau_equifax',
    'EquifaxID': 'bureau_equifax',
    'Equifax': 'bureau_equifax',
    'EXPERIANID': 'bureau_experian',
    'ExperianID': 'bureau_experian',
    'Experian': 'bureau_experian',
    'TRANSUNIONID': 'bureau_transunion',
    'TransUnionID': 'bureau_transunion',
    'TransUnion': 'bureau_transunion',

    # Dates
    'PRAUTHDATE': 'auth_date',
    'AuthDate': 'auth_date',
    'AuthorizationDate': 'auth_date',
    'PRPAIDDATE': 'paid_through_date',
    'PaidDate': 'paid_through_date',
    'PaidThrough': 'paid_through_date',
    'PaidThroughDate': 'paid_through_date',

    # Status/Flags
    'PRAUTHSTATUS': 'subscription_status',
    'AuthStatus': 'subscription_status',
    'Status': 'subscription_status',
    'PRSUPPAMT': 'support_amount',
    'SupportAmount': 'support_amount',
    'LRETIRED': 'is_retired',
    'Retired': 'is_retired',
    'IsRetired': 'is_retired',
    'LNOSUPP': 'no_support',
    'NoSupport': 'no_support',
    'LSUPPINV': 'support_invoice',
    'SupportInvoice': 'support_invoice',
    'LNOINV': 'no_invoice',
    'NoInvoice': 'no_invoice',

    # Notes/Memos
    'NOTE TO CUSTOMER': 'note_to_customer',
    'NoteToCustomer': 'note_to_customer',
    'CustomerNote': 'note_to_customer',
    'MEMO TO SELF': 'memo_to_self',
    'MemoToSelf': 'memo_to_self',
    'Memo': 'memo_to_self',

    # Invoice dates
    'LAST INVOICE DATE': 'last_invoice_date',
    'LastInvoiceDate': 'last_invoice_date',
    'LAST INVOICE PAST DUE DATE': 'last_invoice_past_due',
    'LastPastDueDate': 'last_invoice_past_due',
    'LAST CSV CREATE DATE': 'last_csv_create_date',
    'LastCSVDate': 'last_csv_create_date',
}


def get_access_connection_string(db_path: str) -> str:
    """Get ODBC connection string for Access database."""
    if not PYODBC_AVAILABLE:
        raise RuntimeError("pyodbc is required for Access import. Install with: pip install pyodbc")

    abs_path = os.path.abspath(db_path)

    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Database not found: {abs_path}")

    # Try to find Access driver
    drivers = [d for d in pyodbc.drivers() if 'Access' in d]

    for driver in drivers:
        try:
            conn_str = f'DRIVER={{{driver}}};DBQ={abs_path};'
            conn = pyodbc.connect(conn_str, timeout=5)
            conn.close()
            return conn_str
        except pyodbc.Error:
            continue

    raise RuntimeError(
        "No Access ODBC driver found. Install Microsoft Access Database Engine:\n"
        "https://www.microsoft.com/en-us/download/details.aspx?id=54920"
    )


def get_table_names(conn_str: str) -> List[str]:
    """Get list of user tables in the database."""
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    tables = []
    for row in cursor.tables(tableType='TABLE'):
        table_name = row.table_name
        # Skip system tables
        if not table_name.startswith('MSys') and not table_name.startswith('~'):
            tables.append(table_name)

    cursor.close()
    conn.close()
    return sorted(tables)


def get_table_columns(conn_str: str, table_name: str) -> List[str]:
    """Get list of column names for a table."""
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    columns = []
    for row in cursor.columns(table=table_name):
        columns.append(row.column_name)

    cursor.close()
    conn.close()
    return columns


def map_access_columns(access_columns: List[str]) -> Dict[str, str]:
    """
    Map Access column names to SQLite column names.

    Returns dict: {access_column: sqlite_column}
    """
    mapping = {}

    for access_col in access_columns:
        # Try exact match first
        if access_col in ACCESS_FIELD_MAPPINGS:
            mapping[access_col] = ACCESS_FIELD_MAPPINGS[access_col]
            continue

        # Try case-insensitive match
        access_col_lower = access_col.lower().replace(' ', '').replace('_', '')
        for known_col, sqlite_col in ACCESS_FIELD_MAPPINGS.items():
            known_lower = known_col.lower().replace(' ', '').replace('_', '')
            if access_col_lower == known_lower:
                mapping[access_col] = sqlite_col
                break

    return mapping


def format_value(value, target_type: str):
    """Format a value for insertion into SQLite."""
    if value is None:
        return None

    # Handle dates
    if target_type in ('auth_date', 'paid_through_date', 'last_invoice_date',
                       'last_invoice_past_due', 'last_csv_create_date'):
        if isinstance(value, datetime):
            return value.date().isoformat()
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, str):
            # Try to parse date string
            for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y']:
                try:
                    return datetime.strptime(value, fmt).date().isoformat()
                except ValueError:
                    continue
        return None

    # Handle booleans
    if target_type in ('is_retired', 'no_support', 'support_invoice', 'no_invoice'):
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, int):
            return 1 if value else 0
        if isinstance(value, str):
            return 1 if value.lower() in ('true', 'yes', '1', '-1') else 0
        return 0

    # Handle subscription status
    if target_type == 'subscription_status':
        if isinstance(value, bool):
            return 'YES' if value else 'NO'
        if isinstance(value, str):
            return 'YES' if value.upper() in ('YES', 'TRUE', '1') else 'NO'
        return 'NO'

    # Handle numbers
    if target_type == 'support_amount':
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    # Default: return as string
    if isinstance(value, str):
        return value.strip()
    return str(value) if value else None


def read_access_customers(conn_str: str, table_name: str, column_mapping: Dict[str, str]) -> List[Dict]:
    """Read customer records from Access database."""
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Build SELECT clause
    access_cols = list(column_mapping.keys())
    select_cols = ', '.join([f'[{col}]' for col in access_cols])

    cursor.execute(f"SELECT {select_cols} FROM [{table_name}]")
    rows = cursor.fetchall()

    customers = []
    for row in rows:
        customer = {}
        for i, access_col in enumerate(access_cols):
            sqlite_col = column_mapping[access_col]
            value = format_value(row[i], sqlite_col)
            if value is not None:
                customer[sqlite_col] = value
        customers.append(customer)

    cursor.close()
    conn.close()

    return customers


def read_access_notes(conn_str: str, notes_table: str, account_col: str,
                      note_col: str, date_col: Optional[str] = None) -> List[Dict]:
    """Read notes from Access database."""
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    if date_col:
        cursor.execute(f"SELECT [{account_col}], [{note_col}], [{date_col}] FROM [{notes_table}]")
    else:
        cursor.execute(f"SELECT [{account_col}], [{note_col}] FROM [{notes_table}]")

    rows = cursor.fetchall()

    notes = []
    for row in rows:
        note = {
            'account_number': str(row[0]).strip() if row[0] else None,
            'note_text': str(row[1]).strip() if row[1] else None,
        }

        if date_col and len(row) > 2 and row[2]:
            if isinstance(row[2], datetime):
                note['note_date'] = row[2].isoformat()
            elif isinstance(row[2], date):
                note['note_date'] = datetime.combine(row[2], datetime.min.time()).isoformat()

        if note['account_number'] and note['note_text']:
            notes.append(note)

    cursor.close()
    conn.close()

    return notes


def read_access_notes_with_join(conn_str: str, notes_table: str, customer_table: str,
                                 notes_id_col: str, customer_id_col: str, account_col: str,
                                 note_col: str, date_col: Optional[str] = None) -> List[Dict]:
    """
    Read notes from Access database using a JOIN to get account numbers.

    This handles the case where the notes table has a foreign key to the customer
    table (e.g., CustomerID) rather than the account number directly.
    """
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Build query with JOIN
    if date_col:
        sql = f"""
            SELECT c.[{account_col}], n.[{note_col}], n.[{date_col}]
            FROM [{notes_table}] n
            INNER JOIN [{customer_table}] c ON n.[{notes_id_col}] = c.[{customer_id_col}]
        """
    else:
        sql = f"""
            SELECT c.[{account_col}], n.[{note_col}]
            FROM [{notes_table}] n
            INNER JOIN [{customer_table}] c ON n.[{notes_id_col}] = c.[{customer_id_col}]
        """

    cursor.execute(sql)
    rows = cursor.fetchall()

    notes = []
    for row in rows:
        note = {
            'account_number': str(row[0]).strip() if row[0] else None,
            'note_text': str(row[1]).strip() if row[1] else None,
        }

        if date_col and len(row) > 2 and row[2]:
            if isinstance(row[2], datetime):
                note['note_date'] = row[2].isoformat()
            elif isinstance(row[2], date):
                note['note_date'] = datetime.combine(row[2], datetime.min.time()).isoformat()

        if note['account_number'] and note['note_text']:
            notes.append(note)

    cursor.close()
    conn.close()

    return notes


class ImportDialog(tk.Toplevel):
    """Dialog for importing from Access database."""

    def __init__(self, parent, on_complete: Optional[Callable] = None):
        super().__init__(parent)
        self.title("Import from Access")
        self.geometry("600x550")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.on_complete = on_complete
        self.conn_str = None
        self.column_mapping = {}
        self.access_columns = []

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 600) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 550) // 2
        self.geometry(f"+{x}+{y}")

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill="both", expand=True)

        # Title
        ttk.Label(main_frame, text="Import from Access Database",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))

        # Database selection
        db_frame = ttk.LabelFrame(main_frame, text="Database", padding=10)
        db_frame.pack(fill="x", pady=(0, 10))

        db_row = ttk.Frame(db_frame)
        db_row.pack(fill="x")

        ttk.Label(db_row, text="File:").pack(side="left")
        self.db_path_var = tk.StringVar()
        self.db_path_entry = ttk.Entry(db_row, textvariable=self.db_path_var, width=50)
        self.db_path_entry.pack(side="left", padx=(5, 5), fill="x", expand=True)

        ttk.Button(db_row, text="Browse...", command=self._browse_db).pack(side="left")

        # Table selection
        table_row = ttk.Frame(db_frame)
        table_row.pack(fill="x", pady=(10, 0))

        ttk.Label(table_row, text="Customer Table:").pack(side="left")
        self.table_var = tk.StringVar()
        self.table_combo = ttk.Combobox(table_row, textvariable=self.table_var, state="readonly", width=30)
        self.table_combo.pack(side="left", padx=5)
        self.table_combo.bind("<<ComboboxSelected>>", self._on_table_selected)

        ttk.Button(table_row, text="Load Tables", command=self._load_tables).pack(side="left")

        # Column mapping display
        mapping_frame = ttk.LabelFrame(main_frame, text="Column Mapping", padding=10)
        mapping_frame.pack(fill="both", expand=True, pady=(0, 10))

        mapping_scroll = ttk.Scrollbar(mapping_frame)
        mapping_scroll.pack(side="right", fill="y")

        self.mapping_text = tk.Text(mapping_frame, height=10, state="disabled",
                                    yscrollcommand=mapping_scroll.set, font=("Consolas", 9))
        self.mapping_text.pack(fill="both", expand=True)
        mapping_scroll.config(command=self.mapping_text.yview)

        # Notes table (optional)
        notes_frame = ttk.LabelFrame(main_frame, text="Notes Import (Optional)", padding=10)
        notes_frame.pack(fill="x", pady=(0, 10))

        notes_row = ttk.Frame(notes_frame)
        notes_row.pack(fill="x")

        ttk.Label(notes_row, text="Notes Table:").pack(side="left")
        self.notes_table_var = tk.StringVar()
        self.notes_table_combo = ttk.Combobox(notes_row, textvariable=self.notes_table_var,
                                               state="readonly", width=25)
        self.notes_table_combo.pack(side="left", padx=5)
        self.notes_table_combo.bind("<<ComboboxSelected>>", self._on_notes_table_selected)

        # Link type selection
        link_row = ttk.Frame(notes_frame)
        link_row.pack(fill="x", pady=(5, 0))

        self.notes_link_type = tk.StringVar(value="join")
        ttk.Radiobutton(link_row, text="Link via Customer ID (join)",
                        variable=self.notes_link_type, value="join").pack(side="left")
        ttk.Radiobutton(link_row, text="Has Account # directly",
                        variable=self.notes_link_type, value="direct").pack(side="left", padx=(15, 0))

        notes_col_row = ttk.Frame(notes_frame)
        notes_col_row.pack(fill="x", pady=(5, 0))

        ttk.Label(notes_col_row, text="ID/Account Col:").pack(side="left")
        self.notes_account_var = tk.StringVar()
        self.notes_account_combo = ttk.Combobox(notes_col_row, textvariable=self.notes_account_var,
                                                 state="readonly", width=15)
        self.notes_account_combo.pack(side="left", padx=(5, 15))

        ttk.Label(notes_col_row, text="Note Col:").pack(side="left")
        self.notes_text_var = tk.StringVar()
        self.notes_text_combo = ttk.Combobox(notes_col_row, textvariable=self.notes_text_var,
                                              state="readonly", width=15)
        self.notes_text_combo.pack(side="left", padx=5)

        # Date column (optional)
        notes_date_row = ttk.Frame(notes_frame)
        notes_date_row.pack(fill="x", pady=(5, 0))

        ttk.Label(notes_date_row, text="Date Col (opt):").pack(side="left")
        self.notes_date_var = tk.StringVar()
        self.notes_date_combo = ttk.Combobox(notes_date_row, textvariable=self.notes_date_var,
                                              state="readonly", width=15)
        self.notes_date_combo.pack(side="left", padx=(5, 15))

        # Preview counts
        self.preview_label = ttk.Label(main_frame, text="")
        self.preview_label.pack(anchor="w", pady=(0, 10))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x")

        self.import_btn = ttk.Button(btn_frame, text="Import", command=self._do_import, state="disabled")
        self.import_btn.pack(side="left", padx=(0, 10))

        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left")

        self.status_var = tk.StringVar(value="Select an Access database to begin")
        ttk.Label(btn_frame, textvariable=self.status_var).pack(side="right")

    def _browse_db(self):
        """Browse for Access database."""
        path = filedialog.askopenfilename(
            title="Select Access Database",
            filetypes=[("Access Database", "*.accdb *.mdb"), ("All Files", "*.*")],
            parent=self
        )
        if path:
            self.db_path_var.set(path)
            self._load_tables()

    def _load_tables(self):
        """Load tables from database."""
        db_path = self.db_path_var.get()
        if not db_path:
            return

        if not os.path.exists(db_path):
            messagebox.showerror("Error", "Database file not found.", parent=self)
            return

        try:
            self.conn_str = get_access_connection_string(db_path)
            tables = get_table_names(self.conn_str)

            self.table_combo['values'] = tables
            self.notes_table_combo['values'] = ['(None)'] + tables

            # Try to auto-select customer table
            for table in tables:
                if 'customer' in table.lower() or 'client' in table.lower():
                    self.table_combo.set(table)
                    self._on_table_selected(None)
                    break

            # Try to auto-select notes table
            for table in tables:
                if 'note' in table.lower():
                    self.notes_table_combo.set(table)
                    self._on_notes_table_selected(None)
                    break

            self.status_var.set(f"Connected - {len(tables)} tables found")

        except Exception as e:
            messagebox.showerror("Connection Error", str(e), parent=self)
            self.status_var.set("Connection failed")

    def _on_table_selected(self, event):
        """Handle customer table selection."""
        table_name = self.table_var.get()
        if not table_name or not self.conn_str:
            return

        try:
            self.access_columns = get_table_columns(self.conn_str, table_name)
            self.column_mapping = map_access_columns(self.access_columns)

            self._update_mapping_display()
            self._update_preview()

            self.import_btn.config(state="normal" if self.column_mapping else "disabled")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to read table:\n{e}", parent=self)

    def _on_notes_table_selected(self, event):
        """Handle notes table selection."""
        table_name = self.notes_table_var.get()
        if not table_name or table_name == '(None)' or not self.conn_str:
            self.notes_account_combo['values'] = []
            self.notes_text_combo['values'] = []
            self.notes_date_combo['values'] = []
            return

        try:
            columns = get_table_columns(self.conn_str, table_name)
            self.notes_account_combo['values'] = columns
            self.notes_text_combo['values'] = columns
            self.notes_date_combo['values'] = ['(None)'] + columns

            # Try to auto-select columns
            for col in columns:
                col_lower = col.lower()
                # For ID/account column
                if 'customerid' in col_lower.replace(' ', '').replace('_', ''):
                    self.notes_account_combo.set(col)
                    self.notes_link_type.set("join")
                elif 'serial' in col_lower or 'account' in col_lower:
                    self.notes_account_combo.set(col)
                    self.notes_link_type.set("direct")
                # For note text column
                if 'note' in col_lower and 'date' not in col_lower and 'id' not in col_lower:
                    self.notes_text_combo.set(col)
                # For date column
                if 'date' in col_lower:
                    self.notes_date_combo.set(col)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to read notes table:\n{e}", parent=self)

    def _update_mapping_display(self):
        """Update the column mapping display."""
        self.mapping_text.config(state="normal")
        self.mapping_text.delete("1.0", "end")

        mapped_count = 0
        for access_col in self.access_columns:
            sqlite_col = self.column_mapping.get(access_col)
            if sqlite_col:
                status = f"[OK]  {access_col}  ->  {sqlite_col}"
                mapped_count += 1
            else:
                status = f"[--]  {access_col}  ->  (ignored)"
            self.mapping_text.insert("end", status + "\n")

        self.mapping_text.insert("end", f"\n{mapped_count} columns will be imported")
        self.mapping_text.config(state="disabled")

    def _update_preview(self):
        """Update the preview count."""
        if not self.conn_str or not self.table_var.get():
            return

        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM [{self.table_var.get()}]")
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()

            self.preview_label.config(text=f"Found {count} records to import")
        except:
            self.preview_label.config(text="")

    def _do_import(self):
        """Perform the import."""
        if not self.conn_str or not self.column_mapping:
            return

        table_name = self.table_var.get()
        if not table_name:
            messagebox.showerror("Error", "Please select a customer table.", parent=self)
            return

        # Confirm import
        result = messagebox.askyesno(
            "Confirm Import",
            "This will import customers from the Access database.\n"
            "Existing customers with matching account numbers will be skipped.\n\n"
            "Continue?",
            parent=self
        )
        if not result:
            return

        try:
            self.status_var.set("Reading customers...")
            self.update_idletasks()

            # Read customers
            customers = read_access_customers(self.conn_str, table_name, self.column_mapping)

            self.status_var.set(f"Importing {len(customers)} customers...")
            self.update_idletasks()

            # Import customers
            imported, skipped, errors = db.bulk_import_customers(customers)

            # Import notes if configured
            notes_imported = 0
            notes_table = self.notes_table_var.get()
            if notes_table and notes_table != '(None)':
                id_col = self.notes_account_var.get()
                text_col = self.notes_text_var.get()
                date_col = self.notes_date_var.get()
                if date_col == '(None)':
                    date_col = None

                if id_col and text_col:
                    self.status_var.set("Importing notes...")
                    self.update_idletasks()

                    link_type = self.notes_link_type.get()

                    if link_type == "join":
                        # Use JOIN to get account numbers from customer table
                        # Find the ID column and account column in customer table
                        customer_table = table_name
                        customer_id_col = "ID"  # Typically the auto-increment ID
                        account_col = None

                        # Find account column in mapping
                        for access_col, sqlite_col in self.column_mapping.items():
                            if sqlite_col == 'account_number':
                                account_col = access_col
                                break

                        if account_col:
                            notes = read_access_notes_with_join(
                                self.conn_str, notes_table, customer_table,
                                id_col, customer_id_col, account_col,
                                text_col, date_col
                            )
                            notes_imported, note_errors = db.bulk_import_notes(notes)
                            errors.extend(note_errors)
                        else:
                            errors.append("Could not find account number column for notes join")
                    else:
                        # Direct - account number is in notes table
                        notes = read_access_notes(self.conn_str, notes_table, id_col, text_col, date_col)
                        notes_imported, note_errors = db.bulk_import_notes(notes)
                        errors.extend(note_errors)

            # Update next account number
            highest = db.get_highest_account_number()
            if highest:
                current_next = int(db.get_next_account_number())
                if highest >= current_next:
                    db.update_next_account_number(highest + 1)

            # Show results
            message = f"Import Complete\n\n"
            message += f"Customers imported: {imported}\n"
            message += f"Customers skipped (duplicates): {skipped}\n"
            if notes_imported:
                message += f"Notes imported: {notes_imported}\n"

            if errors:
                message += f"\n{len(errors)} errors occurred."

            messagebox.showinfo("Import Complete", message, parent=self)

            self.status_var.set("Import complete")

            if self.on_complete:
                self.on_complete()

            self.destroy()

        except Exception as e:
            messagebox.showerror("Import Error", str(e), parent=self)
            self.status_var.set("Import failed")
