import csv
import io
import os
import re
import sys
import time
import urllib.parse
import threading
import requests
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Try importing Selenium for reliable browser rendering & CAPTCHA bypass
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


# Regex patterns for contact information extraction
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
PHONE_PATTERN = re.compile(r'(?:(?:\+44\s?\(0\)\s?\d{2,4}|\+44\s?\d{2,4}|0\d{2,4})\s?\d{3,4}\s?\d{3,4}|\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9})')

# History log file path & Auth Profile path
HISTORY_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "search_history.log")
AUTH_PROFILE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "GoogleScraperAuthProfile")


def sanitize_search_query(query: str) -> str:
    """Cleans up formatting mistakes (protocols in site:, spaces after operators, bare operators)."""
    if not query:
        return ""
    q = query.strip()
    
    # 1. Remove http:// or https:// from site: operators (e.g. site:https://linkedin.com -> site:linkedin.com)
    q = re.sub(r'site:\s*https?://', 'site:', q, flags=re.IGNORECASE)
    
    # 2. Fix spaces between operators and their values (e.g. site: linkedin.com -> site:linkedin.com)
    q = re.sub(r'\bsite:\s+', 'site:', q, flags=re.IGNORECASE)
    q = re.sub(r'\bintext:\s+', 'intext:', q, flags=re.IGNORECASE)
    q = re.sub(r'\bintitle:\s+', 'intitle:', q, flags=re.IGNORECASE)
    q = re.sub(r'\binurl:\s+', 'inurl:', q, flags=re.IGNORECASE)
    q = re.sub(r'\bfiletype:\s+', 'filetype:', q, flags=re.IGNORECASE)
    
    # 3. Remove bare/dangling operators with no value (e.g. trailing "site:" or "site: ")
    q = re.sub(r'\bsite:(?=\s|$)', '', q, flags=re.IGNORECASE)
    q = re.sub(r'\bintext:(?=\s|$)', '', q, flags=re.IGNORECASE)
    q = re.sub(r'\bintitle:(?=\s|$)', '', q, flags=re.IGNORECASE)
    q = re.sub(r'\binurl:(?=\s|$)', '', q, flags=re.IGNORECASE)
    q = re.sub(r'\bfiletype:(?=\s|$)', '', q, flags=re.IGNORECASE)
    
    # 4. Collapse extra whitespace
    q = re.sub(r'\s+', ' ', q).strip()
    return q


class ToolTip:
    """Hover tooltip helper for Tkinter widgets."""
    def __init__(self, widget, text, delay=250):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip_window = None
        self.schedule_id = None
        
        self.widget.bind("<Enter>", self._on_enter)
        self.widget.bind("<Leave>", self._on_leave)
        self.widget.bind("<ButtonPress>", self._on_leave)

    def _on_enter(self, event=None):
        self._cancel_schedule()
        self.schedule_id = self.widget.after(self.delay, self._show_tip)

    def _on_leave(self, event=None):
        self._cancel_schedule()
        self._hide_tip()

    def _cancel_schedule(self):
        if self.schedule_id:
            self.widget.after_cancel(self.schedule_id)
            self.schedule_id = None

    def _show_tip(self):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 15
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        
        frame = tk.Frame(tw, background="#0F172A", borderwidth=1, relief=tk.SOLID)
        frame.pack()
        
        label = tk.Label(
            frame,
            text=self.text,
            justify=tk.LEFT,
            background="#0F172A",
            foreground="#F8FAFC",
            font=("Segoe UI", 8),
            padx=8,
            pady=5,
            wraplength=380
        )
        label.pack()

    def _hide_tip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()


class GoogleLeadScraperSuite(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Multi-Engine Lead & Advanced Dork Extractor Suite")
        self.geometry("1160x920")
        self.minsize(980, 740)
        
        # Application State
        self.is_running = False
        self.stop_requested = False
        self.results_data = []  # list of lead dicts
        self.driver = None
        self._updating_query = False
        self.search_history = self._load_search_history()
        
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        self._setup_styles()
        self._build_ui()
        self._reset_builder()  # Start with completely clean/empty textboxes (no hardcoded defaults)
        
    def _setup_styles(self):
        self.configure(bg="#F1F5F9")
        self.style = ttk.Style(self)
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")
            
        # Base colors
        self.style.configure("TFrame", background="#F1F5F9")
        self.style.configure("TLabelframe", background="#F1F5F9")
        self.style.configure("TLabelframe.Label", background="#F1F5F9", foreground="#0F172A", font=("Segoe UI", 10, "bold"))
        self.style.configure("TLabel", background="#F1F5F9", foreground="#334155", font=("Segoe UI", 9))
        self.style.configure("TCheckbutton", background="#F1F5F9", foreground="#1E293B", font=("Segoe UI", 9))
        self.style.configure("TRadiobutton", background="#F1F5F9", foreground="#1E293B", font=("Segoe UI", 9))
        self.style.configure("TCombobox", font=("Segoe UI", 9))
        
        # Notebook (Tabs)
        self.style.configure("TNotebook", background="#E2E8F0", borderwidth=0)
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 9, "bold"), padding=[14, 7], background="#CBD5E1", foreground="#475569")
        self.style.map("TNotebook.Tab", 
                       background=[("selected", "#FFFFFF"), ("active", "#E2E8F0")], 
                       foreground=[("selected", "#2563EB"), ("active", "#0F172A")])
        
        # Headers
        self.style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"), foreground="#0F172A", background="#F1F5F9")
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 9), foreground="#64748B", background="#F1F5F9")
        self.style.configure("Section.TLabel", font=("Segoe UI", 9, "bold"), foreground="#1E293B", background="#F1F5F9")
        self.style.configure("Badge.TLabel", font=("Segoe UI", 9, "bold"), foreground="#2563EB", background="#EFF6FF", padding=4)
        
        # Buttons
        self.style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), background="#2563EB", foreground="white", borderwidth=0, padding=6)
        self.style.map("Primary.TButton", background=[("active", "#1D4ED8"), ("disabled", "#94A3B8")])
        
        self.style.configure("Success.TButton", font=("Segoe UI", 9, "bold"), background="#10B981", foreground="white", borderwidth=0, padding=6)
        self.style.map("Success.TButton", background=[("active", "#059669"), ("disabled", "#94A3B8")])
        
        self.style.configure("Danger.TButton", font=("Segoe UI", 9, "bold"), background="#EF4444", foreground="white", borderwidth=0, padding=6)
        self.style.map("Danger.TButton", background=[("active", "#DC2626"), ("disabled", "#94A3B8")])
        
        self.style.configure("Secondary.TButton", font=("Segoe UI", 9), background="#E2E8F0", foreground="#1E293B", borderwidth=0, padding=5)
        self.style.map("Secondary.TButton", background=[("active", "#CBD5E1")])
        
        self.style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"), background="#8B5CF6", foreground="white", borderwidth=0, padding=5)
        self.style.map("Accent.TButton", background=[("active", "#7C3AED")])

        self.style.configure("Operator.TButton", font=("Consolas", 8, "bold"), background="#E0E7FF", foreground="#3730A3", borderwidth=0, padding=3)
        self.style.map("Operator.TButton", background=[("active", "#C7D2FE")])

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- Top Banner ---
        top_banner = ttk.Frame(main_frame)
        top_banner.pack(fill=tk.X, pady=(0, 8))
        
        banner_left = ttk.Frame(top_banner)
        banner_left.pack(side=tk.LEFT)
        
        title_lbl = ttk.Label(banner_left, text="⚡ Multi-Engine Lead & Advanced Dork Suite", style="Header.TLabel")
        title_lbl.pack(anchor=tk.W)
        sub_lbl = ttk.Label(banner_left, text="Search Google, Bing, DuckDuckGo, Brave, Yahoo, Tor/Onion with precision Dorks, extract contacts, and export with 1 click.", style="SubHeader.TLabel")
        sub_lbl.pack(anchor=tk.W)
        
        # --- Main Notebook (Tabs) ---
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        # Tab 1: Interactive Query Builder
        self.tab_builder = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.tab_builder, text=" 🛠️ Query Builder & Presets ")
        self._build_tab_builder()
        
        # Tab 2: Results & Extractor Output
        self.tab_results = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.tab_results, text=" 📋 Extracted Results & Text Box ")
        self._build_tab_results()
        
        # Tab 3: Search Operators Cheat Sheet
        self.tab_cheatsheet = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.tab_cheatsheet, text=" 📖 Search Operators Cheat Sheet ")
        self._build_tab_cheatsheet()
        
        # Tab 4: Search Query History Log
        self.tab_history = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.tab_history, text=" 📜 Query History Log ")
        self._build_tab_history()
        
        # --- Bottom Status Bar ---
        status_bar = ttk.Frame(main_frame)
        status_bar.pack(fill=tk.X)
        
        self.status_var = tk.StringVar(value="Ready. Enter search criteria or apply a template to get started.")
        status_lbl = ttk.Label(status_bar, textvariable=self.status_var, font=("Segoe UI", 9, "italic"), foreground="#475569")
        status_lbl.pack(side=tk.LEFT)
        
        self.stat_leads_var = tk.StringVar(value="0 leads | 0 emails")
        stat_lbl = ttk.Label(status_bar, textvariable=self.stat_leads_var, font=("Segoe UI", 9, "bold"), foreground="#2563EB")
        stat_lbl.pack(side=tk.RIGHT)

    def _create_help_label(self, parent, text, help_text, width=19):
        """Creates a section label accompanied by a clickable/hoverable (?) help badge."""
        f = ttk.Frame(parent)
        lbl = ttk.Label(f, text=text, width=width, anchor=tk.W, style="Section.TLabel")
        lbl.pack(side=tk.LEFT)
        ToolTip(lbl, help_text)
        
        badge = tk.Label(f, text="?", font=("Segoe UI", 8, "bold"), fg="#2563EB", bg="#EFF6FF", relief=tk.SOLID, borderwidth=1, padx=3, pady=0, cursor="hand2")
        badge.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(badge, help_text)
        return f

    # -------------------------------------------------------------
    # TAB 1: QUERY BUILDER
    # -------------------------------------------------------------
    def _build_tab_builder(self):
        # 1. Search Engine & History Row
        engine_preset_frame = ttk.LabelFrame(self.tab_builder, text=" 🌐 Search Engine & Template Selector ", padding="8")
        engine_preset_frame.pack(fill=tk.X, pady=(0, 8))
        
        # Row A: Search Engine & Tor Proxy
        r_eng = ttk.Frame(engine_preset_frame)
        r_eng.pack(fill=tk.X, pady=(0, 4))
        
        hl_eng = self._create_help_label(r_eng, "Search Engine:", "Select which search engine to query. Each engine supports different operators and anti-bot defenses.")
        hl_eng.pack(side=tk.LEFT)
        
        self.engine_var = tk.StringVar(value="Google")
        engines = [
            ("🌐 Google", "Google"),
            ("🟦 Bing", "Bing"),
            ("🦆 DuckDuckGo", "DuckDuckGo"),
            ("🦁 Brave Search", "Brave"),
            ("🟣 Yahoo Search", "Yahoo"),
            ("🧅 Ahmia (Tor / Onion Web)", "Ahmia"),
            ("🔴 Yandex", "Yandex")
        ]
        
        self.engine_combo = ttk.Combobox(r_eng, values=[e[0] for e in engines], state="readonly", width=26)
        self.engine_combo.current(0)
        self.engine_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.engine_combo.bind("<<ComboboxSelected>>", self._on_engine_selected)
        
        self.google_auth_btn = ttk.Button(r_eng, text="🔑 Log in to Google", style="Accent.TButton", command=self._open_google_login)
        self.google_auth_btn.pack(side=tk.LEFT, padx=(0, 12))
        self._refresh_google_auth_ui()
        
        self.tor_proxy_var = tk.BooleanVar(value=False)
        chk_tor = ttk.Checkbutton(r_eng, text="🧅 Route through Tor Proxy (SOCKS5 127.0.0.1:9150/9050)", variable=self.tor_proxy_var)
        chk_tor.pack(side=tk.LEFT, padx=(5, 0))
        ToolTip(chk_tor, "Enables SOCKS5 proxy routing via Tor Browser/service for 100% anonymous scraping.")
        
        # Row B: Preset Template + History Recall
        r_pre = ttk.Frame(engine_preset_frame)
        r_pre.pack(fill=tk.X, pady=(4, 0))
        
        hl_pre = self._create_help_label(r_pre, "Load Template:", "Optional pre-configured industry search templates with ready-made dork keywords.")
        hl_pre.pack(side=tk.LEFT)
        
        self.preset_var = tk.StringVar(value="custom")
        presets = [
            ("-- Clean / Blank Form --", "custom"),
            ("Fire & Rescue IT Leaders (UK)", "fire_it"),
            ("NHS & Healthcare IT Heads", "nhs_it"),
            ("Local Council & Gov IT Directors", "gov_it"),
            ("Tech Startup Founders / CTOs", "tech_founders"),
            ("Procurement & Supply Chain Heads", "procurement"),
            ("Public Email Hunter (@gmail/@outlook)", "email_hunter"),
            ("Developer Code Solutions (StackOverflow/GitHub)", "dev_code"),
            ("Recent Tech Tutorials (after:2023)", "recent_tutorials"),
            ("Official Documentation (MDN/Microsoft)", "official_docs"),
            ("Open Directory Search (Index of /)", "index_of"),
            ("Confidential Salary & Budgets", "confidential_docs"),
            ("Server Configs & Exposed FTP", "server_configs"),
            ("Price/Number Range ($100..$500)", "number_range"),
            ("PDF Resumes & CVs", "resumes")
        ]
        
        self.preset_combo = ttk.Combobox(r_pre, values=[p[0] for p in presets], state="readonly", width=34)
        self.preset_combo.current(0)
        self.preset_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)
        
        load_btn = ttk.Button(r_pre, text="Apply Template", style="Secondary.TButton", command=lambda: self._on_preset_selected(None))
        load_btn.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(load_btn, "Loads selected template parameters into the builder form below.")
        
        # History recall dropdown
        hist_lbl = ttk.Label(r_pre, text="📜 Recall Past Query:", style="Section.TLabel")
        hist_lbl.pack(side=tk.LEFT, padx=(5, 4))
        
        self.history_combo = ttk.Combobox(r_pre, state="readonly", width=30)
        self._refresh_history_combo()
        self.history_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.history_combo.bind("<<ComboboxSelected>>", self._on_history_combo_selected)
        ToolTip(self.history_combo, "Select any past logged search query to recall it directly into the builder.")

        # 2. Builder Form Panes
        form_frame = ttk.LabelFrame(self.tab_builder, text=" Search Criteria & Dork Parameters ", padding="8")
        form_frame.pack(fill=tk.X, pady=(0, 8))
        
        # Row 1: Target Platform / Site (MANUAL & PRESETS)
        r1 = ttk.Frame(form_frame)
        r1.pack(fill=tk.X, pady=2)
        
        hl_site = self._create_help_label(r1, "Target Site (site:):", "Restricts results to a specific website or domain. Type any domain manually or pick from presets.")
        hl_site.pack(side=tk.LEFT)
        
        self.site_preset_var = tk.StringVar(value="")
        self.site_combo = ttk.Combobox(r1, textvariable=self.site_preset_var, width=32)
        self.site_combo['values'] = (
            "site:linkedin.com/in/",
            "site:linkedin.com/company/",
            "site:github.com",
            "site:stackoverflow.com OR site:github.com",
            "site:twitter.com OR site:x.com",
            "site:gov.uk",
            "site:facebook.com",
            "site:*.gov",
            "site:*.edu",
            "(All Websites / Open Web)"
        )
        self.site_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.site_combo.bind("<KeyRelease>", lambda e: self._rebuild_query())
        self.site_combo.bind("<<ComboboxSelected>>", lambda e: self._rebuild_query())
        ToolTip(self.site_combo, "Type any custom domain (e.g. reddit.com, bbc.co.uk) or choose a preset.")
        
        btn_wrap_site = ttk.Button(r1, text="+ Wrap site:", style="Secondary.TButton", command=self._wrap_site_syntax)
        btn_wrap_site.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(btn_wrap_site, "Automatically prefixes your typed domain with 'site:' (e.g., example.com -> site:example.com).")
        
        btn_clear_site = ttk.Button(r1, text="Clear (Open Web)", style="Secondary.TButton", command=lambda: (self.site_preset_var.set(""), self._rebuild_query()))
        btn_clear_site.pack(side=tk.LEFT)
        ToolTip(btn_clear_site, "Clears site restriction so search spans all websites on the open web.")
        
        # Row 2: Industry / Organization / intext
        r2 = ttk.Frame(form_frame)
        r2.pack(fill=tk.X, pady=2)
        
        hl_org = self._create_help_label(r2, "Industry / Keyword:", "Keywords, company names, or sectors to search for. E.g. \"Fire and Rescue\" or \"NHS Trust\".")
        hl_org.pack(side=tk.LEFT)
        
        self.org_var = tk.StringVar(value="")
        org_entry = ttk.Entry(r2, textvariable=self.org_var, font=("Segoe UI", 9), width=50)
        org_entry.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)
        org_entry.bind("<KeyRelease>", lambda e: self._rebuild_query())
        ToolTip(org_entry, "Enter comma-separated or quoted phrases. Click '+ Quotes/OR' to auto-format.")
        
        btn_org_add = ttk.Button(r2, text="+ Quotes/OR", style="Secondary.TButton", command=lambda: self._format_as_or_group(self.org_var))
        btn_org_add.pack(side=tk.RIGHT)
        ToolTip(btn_org_add, "Converts comma-separated words into quoted OR group: (\"Word 1\" OR \"Word 2\").")
        
        # Row 3: Job Titles / Target Roles / intitle
        r3 = ttk.Frame(form_frame)
        r3.pack(fill=tk.X, pady=2)
        
        hl_titles = self._create_help_label(r3, "Job Titles / Roles:", "Job roles or positions to find. E.g. \"Head of IT\" OR \"CTO\" OR \"IT Director\".")
        hl_titles.pack(side=tk.LEFT)
        
        self.titles_var = tk.StringVar(value="")
        titles_entry = ttk.Entry(r3, textvariable=self.titles_var, font=("Segoe UI", 9), width=50)
        titles_entry.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)
        titles_entry.bind("<KeyRelease>", lambda e: self._rebuild_query())
        ToolTip(titles_entry, "Target job titles or role variations.")
        
        btn_title_add = ttk.Button(r3, text="+ Quotes/OR", style="Secondary.TButton", command=lambda: self._format_as_or_group(self.titles_var))
        btn_title_add.pack(side=tk.RIGHT)
        ToolTip(btn_title_add, "Converts comma-separated titles into quoted OR group.")
        
        # Row 4: Location / Country / City
        r4 = ttk.Frame(form_frame)
        r4.pack(fill=tk.X, pady=2)
        
        hl_loc = self._create_help_label(r4, "Location / Region:", "Geographic filter for the search (e.g. \"United Kingdom\", \"London\", \"United States\").")
        hl_loc.pack(side=tk.LEFT)
        
        self.location_var = tk.StringVar(value="")
        loc_combo = ttk.Combobox(r4, textvariable=self.location_var, width=30)
        loc_combo['values'] = (
            '"United Kingdom"',
            '"London" OR "Greater London"',
            '"Manchester" OR "Birmingham" OR "Leeds"',
            '"United States"',
            '"Canada"',
            '"Australia"',
            '"Europe"',
            '(Worldwide / No Location)'
        )
        loc_combo.pack(side=tk.LEFT, padx=(0, 10))
        loc_combo.bind("<KeyRelease>", lambda e: self._rebuild_query())
        loc_combo.bind("<<ComboboxSelected>>", lambda e: self._rebuild_query())
        ToolTip(loc_combo, "Select or type any custom city, county, country, or region.")
        
        # Row 5: Contact Extractor Dorks & Extra Filters
        r5 = ttk.Frame(form_frame)
        r5.pack(fill=tk.X, pady=2)
        
        hl_contact = self._create_help_label(r5, "Contact / Email Filters:", "Appends contact hunting dorks to find emails or phone numbers in search snippets.")
        hl_contact.pack(side=tk.LEFT)
        
        self.email_dork_var = tk.BooleanVar(value=False)
        chk_email = ttk.Checkbutton(r5, text="Public Emails (@gmail, @outlook)", variable=self.email_dork_var, command=self._rebuild_query)
        chk_email.pack(side=tk.LEFT, padx=(0, 12))
        ToolTip(chk_email, "Appends (@gmail.com OR @outlook.com OR @yahoo.com) to find leads with public emails.")
        
        self.phone_dork_var = tk.BooleanVar(value=False)
        chk_phone = ttk.Checkbutton(r5, text="Phone / Tel", variable=self.phone_dork_var, command=self._rebuild_query)
        chk_phone.pack(side=tk.LEFT, padx=(0, 12))
        ToolTip(chk_phone, "Appends (\"phone\" OR \"tel\" OR \"mobile\") to prioritize contacts with numbers.")
        
        self.custom_email_domain_var = tk.StringVar(value="")
        custom_dom_lbl = ttk.Label(r5, text="Domain:")
        custom_dom_lbl.pack(side=tk.LEFT, padx=(4, 2))
        
        custom_dom_entry = ttk.Entry(r5, textvariable=self.custom_email_domain_var, font=("Segoe UI", 9), width=16)
        custom_dom_entry.pack(side=tk.LEFT, padx=(0, 5))
        custom_dom_entry.bind("<KeyRelease>", lambda e: self._rebuild_query())
        ToolTip(custom_dom_entry, "Search for company-specific email domain (e.g. acme.com or @acme.com).")
        
        # Row 6: Exclude Keywords & Filetype
        r6 = ttk.Frame(form_frame)
        r6.pack(fill=tk.X, pady=2)
        
        hl_exclude = self._create_help_label(r6, "Exclude Words (-):", "Excludes unwanted terms with the minus operator. E.g. -jobs -recruiter -intern.")
        hl_exclude.pack(side=tk.LEFT)
        
        self.exclude_var = tk.StringVar(value="")
        exclude_entry = ttk.Entry(r6, textvariable=self.exclude_var, font=("Segoe UI", 9), width=32)
        exclude_entry.pack(side=tk.LEFT, padx=(0, 12))
        exclude_entry.bind("<KeyRelease>", lambda e: self._rebuild_query())
        ToolTip(exclude_entry, "Words prefixed with '-' will be excluded from search results.")
        
        hl_filetype = self._create_help_label(r6, "Filetype (filetype:):", "Filters for specific file formats like PDF resumes, Excel sheets, or configuration files.", width=16)
        hl_filetype.pack(side=tk.LEFT)
        
        self.filetype_var = tk.StringVar(value="None")
        filetype_combo = ttk.Combobox(r6, textvariable=self.filetype_var, values=["None", "filetype:pdf", "filetype:doc OR filetype:docx", "filetype:xls OR filetype:xlsx", "filetype:config", "filetype:env", "filetype:sql"], width=18, state="readonly")
        filetype_combo.pack(side=tk.LEFT)
        filetype_combo.bind("<<ComboboxSelected>>", lambda e: self._rebuild_query())
        ToolTip(filetype_combo, "Select filetype extension to discover documents or files.")

        # Row 7: Advanced Operators Toolbar (with Hover Tooltips)
        r7 = ttk.Frame(form_frame)
        r7.pack(fill=tk.X, pady=(4, 0))
        
        hl_ops = self._create_help_label(r7, "Quick Insert Operator:", "Click any operator button to insert it into your assembled query. Hover to see what each operator does.")
        hl_ops.pack(side=tk.LEFT)
        
        dork_ops = [
            ("intext:", ' intext:""', "intext:\"keyword\" — Searches for occurrences of keyword anywhere inside the webpage body text."),
            ("intitle:", ' intitle:""', "intitle:\"keyword\" — Searches for keywords inside the webpage HTML title tag."),
            ("inurl:", ' inurl:""', "inurl:\"keyword\" — Finds keywords present directly in the webpage URL path."),
            ("site:", ' site:', "site:domain.com — Restricts search results to a specific website, domain, or TLD."),
            ("filetype:", ' filetype:pdf', "filetype:extension — Filters search results for specific file formats (pdf, doc, xls, config, env, sql)."),
            ("before:", ' before:2025-01-01', "before:YYYY-MM-DD — Returns only pages indexed before the specified date or year."),
            ("after:", ' after:2023-01-01', "after:YYYY-MM-DD — Returns only pages indexed after the specified date or year."),
            (".. (Range)", ' $100..$500', ".. — Searches for numbers within a range such as prices or years ($100..$500 or 2020..2024)."),
            ("error:", ' error:""', "error:\"msg\" — Searches for exact programming error messages or stacktraces."),
            ("related:", ' related:', "related:domain.com — Discovers websites structurally or semantically similar to target domain."),
            ("cache:", ' cache:', "cache:domain.com — Retrieves Google's cached snapshot of a specific webpage."),
            ("* (Wildcard)", ' *', "* — Wildcard acting as a placeholder for any unknown words or phrases in search.")
        ]
        for op_label, op_val, op_tip in dork_ops:
            btn_op = ttk.Button(r7, text=op_label, style="Operator.TButton", command=lambda v=op_val: self._append_operator_to_query(v))
            btn_op.pack(side=tk.LEFT, padx=1)
            ToolTip(btn_op, op_tip)

        # 3. Live Assembled Dork Preview Box
        query_preview_frame = ttk.LabelFrame(self.tab_builder, text=" Live Assembled Search Query (Auto-Generated) ", padding="8")
        query_preview_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.assembled_query_var = tk.StringVar()
        self.query_preview_entry = ttk.Entry(query_preview_frame, textvariable=self.assembled_query_var, font=("Consolas", 10, "bold"), foreground="#1E293B")
        self.query_preview_entry.pack(fill=tk.X, pady=(0, 5))
        self.query_preview_entry.bind("<Return>", lambda event: self._start_search())
        ToolTip(self.query_preview_entry, "This query updates in real-time as you edit form fields above. You can also edit it directly here.")
        
        preview_btn_bar = ttk.Frame(query_preview_frame)
        preview_btn_bar.pack(fill=tk.X)
        
        btn_copy_query = ttk.Button(preview_btn_bar, text="📋 Copy Query", style="Secondary.TButton", command=self._copy_query_to_clipboard)
        btn_copy_query.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(btn_copy_query, "Copies the complete assembled search string to clipboard.")
        
        btn_reset_query = ttk.Button(preview_btn_bar, text="🔄 Clear All Fields / Reset", style="Secondary.TButton", command=self._reset_builder)
        btn_reset_query.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(btn_reset_query, "Clears all textboxes and query fields back to a blank canvas.")
        
        lbl_hint_live = ttk.Label(preview_btn_bar, text="✨ Updates live as you change fields. You can also edit it directly in the text box above.", foreground="#64748B")
        lbl_hint_live.pack(side=tk.LEFT)
        
        # 4. Search Execution Controls
        exec_frame = ttk.LabelFrame(self.tab_builder, text=" Search Execution Controls ", padding="10")
        exec_frame.pack(fill=tk.X, pady=(0, 4))
        
        # Row 1: Parameters & Browser Window Mode
        r_params = ttk.Frame(exec_frame)
        r_params.pack(fill=tk.X, pady=(0, 6))
        
        hl_pages = self._create_help_label(r_params, "Pages to Scrape:", "Number of result pages to fetch (each page has ~10-15 results).", width=14)
        hl_pages.pack(side=tk.LEFT)
        
        self.pages_var = tk.IntVar(value=3)
        pages_spin = ttk.Spinbox(r_params, from_=1, to=20, textvariable=self.pages_var, width=4)
        pages_spin.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(pages_spin, "Number of search result pages (1 to 20).")
        
        hl_delay = self._create_help_label(r_params, "Delay (sec):", "Pause duration between fetching consecutive pages to prevent IP rate-limiting.", width=10)
        hl_delay.pack(side=tk.LEFT)
        
        self.delay_var = tk.DoubleVar(value=2.0)
        delay_spin = ttk.Spinbox(r_params, from_=0.5, to=15.0, increment=0.5, textvariable=self.delay_var, width=4)
        delay_spin.pack(side=tk.LEFT, padx=(0, 20))
        ToolTip(delay_spin, "Delay between pages in seconds (2.0s is recommended).")
        
        # Browser Visibility Mode
        hl_win = self._create_help_label(r_params, "Browser Display:", "Choose how Chrome runs: Silent in the background (no window), minimized corner widget, or normal size.", width=14)
        hl_win.pack(side=tk.LEFT)
        
        self.browser_mode_var = tk.StringVar(value="headless")
        
        r_headless = ttk.Radiobutton(r_params, text="👻 Silent (No Window - Default)", value="headless", variable=self.browser_mode_var)
        r_headless.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(r_headless, "Runs Chrome 100% invisibly in the background with zero pop-up window.")
        
        r_mini = ttk.Radiobutton(r_params, text="🔘 Minimized Corner", value="mini", variable=self.browser_mode_var)
        r_mini.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(r_mini, "Runs Chrome minimized or in a tiny bottom-corner widget.")
        
        r_normal = ttk.Radiobutton(r_params, text="🖥️ Normal Window", value="normal", variable=self.browser_mode_var)
        r_normal.pack(side=tk.LEFT)
        ToolTip(r_normal, "Opens standard size browser window (useful for manually solving CAPTCHAs if needed).")
        
        # Row 2: Action Buttons
        r_actions = ttk.Frame(exec_frame)
        r_actions.pack(fill=tk.X, pady=(2, 0))
        
        self.search_btn = ttk.Button(r_actions, text="🚀 Search & Extract Leads", style="Primary.TButton", command=self._start_search)
        self.search_btn.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(self.search_btn, "Executes search on selected engine and extracts structured contact leads.")
        
        self.stop_btn = ttk.Button(r_actions, text="⏹ Stop Search", style="Danger.TButton", command=self._stop_search, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(self.stop_btn, "Stops the active search immediately.")
        
        hint_exec = ttk.Label(r_actions, text="💡 Mini Corner Window keeps Google docked as a tiny widget in the bottom corner so your screen stays clear.", foreground="#64748B", font=("Segoe UI", 8, "italic"))
        hint_exec.pack(side=tk.LEFT)

    def _reset_builder(self):
        """Clears all textboxes, criteria fields, and search query to a completely blank state."""
        self._updating_query = True
        self.site_preset_var.set("")
        self.org_var.set("")
        self.titles_var.set("")
        self.location_var.set("")
        self.email_dork_var.set(False)
        self.phone_dork_var.set(False)
        self.custom_email_domain_var.set("")
        self.exclude_var.set("")
        self.filetype_var.set("None")
        self.assembled_query_var.set("")
        if hasattr(self, "preset_combo"):
            self.preset_combo.current(0)
        self._updating_query = False
        self.status_var.set("All criteria fields cleared. Ready for custom search or template.")

    def _wrap_site_syntax(self):
        """Turns 'example.com' or 'www.example.com' or 'https://example.com' into 'site:example.com'."""
        raw = self.site_preset_var.get().strip()
        if not raw or "(All" in raw:
            return
        # Remove http:// or https:// and trailing slashes
        clean = re.sub(r'^https?://', '', raw, flags=re.IGNORECASE).rstrip('/')
        clean = re.sub(r'^site:\s*https?://', 'site:', clean, flags=re.IGNORECASE)
        clean = re.sub(r'^site:\s*', 'site:', clean, flags=re.IGNORECASE)
        if not clean.startswith("site:"):
            self.site_preset_var.set(f"site:{clean}")
        else:
            self.site_preset_var.set(clean)
        self._rebuild_query()

    def _on_engine_selected(self, event=None):
        raw = self.engine_combo.get()
        if "Google" in raw:
            self.engine_var.set("Google")
        elif "Bing" in raw:
            self.engine_var.set("Bing")
        elif "DuckDuckGo" in raw:
            self.engine_var.set("DuckDuckGo")
        elif "Brave" in raw:
            self.engine_var.set("Brave")
        elif "Yahoo" in raw:
            self.engine_var.set("Yahoo")
        elif "Ahmia" in raw:
            self.engine_var.set("Ahmia")
        elif "Yandex" in raw:
            self.engine_var.set("Yandex")
        self.status_var.set(f"Selected Search Engine: {self.engine_var.get()}")

    # -------------------------------------------------------------
    # TAB 2: RESULTS & TEXT BOX
    # -------------------------------------------------------------
    def _build_tab_results(self):
        # Format Toolbar & Stats
        toolbar = ttk.Frame(self.tab_results)
        toolbar.pack(fill=tk.X, pady=(0, 6))
        
        fmt_lbl = ttk.Label(toolbar, text="Display Format:", style="Section.TLabel")
        fmt_lbl.pack(side=tk.LEFT, padx=(0, 8))
        
        self.format_var = tk.StringVar(value="formatted")
        
        r1 = ttk.Radiobutton(toolbar, text="Structured Cards", value="formatted", variable=self.format_var, command=self._refresh_text_display)
        r1.pack(side=tk.LEFT, padx=(0, 10))
        
        r2 = ttk.Radiobutton(toolbar, text="Excel TSV (Tab-Separated)", value="tsv", variable=self.format_var, command=self._refresh_text_display)
        r2.pack(side=tk.LEFT, padx=(0, 10))
        
        r3 = ttk.Radiobutton(toolbar, text="CSV Format", value="csv", variable=self.format_var, command=self._refresh_text_display)
        r3.pack(side=tk.LEFT, padx=(0, 10))
        
        r4 = ttk.Radiobutton(toolbar, text="Emails Only", value="emails", variable=self.format_var, command=self._refresh_text_display)
        r4.pack(side=tk.LEFT, padx=(0, 10))
        
        r5 = ttk.Radiobutton(toolbar, text="URLs Only", value="urls", variable=self.format_var, command=self._refresh_text_display)
        r5.pack(side=tk.LEFT)
        
        self.count_badge = ttk.Label(toolbar, text="0 leads collected", style="Badge.TLabel")
        self.count_badge.pack(side=tk.RIGHT)
        
        # Filter row inside results
        filter_row = ttk.Frame(self.tab_results)
        filter_row.pack(fill=tk.X, pady=(0, 6))
        
        filter_lbl = ttk.Label(filter_row, text="Filter Results:")
        filter_lbl.pack(side=tk.LEFT, padx=(0, 6))
        
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *args: self._refresh_text_display())
        filter_entry = ttk.Entry(filter_row, textvariable=self.filter_var, font=("Segoe UI", 9), width=32)
        filter_entry.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(filter_entry, "Filter live results by name, keyword, role, email, or company.")
        
        hint_flt = ttk.Label(filter_row, text="(Type name, keyword, role, or company to instantly filter below)", foreground="#64748B")
        hint_flt.pack(side=tk.LEFT)
        
        # Large Text Box with Dual Scrollbars
        text_container = ttk.Frame(self.tab_results)
        text_container.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        
        self.results_text = tk.Text(
            text_container,
            wrap=tk.NONE,
            font=("Consolas", 10),
            bg="#FFFFFF",
            fg="#0F172A",
            insertbackground="#0F172A",
            selectbackground="#3B82F6",
            selectforeground="#FFFFFF",
            relief=tk.SOLID,
            borderwidth=1,
            padx=10,
            pady=10
        )
        
        vsb = ttk.Scrollbar(text_container, orient="vertical", command=self.results_text.yview)
        hsb = ttk.Scrollbar(text_container, orient="horizontal", command=self.results_text.xview)
        self.results_text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.results_text.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)
        
        text_container.rowconfigure(0, weight=1)
        text_container.columnconfigure(0, weight=1)
        
        self.results_text.insert(tk.END, "Your scraped leads and contact emails will appear here.\nSelect your search engine, build query in Tab 1, and click 'Search & Extract Leads'.")
        
        # Action Buttons
        action_bar = ttk.Frame(self.tab_results)
        action_bar.pack(fill=tk.X)
        
        self.copy_all_btn = ttk.Button(action_bar, text="📋 Copy All to Clipboard", style="Success.TButton", command=self._copy_to_clipboard)
        self.copy_all_btn.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(self.copy_all_btn, "Copies all current text box content to clipboard.")
        
        self.copy_emails_btn = ttk.Button(action_bar, text="✉️ Copy Emails List", style="Accent.TButton", command=self._copy_emails_only)
        self.copy_emails_btn.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(self.copy_emails_btn, "Extracts and copies only unique email addresses found.")
        
        self.save_csv_btn = ttk.Button(action_bar, text="💾 Export CSV File", style="Secondary.TButton", command=self._save_to_csv)
        self.save_csv_btn.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(self.save_csv_btn, "Exports results to a clean CSV file.")
        
        self.clear_btn = ttk.Button(action_bar, text="🗑 Clear Results", style="Secondary.TButton", command=self._clear_results)
        self.clear_btn.pack(side=tk.LEFT)
        ToolTip(self.clear_btn, "Clears current extracted results.")

    # -------------------------------------------------------------
    # TAB 3: SEARCH OPERATORS CHEAT SHEET (MULTI-ENGINE COMPREHENSIVE)
    # -------------------------------------------------------------
    def _build_tab_cheatsheet(self):
        header_cs = ttk.Label(self.tab_cheatsheet, text="Multi-Engine Search Operators & Dork Cheat Sheet", style="Header.TLabel")
        header_cs.pack(anchor=tk.W, pady=(0, 2))
        
        sub_cs = ttk.Label(self.tab_cheatsheet, text="Comprehensive guide across Google, Bing, DuckDuckGo, Brave, Yahoo, and Tor/Ahmia. Click '⚡ Load' on any item.", style="SubHeader.TLabel")
        sub_cs.pack(anchor=tk.W, pady=(0, 8))
        
        # Scrollable container for cheat sheet items
        canvas = tk.Canvas(self.tab_cheatsheet, bg="#F1F5F9", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_cheatsheet, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 0. Engine Compatibility Overview
        compat_frame = ttk.LabelFrame(scrollable_frame, text=" 🌐 Multi-Engine Operator Compatibility Matrix ", padding="8")
        compat_frame.pack(fill=tk.X, pady=(0, 8), padx=4)
        
        matrix = [
            ("Google", "site:, inurl:, intitle:, intext:, filetype:, cache:, related:, before:, after:, -term, OR, *"),
            ("Bing", "site:, filetype:, intitle:, inbody:, inurl:, contains:, near:, feed:, ip:, -term, OR, NOT"),
            ("DuckDuckGo", "site:, filetype:, intitle:, inurl:, -term, OR, \\bangs (e.g. !w, !g, !so)"),
            ("Brave Search", "site:, filetype:, intitle:, inurl:, -term, OR, after:, before:"),
            ("Yahoo", "site:, filetype:, intitle:, inurl:, hostname:, -term, OR"),
            ("Tor / Ahmia", "Searches .onion Tor hidden services & darknet directory indexes directly")
        ]
        for eng_name, ops_list in matrix:
            row = ttk.Frame(compat_frame, padding="1")
            row.pack(fill=tk.X, pady=1)
            lbl_e = ttk.Label(row, text=eng_name, font=("Segoe UI", 9, "bold"), foreground="#2563EB", width=14, anchor=tk.W)
            lbl_e.pack(side=tk.LEFT)
            lbl_o = ttk.Label(row, text=ops_list, font=("Consolas", 8), foreground="#334155")
            lbl_o.pack(side=tk.LEFT)
        
        # 1. Search Filters & Directives Table
        filters_frame = ttk.LabelFrame(scrollable_frame, text=" 🔍 Core Search Filters & Directives ", padding="8")
        filters_frame.pack(fill=tk.X, pady=(0, 8), padx=4)
        
        filters_data = [
            ("allintext:", "Searches for occurrences of ALL given keywords in page text", 'allintext:"fire brigade" "head of it"'),
            ("intext: / inbody:", "Searches for occurrences of keywords anywhere in text", 'intext:"confidential salary"'),
            ("inurl:", "Searches for a URL containing one of the specified terms", 'inurl:"resume" OR inurl:"cv"'),
            ("allinurl:", "Searches for a URL matching ALL the keywords in query", 'allinurl:admin login'),
            ("intitle:", "Searches for occurrences of keywords in HTML title tag", 'intitle:"index.of"'),
            ("allintitle:", "Searches for occurrences of ALL keywords in title tag", 'allintitle:"IT Director" "Fire"'),
            ("site:", "Restricts search to a specific domain, sub-path, or TLD", 'site:linkedin.com/in/'),
            ("filetype: / ext:", "Searches for specific file extensions (pdf, doc, xls, config, env)", 'filetype:pdf javascript guide'),
            ("link:", "Searches for external web pages linking to a specific URL", 'link:"github.com"'),
            ("numrange: / ..", "Locates specific number or price ranges ($100..$500)", 'phone $100..$500'),
            ("before: / after:", "Filters results indexed before or after a specific year/date", 'react tutorial after:2023'),
            ("allinanchor: / inanchor:", "Finds sites with key terms inside anchor links pointing to them", 'inanchor:rat'),
            ("allinpostauthor:", "Finds blog posts/articles written by a specific author name", 'allinpostauthor:"John Doe"'),
            ("related:", "Lists web pages that are similar to a given website", 'related:microsoft.com'),
            ("cache:", "Retrieves Google cached snapshot of a specific web page", 'cache:example.com'),
        ]
        
        for filt, desc, eg in filters_data:
            row = ttk.Frame(filters_frame, padding="2")
            row.pack(fill=tk.X, pady=1)
            
            lbl_f = ttk.Label(row, text=filt, font=("Consolas", 9, "bold"), foreground="#2563EB", width=20, anchor=tk.W)
            lbl_f.pack(side=tk.LEFT)
            
            lbl_d = ttk.Label(row, text=desc, foreground="#334155", width=52, anchor=tk.W)
            lbl_d.pack(side=tk.LEFT, padx=(0, 8))
            
            lbl_eg = ttk.Label(row, text=eg, font=("Consolas", 8), foreground="#64748B")
            lbl_eg.pack(side=tk.LEFT)
            
            btn_load_f = ttk.Button(row, text="⚡ Load", style="Operator.TButton", command=lambda d=eg: self._load_custom_dork(d))
            btn_load_f.pack(side=tk.RIGHT)
            
        # 2. Boolean Operators & Modifiers Table
        ref_frame = ttk.LabelFrame(scrollable_frame, text=" ⚡ Boolean Operators & Modifiers Guide ", padding="8")
        ref_frame.pack(fill=tk.X, pady=(0, 8), padx=4)
        
        ops = [
            ('"Exact Phrase"', 'Forces exact verbatim phrase match (e.g. "how to center a div")', '"how to center a div"'),
            ('OR / |', 'Matches either the left or right term (e.g. python OR javascript)', 'python OR javascript'),
            ('AND / &', 'Matches both terms in the same page (e.g. site:github.com & react)', 'site:github.com & react'),
            ('( ) Parentheses', 'Groups terms together: (javascript OR python) tutorial', '(javascript OR python) tutorial'),
            ('-keyword', 'Excludes results containing this keyword (e.g. javascript -jquery)', 'javascript -jquery'),
            ('+keyword', 'Prioritizes inclusion / keyword occurrence (e.g. -site:fb.com +site:fb.*)', '-site:facebook.com +site:facebook.*'),
            ('* (Wildcard)', 'Acts as a placeholder for any unknown words (e.g. "how to * in python")', 'how to * in python'),
            ('~word (Synonyms)', 'Brings back synonyms (e.g. ~set returns configure, collection, change)', '~set'),
            ('@username', 'Searches for social media tags or usernames', '@username twitter'),
            ('#hashtag', 'Searches for specific topic hashtags', '#javascript')
        ]
        
        for op, desc, eg in ops:
            row = ttk.Frame(ref_frame, padding="2")
            row.pack(fill=tk.X, pady=1)
            lbl_op = ttk.Label(row, text=op, font=("Consolas", 9, "bold"), foreground="#059669", width=22, anchor=tk.W)
            lbl_op.pack(side=tk.LEFT)
            lbl_desc = ttk.Label(row, text=desc, foreground="#334155", width=50, anchor=tk.W)
            lbl_desc.pack(side=tk.LEFT, padx=(0, 8))
            lbl_eg = ttk.Label(row, text=eg, font=("Consolas", 8), foreground="#64748B")
            lbl_eg.pack(side=tk.LEFT)
            btn_load_o = ttk.Button(row, text="⚡ Load", style="Operator.TButton", command=lambda d=eg: self._load_custom_dork(d))
            btn_load_o.pack(side=tk.RIGHT)

        # 3. Code, Developer & Debugging Dorks
        dev_frame = ttk.LabelFrame(scrollable_frame, text=" 💻 Developer, Code & Debugging Search Patterns ", padding="8")
        dev_frame.pack(fill=tk.X, pady=(0, 8), padx=4)
        
        dev_dorks = [
            ("Finding Code Solutions", 'site:stackoverflow.com OR site:github.com "specific error message"', "Finds solutions across StackOverflow and GitHub repos."),
            ("Official Tech Documentation", 'site:docs.microsoft.com OR site:developer.mozilla.org javascript', "Finds official API docs without SEO spam blogs."),
            ("Finding Recent Tutorials", 'intitle:tutorial (react OR vue) after:2023', "Discovers modern, up-to-date framework tutorials."),
            ("GitHub Repository Code Search", 'site:github.com repo:facebook/react hooks', "Searches within a specific organization/repo on GitHub."),
            ("Error Message Debugger", 'error:"npm ERR!" OR error:"TypeError:"', "Finds exact stacktraces and resolution threads.")
        ]
        
        for title, dork, desc in dev_dorks:
            item_frame = ttk.Frame(dev_frame, padding="4")
            item_frame.pack(fill=tk.X, pady=2)
            
            top_line = ttk.Frame(item_frame)
            top_line.pack(fill=tk.X)
            
            t_lbl = ttk.Label(top_line, text=title, font=("Segoe UI", 9, "bold"), foreground="#0F172A")
            t_lbl.pack(side=tk.LEFT)
            
            btn_load = ttk.Button(top_line, text="⚡ Load into Builder", style="Primary.TButton", command=lambda d=dork: self._load_custom_dork(d))
            btn_load.pack(side=tk.RIGHT)
            
            d_lbl = ttk.Label(item_frame, text=desc, foreground="#64748B", font=("Segoe UI", 8))
            d_lbl.pack(anchor=tk.W, pady=(1, 2))
            
            code_box = ttk.Entry(item_frame, font=("Consolas", 8), foreground="#1E293B")
            code_box.insert(0, dork)
            code_box.configure(state="readonly")
            code_box.pack(fill=tk.X)
            
        # 4. OSINT, Security & Lead Generation Recipes
        recipes_frame = ttk.LabelFrame(scrollable_frame, text=" 🎯 OSINT, Security & Lead Generation Recipes ", padding="8")
        recipes_frame.pack(fill=tk.X, pady=(0, 8), padx=4)
        
        recipes = [
            (
                "🔥 UK Fire & Rescue IT Leaders",
                'site:linkedin.com/in/ ("Fire and Rescue" OR "Fire Brigade") ("Head of IT" OR "Head of ICT" OR "Head of Technology" OR "Head of Data" OR "ICT Manager") "United Kingdom" -jobs -recruiter -intern',
                "Extracts IT, Data, and Tech leaders across UK Fire Services."
            ),
            (
                "📂 Open Directory Discovery (Index of /)",
                'intext:"index of /"',
                "Finds open web server directories with exposed browsing enabled."
            ),
            (
                "📑 Confidential Salary & Approved Budget Documents",
                'ext:(doc | pdf | xls | txt | rtf) (intext:confidential salary | intext:"budget approved") inurl:confidential',
                "Locates sensitive internal salary, budget, and compensation records."
            ),
            (
                "⚙️ Exposed Web Server Configs & FTP Credentials",
                'filetype:config inurl:web.config inurl:ftp',
                "Finds exposed web configuration files containing connection strings."
            ),
            (
                "📚 Open E-Book & PDF Document Archive",
                'intitle:"index.of" "parent directory" "size" "last modified" "description" (pdf|txt|epub|doc|docx) -inurl:(jsp|php|html|aspx|htm|cf|shtml|ebooks|ebook) -site:.info',
                "Discovers open directories indexing downloadable e-books and documents."
            ),
            (
                "🎬 Direct Media / Video Index (DVDRip / MP4)",
                'parent directory DVDRip -xxx -html -htm -php -shtml -opendivx -md5 -md5sums',
                "Finds public video and media repository folders without web interfaces."
            ),
            (
                "🏥 NHS Hospital Trusts - Chief Information Officers & IT Directors",
                'site:linkedin.com/in/ ("NHS Trust" OR "NHS Foundation Trust") ("Chief Information Officer" OR "CIO" OR "Director of IT" OR "Head of Digital") "United Kingdom"',
                "Targets healthcare and NHS digital leaders in the UK."
            ),
            (
                "🏛️ UK Local Councils & Police - Tech Decision Makers",
                'site:linkedin.com/in/ ("City Council" OR "Borough Council" OR "County Council" OR "Police") ("Head of IT" OR "Head of ICT" OR "ICT Director") "United Kingdom"',
                "Finds IT heads in local government and police constabularies."
            ),
            (
                "📧 Hunter: LinkedIn Leads with Public Emails in Snippet",
                'site:linkedin.com/in/ ("CEO" OR "Founder" OR "Managing Director") ("@gmail.com" OR "@yahoo.com" OR "@outlook.com") "London"',
                "Discovers executives who posted their personal email on their profile."
            ),
            (
                "📄 Resumes & CVs of IT Directors (PDF)",
                'filetype:pdf (inurl:resume OR inurl:cv) ("Head of IT" OR "IT Director") ("Fire" OR "Emergency") "United Kingdom"',
                "Finds public PDF resumes and CV files hosted on the web."
            )
        ]
        
        for title, dork, desc in recipes:
            item_frame = ttk.Frame(recipes_frame, padding="4")
            item_frame.pack(fill=tk.X, pady=2)
            
            top_line = ttk.Frame(item_frame)
            top_line.pack(fill=tk.X)
            
            t_lbl = ttk.Label(top_line, text=title, font=("Segoe UI", 9, "bold"), foreground="#0F172A")
            t_lbl.pack(side=tk.LEFT)
            
            btn_load = ttk.Button(top_line, text="⚡ Load into Builder", style="Primary.TButton", command=lambda d=dork: self._load_custom_dork(d))
            btn_load.pack(side=tk.RIGHT)
            
            d_lbl = ttk.Label(item_frame, text=desc, foreground="#64748B", font=("Segoe UI", 8))
            d_lbl.pack(anchor=tk.W, pady=(1, 2))
            
            code_box = ttk.Entry(item_frame, font=("Consolas", 8), foreground="#1E293B")
            code_box.insert(0, dork)
            code_box.configure(state="readonly")
            code_box.pack(fill=tk.X)

    # -------------------------------------------------------------
    # TAB 4: QUERY HISTORY LOG
    # -------------------------------------------------------------
    def _build_tab_history(self):
        header_h = ttk.Label(self.tab_history, text="📜 Executed Search Queries History Log", style="Header.TLabel")
        header_h.pack(anchor=tk.W, pady=(0, 2))
        
        sub_h = ttk.Label(self.tab_history, text="Every search query you execute is logged below. Select any past query and click 'Recall Query' to load it back into the builder.", style="SubHeader.TLabel")
        sub_h.pack(anchor=tk.W, pady=(0, 8))
        
        # Search / Filter Bar for History
        h_toolbar = ttk.Frame(self.tab_history)
        h_toolbar.pack(fill=tk.X, pady=(0, 6))
        
        filter_lbl = ttk.Label(h_toolbar, text="Filter History:")
        filter_lbl.pack(side=tk.LEFT, padx=(0, 6))
        
        self.hist_filter_var = tk.StringVar()
        self.hist_filter_var.trace_add("write", lambda *args: self._refresh_history_listbox())
        hist_filter_entry = ttk.Entry(h_toolbar, textvariable=self.hist_filter_var, font=("Segoe UI", 9), width=30)
        hist_filter_entry.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(hist_filter_entry, "Search through your previous logged search queries.")
        
        btn_recall_sel = ttk.Button(h_toolbar, text="⚡ Recall Selected into Builder", style="Primary.TButton", command=self._recall_selected_from_listbox)
        btn_recall_sel.pack(side=tk.LEFT, padx=(0, 8))
        
        btn_copy_hist = ttk.Button(h_toolbar, text="📋 Copy Selected Query", style="Secondary.TButton", command=self._copy_selected_history)
        btn_copy_hist.pack(side=tk.LEFT, padx=(0, 8))
        
        btn_clear_hist = ttk.Button(h_toolbar, text="🗑 Clear History Log", style="Danger.TButton", command=self._clear_history_log)
        btn_clear_hist.pack(side=tk.LEFT)
        
        # History Listbox Container
        list_container = ttk.Frame(self.tab_history)
        list_container.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        
        self.history_listbox = tk.Listbox(
            list_container,
            font=("Consolas", 10),
            bg="#FFFFFF",
            fg="#0F172A",
            selectbackground="#2563EB",
            selectforeground="#FFFFFF",
            relief=tk.SOLID,
            borderwidth=1,
            activestyle="none"
        )
        
        vsb_h = ttk.Scrollbar(list_container, orient="vertical", command=self.history_listbox.yview)
        hsb_h = ttk.Scrollbar(list_container, orient="horizontal", command=self.history_listbox.xview)
        self.history_listbox.configure(yscrollcommand=vsb_h.set, xscrollcommand=hsb_h.set)
        
        self.history_listbox.grid(row=0, column=0, sticky=tk.NSEW)
        vsb_h.grid(row=0, column=1, sticky=tk.NS)
        hsb_h.grid(row=1, column=0, sticky=tk.EW)
        
        list_container.rowconfigure(0, weight=1)
        list_container.columnconfigure(0, weight=1)
        
        self.history_listbox.bind("<Double-Button-1>", lambda e: self._recall_selected_from_listbox())
        self._refresh_history_listbox()

    # -------------------------------------------------------------
    # HISTORY LOGGING & RECALL ENGINE
    # -------------------------------------------------------------
    def _load_search_history(self):
        """Loads search query history lines from file."""
        history = []
        if os.path.exists(HISTORY_LOG_FILE):
            try:
                with open(HISTORY_LOG_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            history.append(line)
            except Exception:
                pass
        return history

    def _log_search_query(self, engine, query):
        """Appends an executed search query to the persistent log file."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{engine}] {query}"
        self.search_history.insert(0, entry)
        
        try:
            with open(HISTORY_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
        except Exception:
            pass
            
        self.after(0, self._refresh_history_combo)
        self.after(0, self._refresh_history_listbox)

    def _refresh_history_combo(self):
        """Refreshes the history combobox dropdown in Tab 1."""
        display_vals = []
        for item in self.search_history[:25]:
            display_vals.append(item)
        if hasattr(self, "history_combo"):
            self.history_combo['values'] = display_vals
            if display_vals:
                self.history_combo.current(0)

    def _refresh_history_listbox(self):
        """Refreshes the history listbox in Tab 4 with search filter support."""
        if not hasattr(self, "history_listbox"):
            return
        filt = self.hist_filter_var.get().lower().strip() if hasattr(self, "hist_filter_var") else ""
        self.history_listbox.delete(0, tk.END)
        for item in self.search_history:
            if not filt or filt in item.lower():
                self.history_listbox.insert(tk.END, item)

    def _extract_query_from_log_entry(self, log_entry):
        """Extracts engine and query string from formatted log entry: [2026-09-25 15:30:00] [Google] query..."""
        m = re.match(r'\[.*?\]\s*\[(.*?)\]\s*(.*)', log_entry)
        if m:
            return m.group(1), m.group(2)
        return "Google", log_entry

    def _on_history_combo_selected(self, event=None):
        val = self.history_combo.get()
        if not val:
            return
        engine, query = self._extract_query_from_log_entry(val)
        self._load_recalled_query(engine, query)

    def _recall_selected_from_listbox(self):
        sel = self.history_listbox.curselection()
        if not sel:
            messagebox.showinfo("History", "Please select a query line from the history list.")
            return
        val = self.history_listbox.get(sel[0])
        engine, query = self._extract_query_from_log_entry(val)
        self._load_recalled_query(engine, query)
        self.notebook.select(self.tab_builder)

    def _copy_selected_history(self):
        sel = self.history_listbox.curselection()
        if not sel:
            messagebox.showinfo("History", "Please select a query line from the list.")
            return
        val = self.history_listbox.get(sel[0])
        _, query = self._extract_query_from_log_entry(val)
        self.clipboard_clear()
        self.clipboard_append(query)
        messagebox.showinfo("Copied", f"Copied search query to clipboard:\n\n{query}")

    def _load_recalled_query(self, engine, query):
        """Loads a past query into the Query Builder and sets the engine."""
        self.assembled_query_var.set(query)
        if engine in ["Google", "Bing", "DuckDuckGo", "Brave", "Yahoo", "Ahmia", "Yandex"]:
            self.engine_var.set(engine)
            for idx, item in enumerate(self.engine_combo['values']):
                if engine in item:
                    self.engine_combo.current(idx)
                    break
        self.status_var.set(f"Recalled past query ({engine}): {query[:50]}...")
        messagebox.showinfo("Query Recalled", f"Recalled search into Query Builder:\n\nEngine: {engine}\nQuery:\n{query}")

    def _clear_history_log(self):
        if messagebox.askyesno("Clear History", "Are you sure you want to clear all logged search queries?"):
            self.search_history.clear()
            try:
                with open(HISTORY_LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                pass
            self._refresh_history_combo()
            self._refresh_history_listbox()
            self.status_var.set("Search history log cleared.")

    # -------------------------------------------------------------
    # QUERY BUILDER ENGINE
    # -------------------------------------------------------------
    def _append_operator_to_query(self, operator_snippet):
        current = self.assembled_query_var.get().strip()
        new_q = f"{current}{operator_snippet}" if current else operator_snippet.strip()
        self.assembled_query_var.set(new_q)

    def _format_as_or_group(self, string_var):
        """Converts comma-separated or raw words into quoted OR group: ("Word 1" OR "Word 2")"""
        text = string_var.get().strip()
        if not text:
            return
        if " OR " in text and text.startswith("(") and text.endswith(")"):
            return
            
        items = [i.strip().strip('"\'') for i in text.split(",") if i.strip()]
        if not items:
            items = [text.strip('"\'')]
            
        formatted = " OR ".join([f'"{item}"' for item in items])
        if len(items) > 1:
            formatted = f'({formatted})'
        string_var.set(formatted)
        self._rebuild_query()

    def _rebuild_query(self):
        """Assembles all form fields into a unified search query."""
        if self._updating_query:
            return
            
        parts = []
        
        # 1. Site / Platform
        site = self.site_preset_var.get().strip()
        if site and "(All" not in site:
            parts.append(site)
            
        # 2. Industry / Org
        org = self.org_var.get().strip()
        if org:
            if not (org.startswith("(") and org.endswith(")")) and " OR " in org:
                org = f"({org})"
            parts.append(org)
            
        # 3. Titles / Roles
        titles = self.titles_var.get().strip()
        if titles:
            if not (titles.startswith("(") and titles.endswith(")")) and " OR " in titles:
                titles = f"({titles})"
            parts.append(titles)
            
        # 4. Location
        loc = self.location_var.get().strip()
        if loc and "(Worldwide" not in loc:
            parts.append(loc)
            
        # 5. Email hunting
        if self.email_dork_var.get():
            parts.append('("@gmail.com" OR "@yahoo.com" OR "@outlook.com" OR "@hotmail.com" OR "email me at")')
            
        custom_dom = self.custom_email_domain_var.get().strip()
        if custom_dom:
            if not custom_dom.startswith("@") and "." in custom_dom:
                custom_dom = f"@{custom_dom}"
            parts.append(f'"{custom_dom}"')
            
        # 6. Phone hunting
        if self.phone_dork_var.get():
            parts.append('("phone" OR "tel" OR "mobile" OR "contact")')
            
        # 7. Filetype
        ft = self.filetype_var.get().strip()
        if ft and ft != "None":
            parts.append(ft)
            
        # 8. Exclusions
        ex = self.exclude_var.get().strip()
        if ex:
            parts.append(ex)
            
        final_query = " ".join(parts)
        self._updating_query = True
        self.assembled_query_var.set(final_query)
        self._updating_query = False

    def _on_preset_selected(self, event):
        combo_val = self.preset_combo.get()
        if "Clean / Blank" in combo_val:
            self._reset_builder()
        elif "Fire & Rescue" in combo_val:
            self._load_preset("fire_it")
        elif "NHS" in combo_val:
            self._load_preset("nhs_it")
        elif "Local Council" in combo_val:
            self._load_preset("gov_it")
        elif "Tech Startup" in combo_val:
            self._load_preset("tech_founders")
        elif "Procurement" in combo_val:
            self._load_preset("procurement")
        elif "Public Email" in combo_val:
            self._load_preset("email_hunter")
        elif "Developer Code" in combo_val:
            self._load_preset("dev_code")
        elif "Recent Tech" in combo_val:
            self._load_preset("recent_tutorials")
        elif "Official Doc" in combo_val:
            self._load_preset("official_docs")
        elif "Open Directory" in combo_val:
            self._load_preset("index_of")
        elif "Confidential" in combo_val:
            self._load_preset("confidential_docs")
        elif "Server Configs" in combo_val:
            self._load_preset("server_configs")
        elif "Price/Number" in combo_val:
            self._load_preset("number_range")
        elif "PDF Resumes" in combo_val:
            self._load_preset("resumes")
        else:
            self._reset_builder()

    def _load_preset(self, preset_key):
        self._updating_query = True
        if preset_key == "fire_it":
            self.site_preset_var.set("site:linkedin.com/in/")
            self.org_var.set('("Fire and Rescue" OR "Fire Brigade")')
            self.titles_var.set('("Head of IT" OR "Head of ICT" OR "Head of Technology" OR "Head of Data" OR "ICT Manager")')
            self.location_var.set('"United Kingdom"')
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("-jobs -recruiter -intern")
            self.filetype_var.set("None")
            
        elif preset_key == "nhs_it":
            self.site_preset_var.set("site:linkedin.com/in/")
            self.org_var.set('("NHS Trust" OR "NHS Foundation Trust" OR "NHS England")')
            self.titles_var.set('("Chief Information Officer" OR "CIO" OR "Director of IT" OR "Head of Digital" OR "Chief Digital Officer")')
            self.location_var.set('"United Kingdom"')
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("-jobs -recruitment")
            self.filetype_var.set("None")
            
        elif preset_key == "gov_it":
            self.site_preset_var.set("site:linkedin.com/in/")
            self.org_var.set('("City Council" OR "Borough Council" OR "County Council" OR "Police")')
            self.titles_var.set('("Head of IT" OR "Head of ICT" OR "Head of Digital" OR "ICT Director")')
            self.location_var.set('"United Kingdom"')
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("-jobs")
            self.filetype_var.set("None")
            
        elif preset_key == "tech_founders":
            self.site_preset_var.set("site:linkedin.com/in/")
            self.org_var.set('("SaaS" OR "AI" OR "Fintech" OR "Startup")')
            self.titles_var.set('("Founder" OR "Co-Founder" OR "CEO" OR "CTO")')
            self.location_var.set('"London" OR "Greater London"')
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("-jobs")
            self.filetype_var.set("None")
            
        elif preset_key == "procurement":
            self.site_preset_var.set("site:linkedin.com/in/")
            self.org_var.set('("Public Sector" OR "Emergency Services" OR "NHS" OR "Council")')
            self.titles_var.set('("Head of Procurement" OR "Procurement Director" OR "Head of Commercial" OR "Supply Chain Manager")')
            self.location_var.set('"United Kingdom"')
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("-jobs")
            self.filetype_var.set("None")
            
        elif preset_key == "email_hunter":
            self.site_preset_var.set("site:linkedin.com/in/")
            self.org_var.set('("Fire and Rescue" OR "Emergency Services")')
            self.titles_var.set('("Head of IT" OR "Director" OR "Manager")')
            self.location_var.set('"United Kingdom"')
            self.email_dork_var.set(True)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("-jobs")
            self.filetype_var.set("None")

        elif preset_key == "dev_code":
            self.site_preset_var.set("site:stackoverflow.com OR site:github.com")
            self.org_var.set('"TypeError" OR "Exception"')
            self.titles_var.set("")
            self.location_var.set("")
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("")
            self.filetype_var.set("None")

        elif preset_key == "recent_tutorials":
            self.site_preset_var.set("(All Websites / Open Web)")
            self.org_var.set('intitle:tutorial (react OR python) after:2023')
            self.titles_var.set("")
            self.location_var.set("")
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("")
            self.filetype_var.set("None")

        elif preset_key == "official_docs":
            self.site_preset_var.set("site:docs.microsoft.com OR site:developer.mozilla.org")
            self.org_var.set('javascript OR python')
            self.titles_var.set("")
            self.location_var.set("")
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("")
            self.filetype_var.set("None")

        elif preset_key == "number_range":
            self.site_preset_var.set("(All Websites / Open Web)")
            self.org_var.set('phone $100..$500')
            self.titles_var.set("")
            self.location_var.set("")
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("")
            self.filetype_var.set("None")

        elif preset_key == "index_of":
            self.site_preset_var.set("(All Websites / Open Web)")
            self.org_var.set('intext:"index of /"')
            self.titles_var.set("")
            self.location_var.set("")
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("-inurl:(jsp|php|html|aspx|htm)")
            self.filetype_var.set("None")

        elif preset_key == "confidential_docs":
            self.site_preset_var.set("(All Websites / Open Web)")
            self.org_var.set('(intext:"confidential salary" OR intext:"budget approved") inurl:confidential')
            self.titles_var.set("")
            self.location_var.set("")
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("")
            self.filetype_var.set("filetype:pdf")

        elif preset_key == "server_configs":
            self.site_preset_var.set("(All Websites / Open Web)")
            self.org_var.set('inurl:web.config inurl:ftp')
            self.titles_var.set("")
            self.location_var.set("")
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("")
            self.filetype_var.set("filetype:config")
            
        elif preset_key == "resumes":
            self.site_preset_var.set("(All Websites / Open Web)")
            self.org_var.set('("Fire and Rescue" OR "Fire Service")')
            self.titles_var.set('("Head of IT" OR "ICT Manager")')
            self.location_var.set('"United Kingdom"')
            self.email_dork_var.set(False)
            self.phone_dork_var.set(False)
            self.custom_email_domain_var.set("")
            self.exclude_var.set("")
            self.filetype_var.set("filetype:pdf")
            
        elif preset_key == "custom":
            self._reset_builder()
            return
            
        self._updating_query = False
        self._rebuild_query()

    def _load_custom_dork(self, dork_string):
        """Directly loads a full dork string from cheat sheet and switches to builder."""
        self.assembled_query_var.set(dork_string)
        self.notebook.select(self.tab_builder)
        self.status_var.set("Loaded template into Query Builder. Ready to search.")
        messagebox.showinfo("Dork Loaded", f"Query loaded into Builder:\n\n{dork_string}")

    def _copy_query_to_clipboard(self):
        query = self.assembled_query_var.get().strip()
        if not query:
            return
        self.clipboard_clear()
        self.clipboard_append(query)
        self.status_var.set("✅ Copied Search Query to clipboard!")
        messagebox.showinfo("Copied", "Search Query copied to clipboard!\nYou can paste (Ctrl+V) directly into your browser.")

    def _refresh_google_auth_ui(self):
        """Updates the Google login button and status based on saved profile existence."""
        has_profile = os.path.exists(AUTH_PROFILE_DIR) and len(os.listdir(AUTH_PROFILE_DIR)) > 0
        if hasattr(self, "google_auth_btn"):
            if has_profile:
                self.google_auth_btn.configure(text="✅ Google Connected", style="Success.TButton")
                ToolTip(self.google_auth_btn, "Your Google Account session is active and saved locally. Click to manage or re-login.")
            else:
                self.google_auth_btn.configure(text="🔑 Log in to Google", style="Accent.TButton")
                ToolTip(self.google_auth_btn, "Open Chrome to log into your Google Account once. Saves cookies and trust tokens to bypass CAPTCHAs permanently.")

    def _open_google_login(self):
        """Shows instructions first in a dialog, then opens Chrome for Google Account login and confirms session on finish."""
        if self.is_running:
            messagebox.showwarning("Busy", "A search is currently running. Please stop it first.")
            return

        # 1. Pop up notification FIRST before launching browser
        proceed = messagebox.askokcancel(
            "🔑 Google Account Login Instructions",
            "A Chrome browser window will now open for you to log into your Google Account.\n\n"
            "Instructions:\n"
            "1. Enter your Google email & password in the opened window.\n"
            "2. Complete 2-Step Verification if prompted.\n"
            "3. Once you reach your Google dashboard or are logged in, simply CLOSE that Chrome window.\n\n"
            "The app will automatically save your session and confirm that your Google Account is connected!\n\n"
            "Click 'OK' to launch the login window."
        )
        if not proceed:
            return

        def _login_thread():
            self.after(0, self.status_var.set, "Opening Chrome for Google login...")
            opts = Options()
            opts.add_argument(f"--user-data-dir={AUTH_PROFILE_DIR}")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            opts.add_argument("--window-size=1050,750")
            try:
                login_driver = webdriver.Chrome(options=opts)
                login_driver.get("https://accounts.google.com/ServiceLogin")
                self.after(0, self.status_var.set, "Google Login in progress. Please log into Google and then close the Chrome window.")
                
                # Polling loop waiting for the user to finish login and close window
                while True:
                    time.sleep(1)
                    try:
                        # Check if browser window is still open
                        _ = login_driver.current_url
                    except Exception:
                        # User closed the Chrome window
                        break
                        
                try:
                    login_driver.quit()
                except Exception:
                    pass
                    
                # Update UI badge and show success confirmation dialog
                self.after(0, self._refresh_google_auth_ui)
                self.after(0, self.status_var.set, "✅ Google Account Connected! Session saved.")
                self.after(0, messagebox.showinfo, "✅ Google Connected", 
                    "✅ Google Account successfully connected!\n\n"
                    "Your authenticated session and trust cookies have been saved.\n"
                    "All future searches with Google will now use your logged-in profile to bypass CAPTCHAs!")
                    
            except Exception as e:
                self.after(0, messagebox.showerror, "Error", f"Could not launch Chrome for login: {e}")
        
        threading.Thread(target=_login_thread, daemon=True).start()

    # -------------------------------------------------------------
    # MULTI-ENGINE SCRAPING & EXTRACTION ENGINE
    # -------------------------------------------------------------
    def _build_search_url(self, engine, encoded_query, page):
        """Constructs the search URL and pagination parameters per search engine."""
        if engine == "Google":
            start = page * 10
            return f"https://www.google.com/search?q={encoded_query}&start={start}&hl=en&gl=uk"
        elif engine == "Bing":
            first = (page * 10) + 1
            return f"https://www.bing.com/search?q={encoded_query}&first={first}&rdr=1"
        elif engine == "DuckDuckGo":
            if page == 0:
                return f"https://duckduckgo.com/?q={encoded_query}&kl=uk-en"
            else:
                start = page * 30
                return f"https://html.duckduckgo.com/html/?q={encoded_query}&s={start}"
        elif engine == "Brave":
            return f"https://search.brave.com/search?q={encoded_query}&offset={page}&spellcheck=0"
        elif engine == "Yahoo":
            b = (page * 10) + 1
            return f"https://search.yahoo.com/search?p={encoded_query}&b={b}"
        elif engine == "Ahmia":
            return f"https://ahmia.fi/search/?q={encoded_query}"
        elif engine == "Yandex":
            return f"https://yandex.com/search/?text={encoded_query}&p={page}"
        else:
            return f"https://www.google.com/search?q={encoded_query}&start={page * 10}"

    def _parse_results_from_html(self, page_source, engine):
        """Universal multi-engine HTML DOM parser."""
        soup = BeautifulSoup(page_source, "html.parser")
        parsed_items = []

        if engine == "Google":
            # Check for 0 results page (did not match any documents)
            has_no_docs = bool(soup.find(string=lambda t: t and ("did not match any documents" in t or "cannot be recognised" in t or "No results found for" in t)))
            if has_no_docs and not soup.find("div", class_="VwiC3b"):
                # Google explicitly found 0 matching documents — do NOT parse random trending suggestion widgets!
                return []

            cards = soup.find_all("div", class_="MjjYud") or soup.find_all("div", class_="tF2Cxc") or soup.find_all("div", class_="g")
            for card in cards:
                # Discard sidebar / explore / related searches widgets
                if card.find("div", class_="kno-ecr-pt") or card.find("div", class_="s75CSd") or card.find("div", class_="EIeiLe") or card.find("div", class_="ULSxyf"):
                    continue
                h3 = card.find("h3")
                if not h3: continue
                raw_title = h3.get_text(strip=True)
                if not raw_title:
                    continue
                low_title = raw_title.lower()
                if (low_title.startswith("translate") or low_title.startswith("people also ask") 
                    or low_title.startswith("related searches") or low_title.startswith("images for") 
                    or low_title.startswith("videos for") or "explore more" in low_title 
                    or "searches related to" in low_title or "search instead for" in low_title):
                    continue
                a = h3.find_parent("a") or card.find("a", jsname="UWckNb") or card.find("a", href=True)
                if not a: continue
                href = a.get("href", "")
                if href.startswith("/"):
                    if "url=" in href:
                        parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        target_url = parsed_qs.get("q", parsed_qs.get("url", [""]))[0]
                        href = target_url if target_url.startswith("http") else urllib.parse.urljoin("https://www.google.com", href)
                    elif href.startswith("/url?q="):
                        href = urllib.parse.unquote(href.split("/url?q=")[1].split("&")[0])
                    else:
                        href = urllib.parse.urljoin("https://www.google.com", href)
                        
                # Filter out internal google links
                if "google.com/search" in href or "google.com/preferences" in href or "accounts.google.com" in href or "support.google.com" in href:
                    continue
                    
                snip_div = card.find("div", class_="VwiC3b") or card.find("div", class_="yXK7lf") or card.find("div", class_="MUxGbd") or card.find("div", style=re.compile(r"-webkit-line-clamp"))
                snippet = snip_div.get_text(strip=True) if snip_div else ""
                
                # Must have valid external URL
                if raw_title and href.startswith("http"):
                    parsed_items.append({"title": raw_title, "href": href, "snippet": snippet})

        elif engine == "Bing":
            cards = soup.find_all("li", class_="b_algo") or soup.find_all("div", class_="b_algo")
            for card in cards:
                h2 = card.find("h2")
                if not h2: continue
                raw_title = h2.get_text(strip=True)
                a = h2.find("a", href=True) or card.find("a", href=True)
                href = a["href"] if a else ""
                snip_el = card.find("div", class_="b_caption") or card.find("p") or card.find("div", class_="b_snippet")
                snippet = snip_el.get_text(strip=True) if snip_el else ""
                if raw_title and href:
                    parsed_items.append({"title": raw_title, "href": href, "snippet": snippet})

        elif engine == "DuckDuckGo":
            cards = soup.find_all("div", class_=re.compile(r"result")) or soup.find_all("article") or soup.find_all("td", class_="result-snippet")
            for card in cards:
                a = card.find("a", class_=re.compile(r"title|url|snippet")) or card.find("a", href=True)
                if not a: continue
                raw_title = a.get_text(strip=True)
                href = a.get("href", "")
                if "duckduckgo.com/l/?uddg=" in href:
                    parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    href = parsed_qs.get("uddg", [href])[0]
                snip_el = card.find("div", class_=re.compile(r"snippet")) or card.find("p") or card.find("td", class_="result-snippet")
                snippet = snip_el.get_text(strip=True) if snip_el else ""
                if raw_title and href and not href.startswith("/"):
                    parsed_items.append({"title": raw_title, "href": href, "snippet": snippet})

        elif engine == "Brave":
            cards = soup.find_all("div", class_="snippet") or soup.find_all("div", attrs={"data-type": "web"}) or soup.find_all("div", class_="card")
            for card in cards:
                t_el = card.find("div", class_="title") or card.find("span", class_="title") or card.find("h3") or card.find("a")
                if not t_el: continue
                raw_title = t_el.get_text(strip=True)
                a = card.find("a", href=True)
                href = a["href"] if a else ""
                snip_el = card.find("div", class_="snippet-description") or card.find("p", class_="snippet-description") or card.find("p")
                snippet = snip_el.get_text(strip=True) if snip_el else ""
                if raw_title and href:
                    parsed_items.append({"title": raw_title, "href": href, "snippet": snippet})

        elif engine == "Yahoo":
            cards = soup.find_all("div", class_="algo") or soup.find_all("li", class_=re.compile(r"dd|algo"))
            for card in cards:
                h3 = card.find("h3") or card.find("h4")
                if not h3: continue
                raw_title = h3.get_text(strip=True)
                a = h3.find("a", href=True) or card.find("a", href=True)
                href = a["href"] if a else ""
                if "r.search.yahoo.com" in href and "RU=" in href:
                    parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    href = urllib.parse.unquote(parsed_qs.get("RU", [href])[0])
                snip_el = card.find("div", class_="compText") or card.find("p")
                snippet = snip_el.get_text(strip=True) if snip_el else ""
                if raw_title and href:
                    parsed_items.append({"title": raw_title, "href": href, "snippet": snippet})

        elif engine == "Ahmia":
            cards = soup.find_all("li", class_="result") or soup.find_all("div", class_="result")
            for card in cards:
                h4 = card.find("h4") or card.find("h3")
                raw_title = h4.get_text(strip=True) if h4 else "Onion Result"
                a = card.find("a", href=True)
                href = a["href"] if a else ""
                snip_el = card.find("p")
                snippet = snip_el.get_text(strip=True) if snip_el else ""
                if href:
                    parsed_items.append({"title": raw_title, "href": href, "snippet": snippet})

        elif engine == "Yandex":
            cards = soup.find_all("li", class_="serp-item") or soup.find_all("div", class_="serp-item")
            for card in cards:
                h2 = card.find("h2") or card.find("h3")
                if not h2: continue
                raw_title = h2.get_text(strip=True)
                a = h2.find("a", href=True) or card.find("a", href=True)
                href = a["href"] if a else ""
                snip_el = card.find("div", class_="organic__text") or card.find("span", class_="organic__text") or card.find("p")
                snippet = snip_el.get_text(strip=True) if snip_el else ""
                if raw_title and href:
                    parsed_items.append({"title": raw_title, "href": href, "snippet": snippet})

        # Process and normalize extracted items
        normalized_leads = []
        for item in parsed_items:
            raw_title = item["title"]
            href = item["href"]
            snippet = item["snippet"]
            
            combined_text = f"{raw_title} {snippet}"
            emails = EMAIL_PATTERN.findall(combined_text)
            phones = PHONE_PATTERN.findall(combined_text)
            
            clean_title = raw_title.replace(" | LinkedIn", "").replace(" - LinkedIn", "")
            parts = [p.strip() for p in clean_title.split(" - ")]
            name = parts[0] if len(parts) > 0 else clean_title
            headline = parts[1] if len(parts) > 1 else ""
            company = parts[2] if len(parts) > 2 else ""
            
            normalized_leads.append({
                "Name": name,
                "Headline / Role": headline,
                "Organisation": company,
                "Email": ", ".join(list(dict.fromkeys(emails))) if emails else "",
                "Phone": ", ".join(list(dict.fromkeys(phones))) if phones else "",
                "URL": href,
                "Snippet": snippet
            })
            
        return normalized_leads

    def _start_search(self):
        raw_query = self.assembled_query_var.get().strip()
        query = sanitize_search_query(raw_query)
        if not query:
            messagebox.showerror("Error", "Search query is empty. Please enter criteria or choose a template.")
            return
        if query != raw_query:
            self.assembled_query_var.set(query)
            
        try:
            pages = int(self.pages_var.get())
            if pages < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Pages must be a positive integer.")
            return
            
        try:
            delay = float(self.delay_var.get())
            if delay < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Delay must be positive (e.g. 2.0).")
            return
            
        browser_mode = self.browser_mode_var.get() if hasattr(self, "browser_mode_var") else "mini"
        engine = self.engine_var.get()
        use_tor = self.tor_proxy_var.get()
        
        # Log this search query into persistent history
        self._log_search_query(engine, query)
        
        self.is_running = True
        self.stop_requested = False
        self.results_data.clear()
        
        self.search_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        
        # Switch to results tab automatically
        self.notebook.select(self.tab_results)
        
        tor_msg = " [🧅 Tor Proxy SOCKS5 Enabled]" if use_tor else ""
        mode_desc = " [Mini Corner Window]" if browser_mode == "mini" else (" [Silent Background]" if browser_mode == "headless" else " [Normal Window]")
        self.results_text.delete("1.0", tk.END)
        self.results_text.insert(tk.END, f"Target Engine: {engine}{tor_msg}{mode_desc}\nQuery: {query}\n\nInitializing browser...\n")
        self.status_var.set(f"Starting {engine} extraction...")
        
        threading.Thread(target=self._scrape_worker, args=(engine, query, pages, delay, browser_mode, use_tor), daemon=True).start()

    def _stop_search(self):
        if self.is_running:
            self.stop_requested = True
            self.status_var.set("Stopping search...")
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None

    def _scrape_worker(self, engine, query, pages, delay, browser_mode, use_tor):
        if not SELENIUM_AVAILABLE:
            self.after(0, self._scrape_with_requests, engine, query, pages, delay, use_tor)
            return

        # Setup Selenium Chrome options
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--log-level=3")
        options.add_argument("--disable-logging")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--lang=en-US,en")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        
        if use_tor:
            options.add_argument("--proxy-server=socks5://127.0.0.1:9150")
            
        if engine == "Google" and os.path.exists(AUTH_PROFILE_DIR):
            options.add_argument(f"--user-data-dir={AUTH_PROFILE_DIR}")
            
        screen_w = 1920
        screen_h = 1080
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
        except Exception:
            pass

        win_w = 340
        win_h = 240
        pos_x = max(0, screen_w - win_w - 20)
        pos_y = max(0, screen_h - win_h - 60)

        if browser_mode == "headless":
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1280,800")
        elif browser_mode == "mini":
            # Small compact corner window
            options.add_argument(f"--window-size={win_w},{win_h}")
            options.add_argument(f"--window-position={pos_x},{pos_y}")
        else:
            # Normal full window
            options.add_argument("--window-size=1150,850")
            
        try:
            self.status_var.set(f"Launching Chrome for {engine}...")
            self.driver = webdriver.Chrome(options=options)
            
            # Anti-bot detection stealth scripts
            try:
                self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        window.chrome = { runtime: {} };
                        Object.defineProperty(navigator, 'languages', {get: () => ['en-GB', 'en-US', 'en']});
                        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    """
                })
            except Exception:
                pass
                
            if browser_mode == "mini":
                try:
                    self.driver.minimize_window()
                except Exception:
                    try:
                        self.driver.set_window_size(win_w, win_h)
                        self.driver.set_window_position(pos_x, pos_y)
                    except Exception:
                        pass
        except Exception as e:
            self.after(0, self._append_log, f"Could not launch Chrome via Selenium ({e}). Falling back to direct requests...\n")
            self._scrape_with_requests(engine, query, pages, delay, use_tor)
            return
            
        encoded_query = urllib.parse.quote(query)
        
        for page in range(pages):
            if self.stop_requested or not self.driver:
                break
                
            url = self._build_search_url(engine, encoded_query, page)
            self.status_var.set(f"Fetching {engine} search page {page + 1} of {pages}...")
            
            try:
                self.driver.get(url)
            except Exception as e:
                if self.stop_requested:
                    break
                self.after(0, self._append_log, f"Navigation error on page {page + 1} ({e}).\n")
                break
                
            # Allow page to load & handle Cookie Consents
            time.sleep(2.5)
            try:
                for btn_id in ["L2AGLb", "W0wltc", "bnp_btn_accept"]:
                    try:
                        b = self.driver.find_element(By.ID, btn_id)
                        if b.is_displayed():
                            b.click()
                            time.sleep(1.5)
                            break
                    except Exception:
                        pass
                        
                for btn_text in ["Accept all", "I agree", "Tout accepter", "Alle akzeptieren", "Accept"]:
                    btns = self.driver.find_elements(By.XPATH, f"//button[contains(., '{btn_text}')]")
                    if btns and btns[0].is_displayed():
                        btns[0].click()
                        time.sleep(1.5)
                        break
            except Exception:
                pass
                
            # Safely fetch page source
            try:
                page_src = self.driver.page_source if self.driver else ""
            except Exception as e:
                self.after(0, self._append_log, f"Could not read page source: browser window was closed ({e}).\n")
                break

            # Check for CAPTCHA
            curr_url = self.driver.current_url if self.driver else ""
            is_captcha = ("/sorry/" in curr_url or "unusual traffic" in page_src or "recaptcha" in page_src.lower() or "captcha-form" in page_src)
            if is_captcha:
                self.status_var.set(f"⚠️ {engine} CAPTCHA detected. Please solve it in the popup window...")
                self.after(0, self._append_log, f"\n⚠️ {engine} CAPTCHA challenge detected!\nAuto-opened visible Chrome window. Please solve the CAPTCHA now...\n")
                
                # If running silently or minimized, bring up a visible window so user can click CAPTCHA
                if browser_mode == "headless":
                    try:
                        self.driver.quit()
                    except Exception:
                        pass
                    vis_options = Options()
                    vis_options.add_argument("--disable-blink-features=AutomationControlled")
                    vis_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
                    vis_options.add_argument("--window-size=1050,750")
                    if use_tor:
                        vis_options.add_argument("--proxy-server=socks5://127.0.0.1:9150")
                    try:
                        self.driver = webdriver.Chrome(options=vis_options)
                        self.driver.get(url)
                    except Exception as e:
                        self.after(0, self._append_log, f"Could not launch visible window for CAPTCHA: {e}\n")
                elif browser_mode == "mini":
                    try:
                        self.driver.set_window_size(1050, 750)
                        self.driver.set_window_position(100, 100)
                    except Exception:
                        pass
                
                solved = False
                for _ in range(60):
                    if self.stop_requested or not self.driver:
                        break
                    time.sleep(1)
                    try:
                        c_url = self.driver.current_url
                        c_src = self.driver.page_source
                        if "/sorry/" not in c_url and "captcha-form" not in c_src and "unusual traffic from your computer" not in c_src:
                            solved = True
                            self.after(0, self._append_log, "✅ CAPTCHA passed! Resuming extraction...\n\n")
                            # If silent or mini mode, dock/minimize the popup window immediately so it does not linger
                            if browser_mode in ["headless", "mini"]:
                                try:
                                    self.driver.minimize_window()
                                except Exception:
                                    pass
                            break
                    except Exception:
                        pass
                        
                if not solved and not self.stop_requested:
                    self.after(0, self._append_log, "⏳ CAPTCHA was not solved in time.\n💡 Tip: Try switching Search Engine to '🦆 DuckDuckGo' or '🟦 Bing' or '🦁 Brave' (which don't require CAPTCHAs).\n")
                    break
                    
                try:
                    page_src = self.driver.page_source if self.driver else ""
                except Exception:
                    pass
                
            # Parse search results with engine-specific parser
            page_leads = self._parse_results_from_html(page_src, engine)
            
            new_leads_count = 0
            for lead in page_leads:
                if not any(r["URL"] == lead["URL"] for r in self.results_data):
                    self.results_data.append(lead)
                    new_leads_count += 1
            
            self.after(0, self._append_log, f"Page {page + 1} ({engine}): Found {len(page_leads)} result cards ({new_leads_count} new unique leads added).\n")
            self.after(0, self._refresh_text_display)
            
            if page < pages - 1 and not self.stop_requested:
                time.sleep(delay)
                
        # Clean up browser
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            
        self.after(0, self._search_completed)

    def _scrape_with_requests(self, engine, query, pages, delay, use_tor):
        encoded_query = urllib.parse.quote(query)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        proxies = {"http": "socks5://127.0.0.1:9150", "https": "socks5://127.0.0.1:9150"} if use_tor else None
        
        for page in range(pages):
            if self.stop_requested:
                break
            url = self._build_search_url(engine, encoded_query, page)
            try:
                resp = requests.get(url, headers=headers, proxies=proxies, timeout=15)
                if resp.status_code != 200:
                    self.after(0, self._append_log, f"{engine} returned status {resp.status_code}. Keep 'Show Chrome Window' checked for best results.\n")
                    break
                    
                page_leads = self._parse_results_from_html(resp.text, engine)
                for lead in page_leads:
                    if not any(d["URL"] == lead["URL"] for d in self.results_data):
                        self.results_data.append(lead)
                        
                self.after(0, self._refresh_text_display)
            except Exception as e:
                self.after(0, self._append_log, f"Error: {e}\n")
                break
            if page < pages - 1:
                time.sleep(delay)
                
        self.after(0, self._search_completed)

    def _append_log(self, text):
        self.results_text.insert(tk.END, text)
        self.results_text.see(tk.END)

    def _search_completed(self):
        self.is_running = False
        self.search_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        
        count = len(self.results_data)
        email_count = sum(1 for r in self.results_data if r.get("Email"))
        self._refresh_text_display()
        self.status_var.set(f"Completed! Found {count} lead(s) ({email_count} with email addresses).")
        self.stat_leads_var.set(f"{count} leads | {email_count} emails")
        
        if count == 0:
            messagebox.showinfo("Search Complete", f"No results were found on {self.engine_var.get()}.\n\nTip: Leave 'Show Chrome Window' checked to solve any CAPTCHA if prompted.")
        else:
            messagebox.showinfo("Search Complete", f"Extraction completed on {self.engine_var.get()}!\n\nFound: {count} leads\nExtracted Emails: {email_count}\n\nResults are ready in the text box for copy/export.")

    def _get_filtered_data(self):
        filt = self.filter_var.get().lower().strip()
        if not filt:
            return self.results_data
            
        filtered = []
        for r in self.results_data:
            match = (
                filt in r["Name"].lower() or
                filt in r["Headline / Role"].lower() or
                filt in r["Organisation"].lower() or
                filt in r["Email"].lower() or
                filt in r["URL"].lower() or
                filt in r["Snippet"].lower()
            )
            if match:
                filtered.append(r)
        return filtered

    def _refresh_text_display(self):
        fmt = self.format_var.get()
        data = self._get_filtered_data()
        count = len(data)
        total = len(self.results_data)
        
        email_count = sum(1 for r in self.results_data if r.get("Email"))
        self.count_badge.configure(text=f"{count} / {total} leads ({email_count} emails)")
        self.stat_leads_var.set(f"{total} leads | {email_count} emails")
        
        self.results_text.delete("1.0", tk.END)
        
        if not data:
            if self.is_running:
                self.results_text.insert(tk.END, f"Searching {self.engine_var.get()}... please wait.\n")
            else:
                self.results_text.insert(tk.END, f"No results match your criteria.\nConfigure search criteria in Tab 1 and click 'Search & Extract Leads'.\n")
            return
            
        if fmt == "formatted":
            lines = []
            for idx, item in enumerate(data, 1):
                lines.append(f"[{idx}] {item['Name']}")
                if item['Headline / Role']:
                    lines.append(f"    Role:    {item['Headline / Role']}")
                if item['Organisation']:
                    lines.append(f"    Org:     {item['Organisation']}")
                if item['Email']:
                    lines.append(f"    ✉ Email: {item['Email']}")
                if item['Phone']:
                    lines.append(f"    📞 Phone: {item['Phone']}")
                lines.append(f"    🔗 URL:   {item['URL']}")
                if item['Snippet']:
                    lines.append(f"    📝 Snip:  {item['Snippet']}")
                lines.append("-" * 75)
            self.results_text.insert(tk.END, "\n".join(lines))
            
        elif fmt == "tsv":
            # Tab separated for Excel / Google Sheets
            headers = ["Name", "Headline / Role", "Organisation", "Email", "Phone", "URL", "Snippet Context"]
            lines = ["\t".join(headers)]
            for item in data:
                row = [
                    item["Name"].replace("\t", " "),
                    item["Headline / Role"].replace("\t", " "),
                    item["Organisation"].replace("\t", " "),
                    item["Email"].replace("\t", " "),
                    item["Phone"].replace("\t", " "),
                    item["URL"].replace("\t", " "),
                    item["Snippet"].replace("\t", " ").replace("\n", " ")
                ]
                lines.append("\t".join(row))
            self.results_text.insert(tk.END, "\n".join(lines))
            
        elif fmt == "csv":
            output = io.StringIO()
            fieldnames = ["Name", "Headline / Role", "Organisation", "Email", "Phone", "URL", "Snippet Context"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for item in data:
                writer.writerow({
                    "Name": item["Name"],
                    "Headline / Role": item["Headline / Role"],
                    "Organisation": item["Organisation"],
                    "Email": item["Email"],
                    "Phone": item["Phone"],
                    "URL": item["URL"],
                    "Snippet Context": item["Snippet"]
                })
            self.results_text.insert(tk.END, output.getvalue())
            
        elif fmt == "emails":
            all_emails = []
            for item in data:
                if item["Email"]:
                    for e in item["Email"].split(","):
                        if e.strip() and e.strip() not in all_emails:
                            all_emails.append(e.strip())
            if all_emails:
                self.results_text.insert(tk.END, "\n".join(all_emails))
            else:
                self.results_text.insert(tk.END, "No email addresses were found in the current result snippets.\n\nTip: Check 'Public Emails' or add a custom email domain in Tab 1.")
                
        elif fmt == "urls":
            urls = [item["URL"] for item in data]
            self.results_text.insert(tk.END, "\n".join(urls))

    def _copy_to_clipboard(self):
        text = self.results_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Clipboard", "The text box is empty.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        count = len(self._get_filtered_data())
        self.status_var.set(f"✅ Copied {count} result(s) to clipboard!")
        messagebox.showinfo("Copied!", f"Copied {count} results to clipboard!\nYou can paste (Ctrl+V) into Excel, Word, or any document.")

    def _copy_emails_only(self):
        all_emails = []
        for item in self.results_data:
            if item.get("Email"):
                for e in item["Email"].split(","):
                    if e.strip() and e.strip() not in all_emails:
                        all_emails.append(e.strip())
        if not all_emails:
            messagebox.showinfo("Emails", "No email addresses have been extracted yet.")
            return
        text = "\n".join(all_emails)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set(f"✅ Copied {len(all_emails)} email(s) to clipboard!")
        messagebox.showinfo("Copied!", f"Copied {len(all_emails)} extracted email addresses to clipboard!")

    def _save_to_csv(self):
        if not self.results_data:
            messagebox.showwarning("Save CSV", "No leads to save yet. Run a search first.")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="extracted_leads.csv"
        )
        if not filepath:
            return
            
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                fieldnames = ["Name", "Headline / Role", "Organisation", "Email", "Phone", "URL", "Snippet Context"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for item in self.results_data:
                    writer.writerow({
                        "Name": item.get("Name", ""),
                        "Headline / Role": item.get("Headline / Role", ""),
                        "Organisation": item.get("Organisation", ""),
                        "Email": item.get("Email", ""),
                        "Phone": item.get("Phone", ""),
                        "URL": item.get("URL", ""),
                        "Snippet Context": item.get("Snippet", "")
                    })
            self.status_var.set(f"Saved to {os.path.basename(filepath)}")
            messagebox.showinfo("Saved", f"Successfully exported {len(self.results_data)} leads to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")

    def _clear_results(self):
        if self.is_running:
            messagebox.showwarning("Busy", "Cannot clear while search is active.")
            return
        self.results_data.clear()
        self.results_text.delete("1.0", tk.END)
        self.count_badge.configure(text="0 leads")
        self.stat_leads_var.set("0 leads | 0 emails")
        self.status_var.set("Results cleared.")

    def _on_closing(self):
        self._stop_search()
        self.destroy()


if __name__ == "__main__":
    app = GoogleLeadScraperSuite()
    app.mainloop()
