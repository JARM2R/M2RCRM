"""
M2R CRM UI Components
=====================
Tkinter UI components for the M2R CRM application.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
from typing import Callable, Optional, Dict, Any, List

try:
    from tkcalendar import DateEntry
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False

import m2r_crm_database as db


class CustomerListPanel(ttk.Frame):
    """Panel containing the customer list with search and filter controls."""

    def __init__(self, parent, on_select: Callable[[int], None]):
        super().__init__(parent)
        self.on_select = on_select
        self._create_widgets()
        self.refresh()

    def _create_widgets(self):
        # Search and filter frame
        controls_frame = ttk.Frame(self)
        controls_frame.pack(fill="x", padx=5, pady=5)

        # New Customer button (branded)
        self.new_btn = ttk.Button(controls_frame, text="+ New Customer", command=self._on_new,
                                  style="Accent.TButton")
        self.new_btn.pack(side="left", padx=(0, 10))

        # Search
        ttk.Label(controls_frame, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_search())
        self.search_entry = ttk.Entry(controls_frame, textvariable=self.search_var, width=25)
        self.search_entry.pack(side="left", padx=(5, 3))

        self.clear_search_btn = ttk.Button(controls_frame, text="Clear", width=5,
                                            command=lambda: self.search_var.set(""))
        self.clear_search_btn.pack(side="left", padx=(0, 10))

        # Filter
        ttk.Label(controls_frame, text="Filter:").pack(side="left")
        self.filter_var = tk.StringVar(value="Active")
        self.filter_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.filter_var,
            values=["Active", "Retired", "All"],
            state="readonly",
            width=10
        )
        self.filter_combo.pack(side="left", padx=5)
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        # Customer list
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # Treeview with scrollbar
        columns = ("account", "company", "contact", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("account", text="Account #", command=lambda: self._sort_by("account_number"))
        self.tree.heading("company", text="Company", command=lambda: self._sort_by("company_name"))
        self.tree.heading("contact", text="Contact", command=lambda: self._sort_by("contact_name"))
        self.tree.heading("status", text="Status", command=lambda: self._sort_by("subscription_status"))

        self.tree.column("account", width=85, minwidth=50, stretch=False)
        self.tree.column("company", width=190, minwidth=80)
        self.tree.column("contact", width=140, minwidth=60)
        self.tree.column("status", width=55, minwidth=30, stretch=False)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # Count label
        self.count_label = ttk.Label(self, text="0 customers")
        self.count_label.pack(anchor="w", padx=5, pady=(0, 5))

        # Sort state
        self._sort_column = "company_name"
        self._sort_dir = "ASC"

        # For new customer callback
        self._on_new_callback = None

    def set_new_callback(self, callback: Callable[[], None]):
        """Set the callback for New Customer button."""
        self._on_new_callback = callback

    def _on_new(self):
        if self._on_new_callback:
            self._on_new_callback()

    def _on_search(self):
        """Handle search input with debounce."""
        if hasattr(self, '_search_after_id'):
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(300, self.refresh)

    def _sort_by(self, column: str):
        """Sort by column, toggling direction."""
        if self._sort_column == column:
            self._sort_dir = "DESC" if self._sort_dir == "ASC" else "ASC"
        else:
            self._sort_column = column
            self._sort_dir = "ASC"
        self.refresh()

    def refresh(self):
        """Refresh the customer list."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Get customers
        customers = db.search_customers(
            search_term=self.search_var.get(),
            filter_status=self.filter_var.get(),
            order_by=self._sort_column,
            order_dir=self._sort_dir
        )

        # Populate tree
        for customer in customers:
            status = "Yes" if customer.get('subscription_status') == 'YES' else "No"
            if customer.get('is_retired'):
                status = "Retired"

            self.tree.insert("", "end",
                iid=str(customer['id']),
                values=(
                    customer.get('account_number', ''),
                    customer.get('company_name', ''),
                    customer.get('contact_name', ''),
                    status
                )
            )

        # Update count
        count = len(customers)
        self.count_label.config(text=f"{count} customer{'s' if count != 1 else ''}")

    def _on_tree_select(self, event):
        """Handle tree selection."""
        selection = self.tree.selection()
        if selection:
            customer_id = int(selection[0])
            self.on_select(customer_id)

    def _on_tree_double_click(self, event):
        """Handle double-click on tree item."""
        self._on_tree_select(event)

    def select_customer(self, customer_id: int):
        """Select a customer in the tree by ID."""
        item_id = str(customer_id)
        if self.tree.exists(item_id):
            self.tree.selection_set(item_id)
            self.tree.see(item_id)
            self.tree.focus(item_id)

    def get_selected_id(self) -> Optional[int]:
        """Get the currently selected customer ID."""
        selection = self.tree.selection()
        if selection:
            return int(selection[0])
        return None


class CustomerFormPanel(ttk.Frame):
    """Panel containing the customer detail form."""

    def __init__(self, parent, on_save: Callable[[Dict], None], on_delete: Callable[[int], None]):
        super().__init__(parent)
        self.on_save = on_save
        self.on_delete = on_delete
        self.current_customer_id: Optional[int] = None
        self._saved_form_data: Optional[Dict[str, Any]] = None
        self._original_account_number: Optional[str] = None
        self._create_widgets()

    def _create_widgets(self):
        # Main container with scrollbar
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Form content
        form = self.scrollable_frame
        row = 0

        # Title and Buttons row
        btn_frame = ttk.Frame(form)
        btn_frame.grid(row=row, column=0, columnspan=7, sticky="w", padx=10, pady=(10, 15))

        ttk.Label(btn_frame, text="Customer Details", font=("Segoe UI", 12, "bold")).pack(side="left")

        self.save_btn = ttk.Button(btn_frame, text="Save", command=self._on_save, width=8,
                                    style="Accent.TButton")
        self.save_btn.pack(side="left", padx=(15, 3))

        self.delete_btn = ttk.Button(btn_frame, text="Delete", command=self._on_delete, width=8)
        self.delete_btn.pack(side="left", padx=3)

        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=8)
        self.cancel_btn.pack(side="left", padx=3)
        row += 1

        # === ROW 1: Account # (left) | AP Email (middle) ===
        ttk.Label(form, text="Account #:").grid(row=row, column=0, sticky="e", padx=(10, 5), pady=3)
        self.account_var = tk.StringVar()
        self.account_entry = ttk.Entry(form, textvariable=self.account_var, width=15)
        self.account_entry.grid(row=row, column=1, sticky="w", pady=3)
        self.account_entry.bind("<FocusOut>", self._on_account_number_change)
        self.auto_btn = ttk.Button(form, text="Auto", width=6, command=self._generate_account)
        self.auto_btn.grid(row=row, column=2, sticky="w", padx=5, pady=3)

        ttk.Label(form, text="AP Email:").grid(row=row, column=3, sticky="e", padx=(15, 5), pady=3)
        self.email_ap_var = tk.StringVar()
        self.email_ap_entry = ttk.Entry(form, textvariable=self.email_ap_var, width=30)
        self.email_ap_entry.grid(row=row, column=4, sticky="w", pady=3)

        # License Info section - far right, spans rows 1-5
        license_frame = ttk.LabelFrame(form, text="License Info", padding=8)
        license_frame.grid(row=row, column=5, rowspan=5, sticky="nsew", padx=(15, 10), pady=3)

        ttk.Label(license_frame, text="License:").grid(row=0, column=0, sticky="e", padx=(0, 5), pady=3)
        self.license_var = tk.StringVar()
        self.license_combo = ttk.Combobox(
            license_frame,
            textvariable=self.license_var,
            values=["Basic Standard", "Basic Network", "Professional", "Enterprise", "Trial", "Demo"],
            width=18
        )
        self.license_combo.grid(row=0, column=1, sticky="w", pady=3)

        ttk.Label(license_frame, text="Version:").grid(row=1, column=0, sticky="e", padx=(0, 5), pady=3)
        self.version_var = tk.StringVar()
        self.version_entry = ttk.Entry(license_frame, textvariable=self.version_var, width=20)
        self.version_entry.grid(row=1, column=1, sticky="w", pady=3)

        ttk.Label(license_frame, text="Auth Date:").grid(row=2, column=0, sticky="e", padx=(0, 5), pady=3)
        if CALENDAR_AVAILABLE:
            self.auth_date_entry = DateEntry(license_frame, width=12, date_pattern='mm/dd/yyyy')
            self.auth_date_entry.delete(0, "end")
        else:
            self.auth_date_var = tk.StringVar()
            self.auth_date_entry = ttk.Entry(license_frame, textvariable=self.auth_date_var, width=15)
        self.auth_date_entry.grid(row=2, column=1, sticky="w", pady=3)

        ttk.Label(license_frame, text="Paid Through:").grid(row=3, column=0, sticky="e", padx=(0, 5), pady=3)
        if CALENDAR_AVAILABLE:
            self.paid_date_entry = DateEntry(license_frame, width=12, date_pattern='mm/dd/yyyy')
            self.paid_date_entry.delete(0, "end")
        else:
            self.paid_date_var = tk.StringVar()
            self.paid_date_entry = ttk.Entry(license_frame, textvariable=self.paid_date_var, width=15)
        self.paid_date_entry.grid(row=3, column=1, sticky="w", pady=3)

        ttk.Label(license_frame, text="Support Amt:").grid(row=4, column=0, sticky="e", padx=(0, 5), pady=3)
        self.support_amt_var = tk.StringVar()
        self.support_amt_entry = ttk.Entry(license_frame, textvariable=self.support_amt_var, width=15)
        self.support_amt_entry.grid(row=4, column=1, sticky="w", pady=3)

        row += 1

        # === ROW 2: Company (left) | User Email (middle) ===
        ttk.Label(form, text="Company:").grid(row=row, column=0, sticky="e", padx=(10, 5), pady=3)
        self.company_var = tk.StringVar()
        self.company_entry = ttk.Entry(form, textvariable=self.company_var, width=30)
        self.company_entry.grid(row=row, column=1, columnspan=2, sticky="w", pady=3)

        ttk.Label(form, text="User Email:").grid(row=row, column=3, sticky="e", padx=(15, 5), pady=3)
        self.email_user_var = tk.StringVar()
        self.email_user_entry = ttk.Entry(form, textvariable=self.email_user_var, width=30)
        self.email_user_entry.grid(row=row, column=4, sticky="w", pady=3)
        row += 1

        # === ROW 3: Contact (left) | IT Email (middle) ===
        ttk.Label(form, text="Contact:").grid(row=row, column=0, sticky="e", padx=(10, 5), pady=3)
        self.contact_var = tk.StringVar()
        self.contact_entry = ttk.Entry(form, textvariable=self.contact_var, width=30)
        self.contact_entry.grid(row=row, column=1, columnspan=2, sticky="w", pady=3)

        ttk.Label(form, text="IT Email:").grid(row=row, column=3, sticky="e", padx=(15, 5), pady=3)
        self.email_it_var = tk.StringVar()
        self.email_it_entry = ttk.Entry(form, textvariable=self.email_it_var, width=30)
        self.email_it_entry.grid(row=row, column=4, sticky="w", pady=3)
        row += 1

        # === ROW 4: Phone (left) ===
        ttk.Label(form, text="Phone:").grid(row=row, column=0, sticky="e", padx=(10, 5), pady=3)
        phone_frame = ttk.Frame(form)
        phone_frame.grid(row=row, column=1, columnspan=2, sticky="w", pady=3)
        self.phone_var = tk.StringVar()
        self._phone_formatting = False  # Flag to prevent recursive formatting
        self.phone_var.trace_add("write", self._format_phone_number)
        self.phone_entry = ttk.Entry(phone_frame, textvariable=self.phone_var, width=15)
        self.phone_entry.pack(side="left")
        ttk.Label(phone_frame, text="Ext:").pack(side="left", padx=(10, 5))
        self.ext_var = tk.StringVar()
        self.ext_entry = ttk.Entry(phone_frame, textvariable=self.ext_var, width=6)
        self.ext_entry.pack(side="left")
        row += 1

        # === ROW 5: Address (left) ===
        ttk.Label(form, text="Address:").grid(row=row, column=0, sticky="e", padx=(10, 5), pady=3)
        self.street_var = tk.StringVar()
        self.street_entry = ttk.Entry(form, textvariable=self.street_var, width=30)
        self.street_entry.grid(row=row, column=1, columnspan=2, sticky="w", pady=3)
        row += 1

        # === ROW 6: City/St/Zip (left) ===
        ttk.Label(form, text="City/St/Zip:").grid(row=row, column=0, sticky="e", padx=(10, 5), pady=3)
        addr_frame = ttk.Frame(form)
        addr_frame.grid(row=row, column=1, columnspan=2, sticky="w", pady=3)
        self.city_var = tk.StringVar()
        self.city_entry = ttk.Entry(addr_frame, textvariable=self.city_var, width=15)
        self.city_entry.pack(side="left")
        self.state_var = tk.StringVar()
        self.state_entry = ttk.Entry(addr_frame, textvariable=self.state_var, width=5)
        self.state_entry.pack(side="left", padx=(5, 0))
        self.zip_var = tk.StringVar()
        self.zip_entry = ttk.Entry(addr_frame, textvariable=self.zip_var, width=10)
        self.zip_entry.pack(side="left", padx=(5, 0))

        # Bureau IDs section - far right, spans rows 6-10 (same height as License Info)
        bureau_frame = ttk.LabelFrame(form, text="Bureau IDs", padding=8)
        bureau_frame.grid(row=row, column=5, rowspan=5, sticky="nsew", padx=(15, 10), pady=3)

        ttk.Label(bureau_frame, text="Company ID:").grid(row=0, column=0, sticky="e", padx=(0, 5), pady=3)
        self.company_id_var = tk.StringVar()
        self.company_id_entry = ttk.Entry(bureau_frame, textvariable=self.company_id_var, width=18)
        self.company_id_entry.grid(row=0, column=1, sticky="w", pady=3)

        ttk.Label(bureau_frame, text="Equifax:").grid(row=1, column=0, sticky="e", padx=(0, 5), pady=3)
        self.bureau_equifax_var = tk.StringVar()
        self.bureau_equifax_entry = ttk.Entry(bureau_frame, textvariable=self.bureau_equifax_var, width=18)
        self.bureau_equifax_entry.grid(row=1, column=1, sticky="w", pady=3)

        ttk.Label(bureau_frame, text="Experian:").grid(row=2, column=0, sticky="e", padx=(0, 5), pady=3)
        self.bureau_experian_var = tk.StringVar()
        self.bureau_experian_entry = ttk.Entry(bureau_frame, textvariable=self.bureau_experian_var, width=18)
        self.bureau_experian_entry.grid(row=2, column=1, sticky="w", pady=3)

        ttk.Label(bureau_frame, text="TransUnion:").grid(row=3, column=0, sticky="e", padx=(0, 5), pady=3)
        self.bureau_transunion_var = tk.StringVar()
        self.bureau_transunion_entry = ttk.Entry(bureau_frame, textvariable=self.bureau_transunion_var, width=18)
        self.bureau_transunion_entry.grid(row=3, column=1, sticky="w", pady=3)

        row += 1

        # === ROW 7-9: empty left rows for bureau section to span ===
        row += 1
        row += 1
        row += 1

        # === ROW 10: Status + Retired + Checkboxes ===
        status_frame = ttk.Frame(form)
        status_frame.grid(row=row, column=0, columnspan=6, sticky="w", padx=(10, 0), pady=3)
        ttk.Label(status_frame, text="Status:").pack(side="left", padx=(0, 5))
        self.status_var = tk.StringVar(value="NO")
        self.status_combo = ttk.Combobox(
            status_frame,
            textvariable=self.status_var,
            values=["YES", "NO"],
            state="readonly",
            width=6
        )
        self.status_combo.pack(side="left")
        self.retired_var = tk.BooleanVar()
        self.retired_check = ttk.Checkbutton(status_frame, text="Retired", variable=self.retired_var)
        self.retired_check.pack(side="left", padx=(15, 0))
        self.no_support_var = tk.BooleanVar()
        ttk.Checkbutton(status_frame, text="No Support", variable=self.no_support_var).pack(side="left", padx=(15, 0))
        self.support_inv_var = tk.BooleanVar()
        ttk.Checkbutton(status_frame, text="Support Invoice", variable=self.support_inv_var).pack(side="left", padx=(10, 0))
        self.no_inv_var = tk.BooleanVar()
        ttk.Checkbutton(status_frame, text="No Invoice", variable=self.no_inv_var).pack(side="left", padx=(10, 0))
        row += 1

        # Separator
        ttk.Separator(form, orient="horizontal").grid(row=row, column=0, columnspan=6, sticky="ew", pady=10, padx=10)
        row += 1

        # Note to Customer
        ttk.Label(form, text="Note to Customer:").grid(row=row, column=0, sticky="ne", padx=(10, 5), pady=3)
        self.note_customer_text = tk.Text(form, width=60, height=3)
        self.note_customer_text.grid(row=row, column=1, columnspan=4, sticky="w", pady=3)
        row += 1

        # Memo to Self
        ttk.Label(form, text="Memo to Self:").grid(row=row, column=0, sticky="ne", padx=(10, 5), pady=3)
        self.memo_text = tk.Text(form, width=60, height=3)
        self.memo_text.grid(row=row, column=1, columnspan=4, sticky="w", pady=3)
        row += 1

        # Separator
        ttk.Separator(form, orient="horizontal").grid(row=row, column=0, columnspan=6, sticky="ew", pady=10, padx=10)
        row += 1

        # Invoice dates (read-only display) - in a row
        ttk.Label(form, text="Last Invoice:").grid(row=row, column=0, sticky="e", padx=(10, 5), pady=3)
        self.last_inv_label = ttk.Label(form, text="-")
        self.last_inv_label.grid(row=row, column=1, sticky="w", pady=3)

        ttk.Label(form, text="Last Past Due:").grid(row=row, column=2, sticky="e", padx=(10, 5), pady=3)
        self.last_past_due_label = ttk.Label(form, text="-")
        self.last_past_due_label.grid(row=row, column=3, sticky="w", pady=3)

        ttk.Label(form, text="Last CSV:").grid(row=row, column=4, sticky="e", padx=(10, 5), pady=3)
        self.last_csv_label = ttk.Label(form, text="-")
        self.last_csv_label.grid(row=row, column=5, sticky="w", pady=3)

    def _generate_account(self):
        """Generate next account number."""
        # Check if this is an existing customer
        if self.current_customer_id and self._original_account_number:
            next_num = db.get_next_account_number()
            result = messagebox.askyesno(
                "Change Account Number",
                f"You are changing the account number from:\n"
                f"  {self._original_account_number}\n"
                f"to:\n"
                f"  {next_num}\n\n"
                f"Do you want to keep this change?",
                icon="warning"
            )
            if not result:
                return  # User cancelled, don't change

        next_num = db.get_next_account_number()
        self.account_var.set(next_num)

    def _on_account_number_change(self, event=None):
        """Check if account number was changed on an existing customer."""
        # Only check for existing customers
        if not self.current_customer_id or not self._original_account_number:
            return

        current_value = self.account_var.get().strip()

        # If unchanged, nothing to do
        if current_value == self._original_account_number:
            return

        # Warn user about changing account number
        result = messagebox.askyesno(
            "Change Account Number",
            f"You are changing the account number from:\n"
            f"  {self._original_account_number}\n"
            f"to:\n"
            f"  {current_value}\n\n"
            f"Do you want to keep this change?",
            icon="warning"
        )

        if not result:
            # Revert to original account number
            self.account_var.set(self._original_account_number)

    def _format_phone_number(self, *args):
        """Auto-format phone number as (XXX)XXX-XXXX."""
        if self._phone_formatting:
            return

        self._phone_formatting = True
        try:
            # Get current value and cursor position
            current = self.phone_var.get()

            # Extract only digits
            digits = ''.join(c for c in current if c.isdigit())

            # Limit to 10 digits
            digits = digits[:10]

            # Format based on number of digits
            if len(digits) == 0:
                formatted = ""
            elif len(digits) <= 3:
                formatted = f"({digits}"
            elif len(digits) <= 6:
                formatted = f"({digits[:3]}){digits[3:]}"
            else:
                formatted = f"({digits[:3]}){digits[3:6]}-{digits[6:]}"

            # Only update if different to avoid cursor issues
            if current != formatted:
                self.phone_var.set(formatted)
                # Move cursor to end
                self.phone_entry.icursor(len(formatted))
        finally:
            self._phone_formatting = False

    def load_customer(self, customer_id: int):
        """Load a customer into the form."""
        customer = db.get_customer(customer_id)
        if not customer:
            return

        self.clear_form()
        self.current_customer_id = customer_id

        # Basic info
        self.account_var.set(customer.get('account_number', ''))
        self._original_account_number = customer.get('account_number', '')
        self.company_var.set(customer.get('company_name', ''))
        self.contact_var.set(customer.get('contact_name', ''))
        self.email_ap_var.set(customer.get('email_ap', '') or customer.get('email', ''))
        self.email_user_var.set(customer.get('email_user', '') or '')
        self.email_it_var.set(customer.get('email_it', '') or '')
        self.phone_var.set(customer.get('phone', ''))
        self.ext_var.set(customer.get('phone_extension', ''))

        # Address
        self.street_var.set(customer.get('address_street', ''))
        self.city_var.set(customer.get('address_city', ''))
        self.state_var.set(customer.get('address_state', ''))
        self.zip_var.set(customer.get('address_zip', ''))

        # License info
        self.license_var.set(customer.get('license_type', ''))
        self.version_var.set(customer.get('software_version', ''))
        self.company_id_var.set(customer.get('company_id', '') or '')
        self.bureau_equifax_var.set(customer.get('bureau_equifax', '') or customer.get('bureau_id', '') or '')
        self.bureau_experian_var.set(customer.get('bureau_experian', '') or '')
        self.bureau_transunion_var.set(customer.get('bureau_transunion', '') or '')

        # Dates
        self._set_date_entry(self.auth_date_entry, customer.get('auth_date'))
        self._set_date_entry(self.paid_date_entry, customer.get('paid_through_date'))

        # Financial
        amt = customer.get('support_amount')
        self.support_amt_var.set(f"{amt:.2f}" if amt else "")

        # Status
        self.status_var.set(customer.get('subscription_status', 'NO'))
        self.retired_var.set(bool(customer.get('is_retired', 0)))
        self.no_support_var.set(bool(customer.get('no_support', 0)))
        self.support_inv_var.set(bool(customer.get('support_invoice', 0)))
        self.no_inv_var.set(bool(customer.get('no_invoice', 0)))

        # Notes
        self.note_customer_text.delete("1.0", "end")
        self.note_customer_text.insert("1.0", customer.get('note_to_customer', '') or '')

        self.memo_text.delete("1.0", "end")
        self.memo_text.insert("1.0", customer.get('memo_to_self', '') or '')

        # Invoice dates (display only)
        self._format_date_label(self.last_inv_label, customer.get('last_invoice_date'))
        self._format_date_label(self.last_past_due_label, customer.get('last_invoice_past_due'))
        self._format_date_label(self.last_csv_label, customer.get('last_csv_create_date'))

        # Enable delete button
        self.delete_btn.config(state="normal")

        # Store form state for change detection
        self._store_form_state()

    def _set_date_entry(self, entry, date_value):
        """Set a date entry value."""
        if CALENDAR_AVAILABLE:
            entry.delete(0, "end")
            if date_value:
                try:
                    if isinstance(date_value, str):
                        dt = datetime.fromisoformat(date_value)
                        entry.set_date(dt.date())
                    elif isinstance(date_value, date):
                        entry.set_date(date_value)
                except:
                    pass
        else:
            var = getattr(entry, 'textvariable', None)
            if var:
                if date_value:
                    try:
                        if isinstance(date_value, str):
                            dt = datetime.fromisoformat(date_value)
                            entry.delete(0, "end")
                            entry.insert(0, dt.strftime("%m/%d/%Y"))
                        elif isinstance(date_value, date):
                            entry.delete(0, "end")
                            entry.insert(0, date_value.strftime("%m/%d/%Y"))
                    except:
                        pass

    def _format_date_label(self, label, date_value):
        """Format a date for display in a label."""
        if date_value:
            try:
                if isinstance(date_value, str):
                    dt = datetime.fromisoformat(date_value)
                    label.config(text=dt.strftime("%m/%d/%Y"))
                elif isinstance(date_value, date):
                    label.config(text=date_value.strftime("%m/%d/%Y"))
                else:
                    label.config(text="-")
            except:
                label.config(text="-")
        else:
            label.config(text="-")

    def _get_date_value(self, entry) -> Optional[str]:
        """Get date value from entry as ISO format string."""
        if CALENDAR_AVAILABLE:
            try:
                date_str = entry.get()
                if not date_str:
                    return None
                dt = entry.get_date()
                return dt.isoformat()
            except:
                return None
        else:
            date_str = entry.get().strip()
            if not date_str:
                return None
            for fmt in ['%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.date().isoformat()
                except ValueError:
                    continue
            return None

    def clear_form(self):
        """Clear all form fields."""
        self.current_customer_id = None
        self._saved_form_data = None
        self._original_account_number = None

        self.account_var.set("")
        self.company_var.set("")
        self.contact_var.set("")
        self.email_ap_var.set("")
        self.email_user_var.set("")
        self.email_it_var.set("")
        self.phone_var.set("")
        self.ext_var.set("")
        self.street_var.set("")
        self.city_var.set("")
        self.state_var.set("")
        self.zip_var.set("")
        self.license_var.set("")
        self.version_var.set("")
        self.company_id_var.set("")
        self.bureau_equifax_var.set("")
        self.bureau_experian_var.set("")
        self.bureau_transunion_var.set("")
        self.support_amt_var.set("")
        self.status_var.set("NO")
        self.retired_var.set(False)
        self.no_support_var.set(False)
        self.support_inv_var.set(False)
        self.no_inv_var.set(False)

        if CALENDAR_AVAILABLE:
            self.auth_date_entry.delete(0, "end")
            self.paid_date_entry.delete(0, "end")
        else:
            self.auth_date_entry.delete(0, "end")
            self.paid_date_entry.delete(0, "end")

        self.note_customer_text.delete("1.0", "end")
        self.memo_text.delete("1.0", "end")

        self.last_inv_label.config(text="-")
        self.last_past_due_label.config(text="-")
        self.last_csv_label.config(text="-")

        # Disable delete for new customers
        self.delete_btn.config(state="disabled")

    def new_customer(self):
        """Prepare form for a new customer."""
        self.clear_form()
        self._generate_account()
        self.company_entry.focus()
        # Store form state for change detection
        self._store_form_state()

    def get_form_data(self) -> Dict[str, Any]:
        """Get all form data as a dictionary."""
        data = {
            'account_number': self.account_var.get().strip(),
            'company_name': self.company_var.get().strip(),
            'contact_name': self.contact_var.get().strip(),
            'email_ap': self.email_ap_var.get().strip(),
            'email_user': self.email_user_var.get().strip(),
            'email_it': self.email_it_var.get().strip(),
            'phone': self.phone_var.get().strip(),
            'phone_extension': self.ext_var.get().strip(),
            'address_street': self.street_var.get().strip(),
            'address_city': self.city_var.get().strip(),
            'address_state': self.state_var.get().strip(),
            'address_zip': self.zip_var.get().strip(),
            'license_type': self.license_var.get().strip(),
            'software_version': self.version_var.get().strip(),
            'company_id': self.company_id_var.get().strip(),
            'bureau_equifax': self.bureau_equifax_var.get().strip(),
            'bureau_experian': self.bureau_experian_var.get().strip(),
            'bureau_transunion': self.bureau_transunion_var.get().strip(),
            'auth_date': self._get_date_value(self.auth_date_entry),
            'paid_through_date': self._get_date_value(self.paid_date_entry),
            'subscription_status': self.status_var.get(),
            'is_retired': 1 if self.retired_var.get() else 0,
            'no_support': 1 if self.no_support_var.get() else 0,
            'support_invoice': 1 if self.support_inv_var.get() else 0,
            'no_invoice': 1 if self.no_inv_var.get() else 0,
            'note_to_customer': self.note_customer_text.get("1.0", "end-1c").strip(),
            'memo_to_self': self.memo_text.get("1.0", "end-1c").strip(),
        }

        # Parse support amount
        amt_str = self.support_amt_var.get().strip()
        if amt_str:
            try:
                data['support_amount'] = float(amt_str.replace(',', ''))
            except ValueError:
                data['support_amount'] = None
        else:
            data['support_amount'] = None

        return data

    def _store_form_state(self):
        """Store the current form state for change detection."""
        self._saved_form_data = self.get_form_data()

    def has_unsaved_changes(self) -> bool:
        """Check if the form has unsaved changes."""
        if self._saved_form_data is None:
            return False
        current_data = self.get_form_data()
        return current_data != self._saved_form_data

    def check_unsaved_changes(self) -> bool:
        """
        Check for unsaved changes and prompt user if needed.
        Returns True if OK to proceed, False if user wants to stay.
        """
        if not self.has_unsaved_changes():
            return True

        result = messagebox.askyesnocancel(
            "Unsaved Changes",
            "You have unsaved changes. Do you want to save before continuing?",
            icon="warning"
        )

        if result is None:  # Cancel
            return False
        elif result:  # Yes - save first
            self._on_save()
            return True
        else:  # No - discard changes
            return True

    def _on_save(self):
        """Handle save button click."""
        data = self.get_form_data()

        # Validate required fields
        if not data['account_number']:
            messagebox.showerror("Validation Error", "Account number is required.")
            self.account_entry.focus()
            return

        # Check account number uniqueness
        if not db.is_account_number_unique(data['account_number'], self.current_customer_id):
            messagebox.showerror("Validation Error", "Account number already exists.")
            self.account_entry.focus()
            return

        self.on_save(data)

    def _on_delete(self):
        """Handle delete button click."""
        if self.current_customer_id:
            self.on_delete(self.current_customer_id)

    def _on_cancel(self):
        """Handle cancel button click."""
        if self.current_customer_id:
            self.load_customer(self.current_customer_id)
        else:
            self.clear_form()


class NotesPanel(ttk.Frame):
    """Panel for displaying and adding customer notes."""

    def __init__(self, parent):
        super().__init__(parent)
        self.current_customer_id: Optional[int] = None
        self._create_widgets()

    def _create_widgets(self):
        # Title
        title_frame = ttk.Frame(self)
        title_frame.pack(fill="x", padx=5, pady=(10, 5))

        ttk.Label(title_frame, text="Notes", font=("Segoe UI", 11, "bold")).pack(side="left")

        # Notes list
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.notes_text = tk.Text(list_frame, height=8, state="disabled", wrap="word")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.notes_text.yview)
        self.notes_text.configure(yscrollcommand=scrollbar.set)

        self.notes_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Common notes dropdown
        common_frame = ttk.Frame(self)
        common_frame.pack(fill="x", padx=5, pady=(0, 3))

        ttk.Label(common_frame, text="Common:").pack(side="left")
        self.common_notes = [
            "Received order via web. Sent onboarding email to customer.",
            "Received onboarding registration from customer. Sent Activation Key.",
            "Received annual renewal. Updated paid through. Sent download reminder to customer.",
            "Annual renewal not paid. Retired account.",
        ]
        self.common_note_var = tk.StringVar()
        self.common_note_combo = ttk.Combobox(
            common_frame,
            textvariable=self.common_note_var,
            values=self.common_notes,
            state="readonly",
            width=70
        )
        self.common_note_combo.pack(side="left", padx=(5, 0), fill="x", expand=True)
        self.common_note_combo.bind("<<ComboboxSelected>>", self._on_common_note_selected)

        # Add note frame
        add_frame = ttk.Frame(self)
        add_frame.pack(fill="x", padx=5, pady=(0, 10))

        self.new_note_var = tk.StringVar()
        self.new_note_entry = ttk.Entry(add_frame, textvariable=self.new_note_var)
        self.new_note_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.new_note_entry.bind("<Return>", lambda e: self._add_note())

        self.add_btn = ttk.Button(add_frame, text="Add Note", command=self._add_note)
        self.add_btn.pack(side="left")

    def load_notes(self, customer_id: int):
        """Load notes for a customer."""
        self.current_customer_id = customer_id
        notes = db.get_notes(customer_id)

        self.notes_text.config(state="normal")
        self.notes_text.delete("1.0", "end")

        for note in notes:
            date_str = note.get('note_date', '')
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str)
                    date_str = dt.strftime("%m/%d/%Y %I:%M %p")
                except:
                    pass

            text = note.get('note_text', '')
            self.notes_text.insert("end", f"{date_str}\n{text}\n\n")

        self.notes_text.config(state="disabled")

        # Enable/disable add note
        self.add_btn.config(state="normal")
        self.new_note_entry.config(state="normal")

    def clear_notes(self):
        """Clear the notes display."""
        self.current_customer_id = None
        self.notes_text.config(state="normal")
        self.notes_text.delete("1.0", "end")
        self.notes_text.config(state="disabled")
        self.new_note_var.set("")
        self.add_btn.config(state="disabled")
        self.new_note_entry.config(state="disabled")

    def _add_note(self):
        """Add a new note."""
        if not self.current_customer_id:
            return

        note_text = self.new_note_var.get().strip()
        if not note_text:
            return

        db.create_note(self.current_customer_id, note_text)
        self.new_note_var.set("")
        self.common_note_combo.set("")
        self.load_notes(self.current_customer_id)

    def _on_common_note_selected(self, event):
        """Populate the note entry with the selected common note."""
        selected = self.common_note_var.get()
        if selected:
            self.new_note_var.set(selected)
