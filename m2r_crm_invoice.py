"""
M2R CRM Invoice Generator
=========================
Generates PDF support invoices formatted for #10 double-window envelopes.
Fold the printed page in thirds (bottom up, top down) and insert into a
standard #10 double-window envelope — both addresses show through the windows.
"""

import os
from datetime import datetime, date
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from tkcalendar import Calendar as _TkCalendar
    _CAL_AVAIL = True
except ImportError:
    _CAL_AVAIL = False

from m2r_crm_paths import ASSET_DIR, APP_DIR

# =============================================================================
# M2R Company Return Address — update these to match your actual mailing info
# =============================================================================
M2R_NAME  = "M2 Reporter"
M2R_ADDR1 = "PO Box 432"
M2R_ADDR2 = "Oakland, OR 97462"
M2R_PHONE = "(800)942-0470"
M2R_SITE  = "www.m2reporter.com"

# =============================================================================
# Fixed invoice text
# =============================================================================
ITEM_DESCRIPTION = "M2 Reporter Annual Renewal"

BODY_PARA1 = (
    "Our records indicate that your annual renewal is due. To continue your unlimited "
    "toll-free technical support and access to program updates for one year, please "
    "send your payment to M2 Reporter."
)

BODY_PARA1_PAST_DUE = (
    "Our records indicate that your annual renewal is past due. To continue your unlimited "
    "toll-free technical support and access to program updates for one year, please "
    "send your payment to M2 Reporter."
)

BODY_PARA2 = (
    "You can access the current version of M2R through your account at "
    "www.m2reporter.com  If you have not registered for this access please update "
    "your email below and we will send you a registration link."
)


# =============================================================================
# PDF generation
# =============================================================================

def generate_invoice_pdf(customer_data: dict, due_date_str: str, output_path: str,
                         past_due: bool = False) -> bool:
    """
    Render a PDF invoice to output_path.
    Pass past_due=True to use the past-due first paragraph.
    Raises ImportError if reportlab is not installed.
    Returns True on success.
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError(
            "Invoice generation requires the 'reportlab' package.\n"
            "Install it with:  pip install reportlab"
        )

    M2R_BLUE  = colors.HexColor('#144478')
    M2R_GREEN = colors.HexColor('#B3CC48')
    LIGHT_GREY = colors.HexColor('#F5F5F5')
    RULE_GREY  = colors.HexColor('#CCCCCC')

    PAGE_W, PAGE_H = letter   # 612 × 792 pts  (8.5" × 11")

    # ── Fold positions (from bottom; reportlab origin is bottom-left) ──────
    # Tri-fold: bottom third 0"–2.667", middle 2.667"–7.333", top 7.333"–11"
    # The bottom third is the visible "face" when folded into the envelope.
    FOLD_LOW  = 2.947 * inch   # divides bottom from middle thirds
    FOLD_HIGH = 7.333 * inch   # divides middle from top thirds

    # ── Invoice metadata ───────────────────────────────────────────────────
    account_no       = customer_data.get('account_number', '')
    today            = datetime.now()
    invoice_date_str = today.strftime('%m/%d/%Y')
    mmdd             = today.strftime('%m%d%y')         # e.g. "050426" for May 4, 2026
    invoice_no       = f"{account_no}-{mmdd}"

    # ── Customer info ──────────────────────────────────────────────────────
    company  = customer_data.get('company_name', '')
    contact  = customer_data.get('contact_name', '')
    street   = customer_data.get('address_street', '')
    city     = customer_data.get('address_city', '')
    state    = customer_data.get('address_state', '')
    zip_code = customer_data.get('address_zip', '')

    csz_parts = [p for p in [city, state] if p]
    csz = ', '.join(csz_parts)
    if zip_code:
        csz = f"{csz} {zip_code}".strip()

    # Ordered address lines for "Bill To" and window address blocks
    addr_lines = []
    if company:
        addr_lines.append(company)
    if contact:
        addr_lines.append(f"Attn: {contact}")
    if street:
        addr_lines.append(street)
    if csz:
        addr_lines.append(csz)

    # ── Amount ─────────────────────────────────────────────────────────────
    try:
        amt = float(customer_data.get('support_amount') or 0)
    except (ValueError, TypeError):
        amt = 0.0
    amount_str = f"${amt:,.2f}"

    # ── Canvas ─────────────────────────────────────────────────────────────
    c = rl_canvas.Canvas(str(output_path), pagesize=letter)

    # =========================================================================
    # LOGO  (top-left, 0.75" square)
    # =========================================================================
    LOGO_SIZE = 0.75 * inch
    LOGO_X    = 0.5 * inch
    LOGO_Y    = PAGE_H - 0.45 * inch - LOGO_SIZE   # bottom-left corner of logo

    logo_path = ASSET_DIR / "M2RLogo.png"
    if logo_path.exists():
        try:
            c.drawImage(
                str(logo_path), LOGO_X, LOGO_Y,
                width=LOGO_SIZE, height=LOGO_SIZE,
                preserveAspectRatio=True, mask='auto'
            )
        except Exception:
            pass

    # =========================================================================
    # M2R COMPANY INFO  (beside logo, same row)
    # Placing text to the right of the logo keeps the header compact so the
    # green rule sits clearly below all content.
    # =========================================================================
    INFO_X   = LOGO_X + LOGO_SIZE + 0.18 * inch
    INFO_TOP = PAGE_H - 0.52 * inch   # align near top of logo
    LH       = 0.175 * inch

    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(M2R_BLUE)
    c.drawString(INFO_X, INFO_TOP, M2R_NAME)

    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.black)
    for line in (M2R_ADDR1, M2R_ADDR2, M2R_PHONE, M2R_SITE):
        INFO_TOP -= LH
        c.drawString(INFO_X, INFO_TOP, line)

    # =========================================================================
    # "INVOICE"  (top-right, 22 pt)
    # =========================================================================
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(M2R_BLUE)
    c.drawRightString(PAGE_W - 0.5 * inch, PAGE_H - 0.62 * inch, "INVOICE")

    # =========================================================================
    # INVOICE DETAIL TABLE  (right column, below "INVOICE")
    # =========================================================================
    label_x  = PAGE_W - 2.9 * inch
    value_x  = PAGE_W - 0.5 * inch
    detail_y = PAGE_H - 0.98 * inch

    for label, value in [
        ("Invoice #:",    invoice_no),
        ("Invoice Date:", invoice_date_str),
        ("Due Date:",     due_date_str),
    ]:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(M2R_BLUE)
        c.drawString(label_x, detail_y, label)
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.black)
        c.drawRightString(value_x, detail_y, value)
        detail_y -= 0.21 * inch

    # =========================================================================
    # HORIZONTAL RULE
    # Rule sits 0.25" below the bottom of the left header block (logo bottom
    # is at LOGO_Y, company text ends ~3 lines below INFO_TOP).
    # Using a fixed 1.85" from top keeps it safely clear of all header text.
    # =========================================================================
    rule_y = PAGE_H - 1.85 * inch
    c.setStrokeColor(M2R_GREEN)
    c.setLineWidth(2.5)
    c.line(0.5 * inch, rule_y, PAGE_W - 0.5 * inch, rule_y)

    # =========================================================================
    # BILL TO
    # =========================================================================
    bt_y = rule_y - 0.26 * inch
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(M2R_BLUE)
    c.drawString(0.5 * inch, bt_y, "BILL TO:")

    addr_y = bt_y - 0.22 * inch
    for i, line in enumerate(addr_lines):
        c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 10 if i == 0 else 9)
        c.setFillColor(colors.black)
        c.drawString(0.5 * inch, addr_y, line)
        addr_y -= (0.2 * inch if i == 0 else 0.18 * inch)

    # =========================================================================
    # ITEM TABLE
    # =========================================================================
    TBL_TOP  = PAGE_H - 3.55 * inch
    TBL_L    = 0.5 * inch
    TBL_R    = PAGE_W - 0.5 * inch
    TBL_W    = TBL_R - TBL_L
    ROW_H    = 0.26 * inch

    # Header row
    c.setFillColor(M2R_BLUE)
    c.rect(TBL_L, TBL_TOP - ROW_H, TBL_W, ROW_H, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.white)
    c.drawString(TBL_L + 0.12 * inch, TBL_TOP - ROW_H + 0.08 * inch, "ITEM DESCRIPTION")
    c.drawRightString(TBL_R - 0.12 * inch, TBL_TOP - ROW_H + 0.08 * inch, "AMOUNT")

    # Item row
    item_y = TBL_TOP - 2 * ROW_H
    c.setFillColor(LIGHT_GREY)
    c.rect(TBL_L, item_y, TBL_W, ROW_H, fill=1, stroke=0)
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    c.drawString(TBL_L + 0.12 * inch, item_y + 0.08 * inch, ITEM_DESCRIPTION)
    c.drawRightString(TBL_R - 0.12 * inch, item_y + 0.08 * inch, amount_str)

    # Outer border
    c.setStrokeColor(RULE_GREY)
    c.setLineWidth(0.5)
    c.rect(TBL_L, item_y, TBL_W, 2 * ROW_H, fill=0, stroke=1)

    # =========================================================================
    # BODY PARAGRAPHS
    # =========================================================================
    body_style = ParagraphStyle(
        'InvBody',
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.black,
    )

    para_x   = 0.5 * inch
    para_w   = PAGE_W - 1.0 * inch
    para_top = item_y - 0.32 * inch

    first_para = BODY_PARA1_PAST_DUE if past_due else BODY_PARA1
    for para_text in (first_para, BODY_PARA2):
        p = Paragraph(para_text, body_style)
        _, p_h = p.wrap(para_w, 300)
        para_top -= p_h
        p.drawOn(c, para_x, para_top)
        para_top -= 0.16 * inch

    # =========================================================================
    # EMAIL UPDATE FIELD
    # =========================================================================
    email_top = para_top - 0.18 * inch

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    c.drawString(para_x, email_top, "Email:")

    line_x1 = para_x + 0.55 * inch
    line_x2 = para_x + 3.5 * inch
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.75)
    c.line(line_x1, email_top - 0.02 * inch, line_x2, email_top - 0.02 * inch)

    # Total row
    total_y = email_top - ROW_H - 0.2 * inch
    c.setFillColor(M2R_GREEN)
    c.rect(TBL_L, total_y, TBL_W, ROW_H, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(M2R_BLUE)
    c.drawString(TBL_L + 0.12 * inch, total_y + 0.08 * inch, "TOTAL DUE")
    c.drawRightString(TBL_R - 0.12 * inch, total_y + 0.08 * inch, amount_str)

    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.black)
    c.drawRightString(TBL_R - 0.12 * inch, total_y - 0.16 * inch, "Make check payable to M2 Reporter")

    # =========================================================================
    # FOLD LINE  (between middle and bottom thirds)
    # =========================================================================
    c.setStrokeColor(RULE_GREY)
    c.setDash(4, 4)
    c.setLineWidth(0.5)
    c.line(0.3 * inch, FOLD_LOW, PAGE_W - 0.3 * inch, FOLD_LOW)
    c.setDash()

    c.setFont("Helvetica", 6)
    c.setFillColor(colors.HexColor('#BBBBBB'))
    c.drawString(0.3 * inch, FOLD_LOW + 0.04 * inch, "FOLD ▼")

    # =========================================================================
    # BOTTOM THIRD — ADDRESS WINDOW AREA
    #
    # Designed for a standard #10 double-window envelope.
    # Fold the letter bottom-up first, then top-down; the bottom third becomes
    # the visible face.  Both windows are on the left side of the envelope:
    #   • Upper window (return address): ~0.45" below the fold line
    #   • Lower window (recipient):      ~1.45" below the fold line
    # =========================================================================

    # ── Return address (upper window) ──
    RET_X = 0.5 * inch
    ret_y = FOLD_LOW - 0.34 * inch    # top of the text block (pinned; offset compensates for fold line position)

    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(colors.black)
    c.drawString(RET_X, ret_y, M2R_NAME)

    c.setFont("Helvetica", 8)
    for line in (M2R_ADDR1, M2R_ADDR2):
        ret_y -= 0.14 * inch
        c.drawString(RET_X, ret_y, line)

    # ── Customer address (lower window) ──
    CUST_X = 0.5 * inch
    cust_y = 1.017 * inch              # absolute position — independent of fold line

    for i, line in enumerate(addr_lines):
        c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 10 if i == 0 else 9)
        c.setFillColor(colors.black)
        c.drawString(CUST_X, cust_y, line)
        cust_y -= (0.2 * inch if i == 0 else 0.17 * inch)

    c.save()
    return True


# =============================================================================
# Bulk Invoice Dialog  (Tools menu → Generate Invoices)
# =============================================================================

class BulkInvoiceDialog(tk.Toplevel):
    """
    Generates PDF invoices for every active customer with Support Invoice or
    Past Due Invoice checked.  All invoices share the same due date and are
    saved to a user-chosen folder.
    """

    PRIMARY_BLUE = "#144478"
    WHITE        = "#FFFFFF"
    ACCENT_GREEN = "#B3CC48"

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Generate Invoices")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        import m2r_crm_database as db
        self._support_customers  = db.get_support_invoice_customers()
        self._past_due_customers = db.get_past_due_invoice_customers()

        self._build()

        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h   = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build(self):
        # Header bar
        hdr = tk.Frame(self, bg=self.PRIMARY_BLUE, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Generate Invoices",
                 bg=self.PRIMARY_BLUE, fg=self.WHITE,
                 font=("Segoe UI", 12, "bold")).pack(side="left", padx=12, pady=8)

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        n_sup = len(self._support_customers)
        n_pd  = len(self._past_due_customers)
        total = n_sup + n_pd

        all_customers = self._support_customers + self._past_due_customers
        no_amt = sum(1 for c in all_customers
                     if not c.get('support_amount') or float(c.get('support_amount') or 0) <= 0)

        # Summary
        next_row = 0
        ttk.Label(body,
                  text=f"Support Invoice:   {n_sup} customer{'s' if n_sup != 1 else ''}",
                  font=("Segoe UI", 9)).grid(
            row=next_row, column=0, columnspan=3, sticky="w", pady=(0, 2))
        next_row += 1
        ttk.Label(body,
                  text=f"Past Due Invoice:  {n_pd} customer{'s' if n_pd != 1 else ''}",
                  font=("Segoe UI", 9)).grid(
            row=next_row, column=0, columnspan=3, sticky="w", pady=(0, 4))
        next_row += 1
        ttk.Label(body,
                  text=f"Total to generate: {total}",
                  font=("Segoe UI", 10, "bold")).grid(
            row=next_row, column=0, columnspan=3, sticky="w", pady=(0, 4))
        next_row += 1

        if no_amt:
            ttk.Label(body,
                      text=f"  ⚠  {no_amt} have no Support Amount set (will show $0.00).",
                      foreground="#CC6600", font=("Segoe UI", 9)).grid(
                row=next_row, column=0, columnspan=3, sticky="w", pady=(0, 6))
            next_row += 1

        ttk.Separator(body, orient="horizontal").grid(
            row=next_row, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        next_row += 1

        # Due date
        ttk.Label(body, text="Due Date:",
                  font=("Segoe UI", 9, "bold")).grid(
            row=next_row, column=0, sticky="e", padx=(0, 8), pady=4)

        due_frame = ttk.Frame(body)
        due_frame.grid(row=next_row, column=1, columnspan=2, sticky="w", pady=4)

        if _CAL_AVAIL:
            self._due_popup = None
            self._due_var   = tk.StringVar()
            self._due_entry = ttk.Entry(due_frame, textvariable=self._due_var, width=14)
            self._due_entry.pack(side="left")
            ttk.Button(due_frame, text="▼", width=2,
                       command=self._toggle_cal).pack(side="left")
        else:
            self._due_var   = tk.StringVar()
            self._due_entry = ttk.Entry(due_frame, textvariable=self._due_var, width=14)
            self._due_entry.pack(side="left")
            ttk.Label(due_frame, text="MM/DD/YYYY", foreground="gray",
                      font=("Segoe UI", 8)).pack(side="left", padx=(6, 0))
        next_row += 1

        # Output folder
        ttk.Label(body, text="Save to Folder:",
                  font=("Segoe UI", 9, "bold")).grid(
            row=next_row, column=0, sticky="e", padx=(0, 8), pady=4)

        self._folder_var = tk.StringVar()
        ttk.Entry(body, textvariable=self._folder_var, width=36).grid(
            row=next_row, column=1, sticky="w", pady=4)
        ttk.Button(body, text="Browse…",
                   command=self._browse_folder).grid(
            row=next_row, column=2, sticky="w", padx=(4, 0), pady=4)
        next_row += 1

        ttk.Separator(body, orient="horizontal").grid(
            row=next_row, column=0, columnspan=3, sticky="ew", pady=(8, 10))
        next_row += 1

        # Generate button
        btn_row = next_row
        btn_label = f"Generate {total} Invoice{'s' if total != 1 else ''}"
        self._gen_btn = ttk.Button(body, text=btn_label,
                                   command=self._generate,
                                   style="Accent.TButton", width=24)
        self._gen_btn.grid(row=btn_row, column=0, columnspan=2,
                           sticky="w", pady=(0, 6))
        ttk.Button(body, text="Close",
                   command=self.destroy, width=10).grid(
            row=btn_row, column=2, sticky="e", pady=(0, 6))
        next_row += 1

        # Results log (shown after generation)
        self._log = tk.Text(body, width=52, height=8, state="disabled",
                            font=("Consolas", 8), wrap="none")
        self._log_sb = ttk.Scrollbar(body, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=self._log_sb.set)
        # Not gridded yet — shown after generation starts
        self._log_row = next_row
        self._body    = body
        self._total   = total

        if total == 0:
            self._gen_btn.config(state="disabled")

    # ── Calendar popup ────────────────────────────────────────────────────────

    def _toggle_cal(self):
        if self._due_popup and self._due_popup.winfo_exists():
            self._close_cal()
        else:
            self._open_cal()

    def _open_cal(self):
        self._due_popup = tk.Toplevel(self)
        self._due_popup.wm_overrideredirect(True)
        self._due_popup.lift()
        cur = self._parse_due()
        kw  = dict(year=cur.year, month=cur.month, day=cur.day) if cur else {}
        cal = _TkCalendar(self._due_popup, selectmode='day', **kw)
        cal.pack(padx=4, pady=4)
        if cur:
            cal.selection_set(cur)
        cal.bind('<<CalendarSelected>>', lambda e: self._pick(cal))
        self._due_popup.bind('<Escape>', lambda e: self._close_cal())
        self._due_popup.update_idletasks()
        pw = self._due_popup.winfo_reqwidth()
        ph = self._due_popup.winfo_reqheight()
        wx = self._due_entry.winfo_rootx()
        wy = self._due_entry.winfo_rooty() + self._due_entry.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = max(0, min(wx, sw - pw - 4))
        y  = wy if wy + ph <= sh else (self._due_entry.winfo_rooty() - ph - 2)
        self._due_popup.geometry(f'+{x}+{max(0, y)}')
        cal.focus_set()

    def _close_cal(self):
        if self._due_popup and self._due_popup.winfo_exists():
            self._due_popup.destroy()
        self._due_popup = None

    def _pick(self, cal):
        try:
            self._due_var.set(cal.selection_get().strftime('%m/%d/%Y'))
        except Exception:
            pass
        self._close_cal()

    def _parse_due(self):
        val = self._due_var.get().strip()
        for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d'):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                pass
        return None

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select Output Folder", parent=self)
        if folder:
            self._folder_var.set(folder)

    # ── Generation ────────────────────────────────────────────────────────────

    def _log_line(self, text: str):
        self._log.config(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.config(state="disabled")
        self.update_idletasks()

    def _generate(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror(
                "Missing Package",
                "Invoice generation requires 'reportlab'.\n"
                "Install it with:  pip install reportlab",
                parent=self
            )
            return

        due_date_obj = self._parse_due()
        if not due_date_obj:
            messagebox.showwarning("Due Date Required",
                                   "Please enter a Due Date before generating.",
                                   parent=self)
            self._due_entry.focus()
            return

        folder = self._folder_var.get().strip()
        if not folder:
            messagebox.showwarning("Folder Required",
                                   "Please choose a folder to save the invoices.",
                                   parent=self)
            return

        folder_path = Path(folder)
        if not folder_path.exists():
            messagebox.showwarning("Folder Not Found",
                                   f"The folder does not exist:\n{folder}",
                                   parent=self)
            return

        due_str  = due_date_obj.strftime('%m/%d/%Y')
        mmdd     = datetime.now().strftime('%m%d%y')
        today_iso = datetime.now().date().isoformat()
        today_fmt = datetime.now().strftime('%m/%d/%Y')

        # Show the log area
        self._log.grid(row=self._log_row, column=0, columnspan=2,
                       sticky="ew", pady=(8, 0))
        self._log_sb.grid(row=self._log_row, column=2,
                          sticky="ns", pady=(8, 0))
        self._gen_btn.config(state="disabled")

        import m2r_crm_database as db

        generated = 0
        errors    = 0

        self._log_line(f"Generating {self._total} invoice(s)…")
        self._log_line(f"Due date: {due_str}   Folder: {folder}")
        self._log_line("─" * 52)

        # Process each group; past_due flag selects the correct paragraph and date field
        groups = [
            (self._support_customers,  False, 'last_invoice_date',    'support_invoice',  "Annual renewal invoice generated"),
            (self._past_due_customers, True,  'last_invoice_past_due', 'past_due_invoice', "Past due renewal invoice generated"),
        ]

        for customers, is_past_due, date_field, inv_flag, note_prefix in groups:
            for customer in customers:
                acct     = customer.get('account_number', 'unknown')
                company  = customer.get('company_name', acct)
                prefix   = "PD_" if is_past_due else ""
                filename = f"Invoice_{prefix}{acct}-{mmdd}.pdf"
                out_path = folder_path / filename

                try:
                    generate_invoice_pdf(customer, due_str, str(out_path),
                                         past_due=is_past_due)
                    db.update_customer(customer['id'], {
                        date_field: today_iso,
                        inv_flag:   0,
                    })
                    db.create_note(customer['id'],
                                   f"{note_prefix} ({today_fmt}).")
                    self._log_line(f"  ✓  {company}  →  {filename}")
                    generated += 1
                except Exception as exc:
                    self._log_line(f"  ✗  {company}  —  ERROR: {exc}")
                    errors += 1

        self._log_line("─" * 52)
        self._log_line(
            f"Done.  {generated} generated"
            + (f",  {errors} failed." if errors else ".")
        )

        if generated:
            if messagebox.askyesno("Open Folder?",
                                   f"{generated} invoice(s) saved.\nOpen the output folder?",
                                   parent=self):
                try:
                    os.startfile(str(folder_path))
                except Exception:
                    pass


# =============================================================================
# Invoice Dialog  (single customer — kept for reference / future use)
# =============================================================================

class InvoiceDialog(tk.Toplevel):
    """
    Dialog that lets the user choose a due date then generates the PDF invoice.
    After closing, check `self.invoice_generated` to see if a PDF was saved.
    """

    PRIMARY_BLUE = "#144478"
    WHITE        = "#FFFFFF"
    ACCENT_GREEN = "#B3CC48"

    def __init__(self, parent, customer_data: dict):
        super().__init__(parent)
        self.customer_data   = customer_data
        self.invoice_generated = False   # set True when PDF is saved

        self.title("Generate Support Invoice")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build()

        # Center on parent
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h   = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        # Header bar
        hdr = tk.Frame(self, bg=self.PRIMARY_BLUE, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Generate Support Invoice",
                 bg=self.PRIMARY_BLUE, fg=self.WHITE,
                 font=("Segoe UI", 12, "bold")).pack(side="left", padx=12, pady=8)

        # Body
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        # Customer summary
        acct    = self.customer_data.get('account_number', '')
        company = self.customer_data.get('company_name', '') or '—'
        today   = datetime.now()
        mmdd    = today.strftime('%m%d%y')
        inv_no  = f"{acct}-{mmdd}"
        inv_dt  = today.strftime('%m/%d/%Y')

        try:
            amt = float(self.customer_data.get('support_amount') or 0)
        except (ValueError, TypeError):
            amt = 0.0

        ttk.Label(body, text="Customer:", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=3)
        ttk.Label(body, text=company).grid(row=0, column=1, sticky="w", pady=3)

        ttk.Label(body, text="Invoice #:", font=("Segoe UI", 9, "bold")).grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=3)
        ttk.Label(body, text=inv_no).grid(row=1, column=1, sticky="w", pady=3)

        ttk.Label(body, text="Invoice Date:", font=("Segoe UI", 9, "bold")).grid(
            row=2, column=0, sticky="e", padx=(0, 8), pady=3)
        ttk.Label(body, text=inv_dt).grid(row=2, column=1, sticky="w", pady=3)

        ttk.Label(body, text="Amount Due:", font=("Segoe UI", 9, "bold")).grid(
            row=3, column=0, sticky="e", padx=(0, 8), pady=3)
        ttk.Label(body, text=f"${amt:,.2f}",
                  foreground="#144478", font=("Segoe UI", 10, "bold")).grid(
            row=3, column=1, sticky="w", pady=3)

        ttk.Separator(body, orient="horizontal").grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Label(body, text="Due Date:", font=("Segoe UI", 9, "bold")).grid(
            row=5, column=0, sticky="e", padx=(0, 8), pady=3)

        due_frame = ttk.Frame(body)
        due_frame.grid(row=5, column=1, sticky="w", pady=3)

        if _CAL_AVAIL:
            self._due_popup = None
            self._due_var   = tk.StringVar()
            self._due_entry = ttk.Entry(due_frame, textvariable=self._due_var, width=14)
            self._due_entry.pack(side="left")
            ttk.Button(due_frame, text="▼", width=2,
                       command=self._toggle_cal).pack(side="left")
        else:
            self._due_var   = tk.StringVar()
            self._due_entry = ttk.Entry(due_frame, textvariable=self._due_var, width=14)
            self._due_entry.pack(side="left")
            ttk.Label(due_frame, text="(MM/DD/YYYY)", foreground="gray",
                      font=("Segoe UI", 8)).pack(side="left", padx=(6, 0))

        # Buttons
        btn_frame = ttk.Frame(body)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(16, 0))

        ttk.Button(btn_frame, text="Generate Invoice",
                   command=self._generate, style="Accent.TButton",
                   width=18).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Cancel",
                   command=self.destroy, width=10).pack(side="left")

        # Validation note
        if not REPORTLAB_AVAILABLE:
            ttk.Label(body, text="⚠  reportlab not installed — pip install reportlab",
                      foreground="red", font=("Segoe UI", 8)).grid(
                row=7, column=0, columnspan=2, pady=(8, 0))

    # ── Calendar popup ────────────────────────────────────────────────────────

    def _toggle_cal(self):
        if self._due_popup and self._due_popup.winfo_exists():
            self._close_cal()
        else:
            self._open_cal()

    def _open_cal(self):
        self._due_popup = tk.Toplevel(self)
        self._due_popup.wm_overrideredirect(True)
        self._due_popup.lift()

        cur = self._parse_due()
        kw  = dict(year=cur.year, month=cur.month, day=cur.day) if cur else {}
        cal = _TkCalendar(self._due_popup, selectmode='day', **kw)
        cal.pack(padx=4, pady=4)
        if cur:
            cal.selection_set(cur)
        cal.bind('<<CalendarSelected>>', lambda e: self._pick(cal))
        self._due_popup.bind('<Escape>', lambda e: self._close_cal())

        self._due_popup.update_idletasks()
        pw = self._due_popup.winfo_reqwidth()
        ph = self._due_popup.winfo_reqheight()
        wx = self._due_entry.winfo_rootx()
        wy = self._due_entry.winfo_rooty() + self._due_entry.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = max(0, min(wx, sw - pw - 4))
        y  = wy if wy + ph <= sh else (self._due_entry.winfo_rooty() - ph - 2)
        self._due_popup.geometry(f'+{x}+{max(0, y)}')
        cal.focus_set()

    def _close_cal(self):
        if self._due_popup and self._due_popup.winfo_exists():
            self._due_popup.destroy()
        self._due_popup = None

    def _pick(self, cal):
        try:
            d = cal.selection_get()
            self._due_var.set(d.strftime('%m/%d/%Y'))
        except Exception:
            pass
        self._close_cal()

    def _parse_due(self):
        val = self._due_var.get().strip()
        for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d'):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                pass
        return None

    # ── Generate ──────────────────────────────────────────────────────────────

    def _generate(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror(
                "Missing Package",
                "Invoice generation requires 'reportlab'.\n"
                "Install it with:  pip install reportlab",
                parent=self
            )
            return

        # Validate amount
        try:
            amt = float(self.customer_data.get('support_amount') or 0)
        except (ValueError, TypeError):
            amt = 0.0
        if amt <= 0:
            messagebox.showwarning(
                "No Amount",
                "Support Amount is not set for this customer.\n"
                "Please enter a Support Amount before generating an invoice.",
                parent=self
            )
            return

        # Validate due date
        due_date_obj = self._parse_due()
        if not due_date_obj:
            messagebox.showwarning(
                "Due Date Required",
                "Please enter a Due Date (MM/DD/YYYY) before generating.",
                parent=self
            )
            self._due_entry.focus()
            return

        due_date_str = due_date_obj.strftime('%m/%d/%Y')

        # Build default filename
        acct    = self.customer_data.get('account_number', 'invoice')
        mmdd    = datetime.now().strftime('%m%d%y')
        default = f"Invoice_{acct}-{mmdd}.pdf"

        out_path = filedialog.asksaveasfilename(
            title="Save Invoice PDF",
            defaultextension=".pdf",
            filetypes=[("PDF Document", "*.pdf")],
            initialfile=default,
            parent=self,
        )
        if not out_path:
            return

        try:
            generate_invoice_pdf(self.customer_data, due_date_str, out_path)
        except Exception as exc:
            messagebox.showerror("Invoice Error", str(exc), parent=self)
            return

        self.invoice_generated = True
        messagebox.showinfo(
            "Invoice Saved",
            f"Invoice saved to:\n{out_path}",
            parent=self
        )

        if messagebox.askyesno("Open Invoice?", "Open the invoice now?", parent=self):
            try:
                os.startfile(out_path)
            except Exception:
                pass

        self.destroy()
