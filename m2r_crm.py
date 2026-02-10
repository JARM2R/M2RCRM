"""
M2R CRM Application
===================
Main entry point for the M2R CRM desktop application.

Usage:
    python m2r_crm.py
"""

import sys
import os
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from m2r_crm_paths import ASSET_DIR, ensure_writable_database
ensure_writable_database()

import m2r_crm_database as db
from m2r_crm_ui import CustomerListPanel, CustomerFormPanel, NotesPanel


class M2RCrmApp:
    """Main CRM application class."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("M2R CRM")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)

        # Set icon if available
        icon_path = ASSET_DIR / "m2r_crm.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except:
                pass

        self._setup_styles()
        self._create_menu()
        self._create_ui()
        self._create_statusbar()

        # Bind keyboard shortcuts
        self.root.bind("<Control-n>", lambda e: self._new_customer())
        self.root.bind("<Control-s>", lambda e: self._save_current())
        self.root.bind("<Control-f>", lambda e: self._focus_search())
        self.root.bind("<F5>", lambda e: self._refresh())

        self._update_status("Ready")

    # M2R Brand Colors
    PRIMARY_BLUE = "#144478"
    HOVER_BLUE = "#0F3A66"
    ACCENT_GREEN = "#B3CC48"
    SELECTION_GREEN = "#CEDE88"
    WHITE = "#FFFFFF"
    LIGHT_BG = "#F0F0F0"

    def _setup_styles(self):
        """Configure ttk styles with M2R branding."""
        style = ttk.Style()

        # Use clam theme as base (best for custom styling)
        available_themes = style.theme_names()
        if 'clam' in available_themes:
            style.theme_use('clam')
        elif 'vista' in available_themes:
            style.theme_use('vista')

        # Custom styles
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), foreground=self.PRIMARY_BLUE)
        style.configure("Heading.TLabel", font=("Segoe UI", 11, "bold"), foreground=self.PRIMARY_BLUE)

        # Treeview styling - M2R branded headers and selection
        style.configure("Treeview.Heading",
                        background=self.PRIMARY_BLUE,
                        foreground=self.WHITE,
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview.Heading",
                  background=[("active", self.HOVER_BLUE)])
        style.configure("Treeview",
                        rowheight=24,
                        font=("Segoe UI", 9))
        style.map("Treeview",
                  background=[("selected", self.SELECTION_GREEN)],
                  foreground=[("selected", "black")])

        # Button styling
        style.configure("TButton",
                        font=("Segoe UI", 9))
        style.configure("Accent.TButton",
                        background=self.PRIMARY_BLUE,
                        foreground=self.WHITE,
                        font=("Segoe UI", 9, "bold"))
        style.map("Accent.TButton",
                  background=[("active", self.HOVER_BLUE), ("pressed", self.HOVER_BLUE)])

        # LabelFrame styling
        style.configure("TLabelframe.Label",
                        foreground=self.PRIMARY_BLUE,
                        font=("Segoe UI", 9, "bold"))

        # Notebook/Tab styling
        style.configure("TNotebook.Tab",
                        font=("Segoe UI", 9))

    def _create_menu(self):
        """Create the menu bar with M2R branding."""
        menubar = tk.Menu(self.root, bg=self.PRIMARY_BLUE, fg=self.WHITE,
                         activebackground=self.HOVER_BLUE, activeforeground=self.WHITE,
                         font=("Segoe UI", 9))
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0, bg=self.WHITE, fg="black",
                           activebackground=self.SELECTION_GREEN, activeforeground="black")
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Customer", command=self._new_customer, accelerator="Ctrl+N")
        file_menu.add_separator()
        file_menu.add_command(label="Import from Access...", command=self._import_from_access)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_exit)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0, bg=self.WHITE, fg="black",
                           activebackground=self.SELECTION_GREEN, activeforeground="black")
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Save", command=self._save_current, accelerator="Ctrl+S")
        edit_menu.add_command(label="Refresh", command=self._refresh, accelerator="F5")

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0, bg=self.WHITE, fg="black",
                            activebackground=self.SELECTION_GREEN, activeforeground="black")
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Export Contacts...", command=self._export_contacts)
        tools_menu.add_separator()
        tools_menu.add_command(label="Database Statistics", command=self._show_statistics)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0, bg=self.WHITE, fg="black",
                           activebackground=self.SELECTION_GREEN, activeforeground="black")
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _create_ui(self):
        """Create the main user interface."""
        # App header bar with logo and title
        header_bar = tk.Frame(self.root, bg=self.PRIMARY_BLUE, height=45)
        header_bar.pack(fill="x")
        header_bar.pack_propagate(False)

        # Load logo for header
        logo_path = ASSET_DIR / "M2RLogo.png"
        if logo_path.exists() and PIL_AVAILABLE:
            try:
                pil_img = Image.open(str(logo_path))
                pil_img = pil_img.resize((32, 32), Image.LANCZOS)
                self._header_logo = ImageTk.PhotoImage(pil_img)
                tk.Label(header_bar, image=self._header_logo, bg=self.PRIMARY_BLUE).pack(side="left", padx=(10, 5), pady=5)
            except:
                pass

        tk.Label(header_bar, text="M2R CRM", bg=self.PRIMARY_BLUE, fg=self.WHITE,
                font=("Segoe UI", 14, "bold")).pack(side="left", padx=5, pady=5)

        tk.Label(header_bar, text="Customer Relationship Management", bg=self.PRIMARY_BLUE,
                fg=self.ACCENT_GREEN, font=("Segoe UI", 9)).pack(side="left", padx=(10, 0), pady=5)

        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True)

        # Create paned window for resizable panels
        paned = ttk.PanedWindow(main_frame, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=5, pady=5)

        # Left panel - Customer List
        left_frame = ttk.Frame(paned)
        self.customer_list = CustomerListPanel(left_frame, self._on_customer_select)
        self.customer_list.pack(fill="both", expand=True)
        self.customer_list.set_new_callback(self._new_customer)
        paned.add(left_frame, weight=1)

        # Right panel - Customer Details and Notes
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=7)

        # Right panel uses another paned window (vertical)
        right_paned = ttk.PanedWindow(right_frame, orient="vertical")
        right_paned.pack(fill="both", expand=True)

        # Customer Form
        form_frame = ttk.Frame(right_paned)
        self.customer_form = CustomerFormPanel(form_frame, self._save_customer, self._delete_customer)
        self.customer_form.pack(fill="both", expand=True)
        right_paned.add(form_frame, weight=3)

        # Notes Panel
        notes_frame = ttk.Frame(right_paned)
        self.notes_panel = NotesPanel(notes_frame)
        self.notes_panel.pack(fill="both", expand=True)
        right_paned.add(notes_frame, weight=1)

    def _create_statusbar(self):
        """Create the status bar with M2R branding."""
        self.statusbar = tk.Frame(self.root, bg=self.PRIMARY_BLUE, height=25)
        self.statusbar.pack(fill="x", side="bottom")

        self.status_label = tk.Label(self.statusbar, text="Ready", anchor="w",
                                     bg=self.PRIMARY_BLUE, fg=self.WHITE,
                                     font=("Segoe UI", 9))
        self.status_label.pack(side="left", padx=10, pady=3)

        # Database location
        db_label = tk.Label(self.statusbar, text=f"Database: {db.DB_PATH.name}", anchor="e",
                           bg=self.PRIMARY_BLUE, fg=self.WHITE,
                           font=("Segoe UI", 9))
        db_label.pack(side="right", padx=10, pady=3)

    def _update_status(self, message: str):
        """Update the status bar message."""
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def _on_customer_select(self, customer_id: int):
        """Handle customer selection from list."""
        # Check for unsaved changes before switching
        if not self.customer_form.check_unsaved_changes():
            return  # User cancelled, stay on current record

        self.customer_form.load_customer(customer_id)
        self.notes_panel.load_notes(customer_id)
        self._update_status(f"Loaded customer #{customer_id}")

    def _new_customer(self):
        """Create a new customer."""
        # Check for unsaved changes before creating new
        if not self.customer_form.check_unsaved_changes():
            return  # User cancelled, stay on current record

        self.customer_form.new_customer()
        self.notes_panel.clear_notes()
        self._update_status("New customer")

    def _save_customer(self, data: dict):
        """Save customer data."""
        customer_id = self.customer_form.current_customer_id

        try:
            if customer_id:
                # Update existing
                db.update_customer(customer_id, data)
                self._update_status(f"Customer #{customer_id} updated")
            else:
                # Create new
                customer_id = db.create_customer(data)

                # Increment account number counter if we used an auto-generated one
                next_num = db.get_next_account_number()
                if data['account_number'] == next_num:
                    db.increment_account_number()

                self.customer_form.current_customer_id = customer_id
                self.customer_form.delete_btn.config(state="normal")
                self._update_status(f"Customer #{customer_id} created")

            # Refresh list and select the customer
            self.customer_list.refresh()
            self.customer_list.select_customer(customer_id)

            # Update saved form state so changes are now tracked from this point
            self.customer_form._store_form_state()

            messagebox.showinfo("Success", "Customer saved successfully.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save customer:\n{str(e)}")

    def _delete_customer(self, customer_id: int):
        """Delete a customer."""
        customer = db.get_customer(customer_id)
        if not customer:
            return

        company = customer.get('company_name') or customer.get('account_number')
        result = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete customer:\n{company}?\n\n"
            "This will also delete all associated notes."
        )

        if result:
            try:
                db.delete_customer(customer_id)
                self.customer_form.clear_form()
                self.notes_panel.clear_notes()
                self.customer_list.refresh()
                self._update_status(f"Customer deleted")
                messagebox.showinfo("Success", "Customer deleted successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete customer:\n{str(e)}")

    def _save_current(self):
        """Save the current customer (keyboard shortcut handler)."""
        if self.customer_form.account_var.get().strip():
            self.customer_form._on_save()

    def _focus_search(self):
        """Focus the search entry."""
        self.customer_list.search_entry.focus()
        self.customer_list.search_entry.select_range(0, "end")

    def _refresh(self):
        """Refresh the customer list."""
        self.customer_list.refresh()
        self._update_status("Refreshed")

    def _export_contacts(self):
        """Open the export contacts dialog."""
        try:
            from m2r_crm_export import ExportDialog
            dialog = ExportDialog(self.root)
            self.root.wait_window(dialog)
        except ImportError as e:
            messagebox.showerror("Error", f"Export module not available:\n{str(e)}")

    def _import_from_access(self):
        """Open the import from Access dialog."""
        try:
            from m2r_crm_import import ImportDialog
            dialog = ImportDialog(self.root, self._on_import_complete)
            self.root.wait_window(dialog)
        except ImportError as e:
            messagebox.showerror("Error", f"Import module not available:\n{str(e)}")

    def _on_import_complete(self):
        """Called when import is complete."""
        self.customer_list.refresh()
        self._update_status("Import complete - list refreshed")

    def _show_statistics(self):
        """Show database statistics."""
        total = db.get_customer_count("All")
        active = db.get_customer_count("Active")
        retired = db.get_customer_count("Retired")

        messagebox.showinfo(
            "Database Statistics",
            f"Total Customers: {total}\n"
            f"Active: {active}\n"
            f"Retired: {retired}\n\n"
            f"Database: {db.DB_PATH}"
        )

    def _show_about(self):
        """Show about dialog with M2R branding."""
        about_win = tk.Toplevel(self.root)
        about_win.title("About M2R CRM")
        about_win.geometry("350x280")
        about_win.resizable(False, False)
        about_win.transient(self.root)
        about_win.grab_set()

        # Center on parent
        about_win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 350) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 280) // 2
        about_win.geometry(f"+{x}+{y}")

        # Header with brand color
        header = tk.Frame(about_win, bg=self.PRIMARY_BLUE, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Logo in header
        logo_path = ASSET_DIR / "M2RLogo.png"
        if logo_path.exists() and PIL_AVAILABLE:
            try:
                pil_img = Image.open(str(logo_path))
                pil_img = pil_img.resize((55, 55), Image.LANCZOS)
                self._about_logo = ImageTk.PhotoImage(pil_img)
                tk.Label(header, image=self._about_logo, bg=self.PRIMARY_BLUE).pack(side="left", padx=15, pady=10)
            except:
                pass

        tk.Label(header, text="M2R CRM", bg=self.PRIMARY_BLUE, fg=self.WHITE,
                font=("Segoe UI", 18, "bold")).pack(side="left", padx=10, pady=10)

        # Content
        content = ttk.Frame(about_win, padding=20)
        content.pack(fill="both", expand=True)

        ttk.Label(content, text="Version 1.0", font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))
        ttk.Label(content, text="Customer Relationship Management\nfor M2 Reporter",
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))
        ttk.Label(content, text="Built with Python and Tkinter",
                 foreground="gray", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 15))

        ttk.Button(content, text="OK", command=about_win.destroy, width=10).pack()

    def _on_exit(self):
        """Handle application exit."""
        self.root.quit()


def main():
    """Main entry point."""
    root = tk.Tk()

    # Center window on screen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - 1200) // 2
    y = (screen_height - 800) // 2
    root.geometry(f"1200x800+{x}+{y}")

    app = M2RCrmApp(root)

    # Handle window close
    root.protocol("WM_DELETE_WINDOW", app._on_exit)

    root.mainloop()


if __name__ == "__main__":
    main()
