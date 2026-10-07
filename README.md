# ⚡ Multi-Engine Lead Extractor & Advanced Google Dork Scraping Suite

A high-performance Python & Tkinter desktop suite for precision OSINT, advanced Google Dorking, multi-engine web scraping, automated contact extraction, corporate email enrichment, and zero-spam deliverability verification.

> 📖 **Comprehensive Walkthrough:** For complete step-by-step instructions, visual workflows, and feature deep-dives, consult the [Beginner's User Guide & Walkthrough (USER_GUIDE.md)](USER_GUIDE.md).

---

## 🌟 Overview & Key Features

### 🌐 1. Multi-Engine Search & Scraping
- **Supported Engines**: Google, Bing, DuckDuckGo, Brave Search, Yahoo, Yandex, and Ahmia (Tor darknet).
- **Anti-Bot & Anti-CAPTCHA Architecture**:
  - **Authenticated Google Session Profile**: 1-click Google account login that saves session cookies locally, bypassing robotic reCAPTCHA blocks.
  - **Smart CAPTCHA Detection**: Automatically pops up a visible browser window only when a verification challenge is detected, then resumes silently once completed.
  - **Browser Visibility Modes**: Silent Headless (default), Minimized Corner Widget, or Full Window.
  - **Tor SOCKS5 Proxy Routing**: 1-click routing through Tor (`socks5://127.0.0.1:9150` or `9050`) for anonymous queries.
  - **Configurable Delays**: Per-page scraping rate-limit prevention and custom timeouts.

### 🛠️ 2. Dual-Strategy Query Builder & Search Templates
- **Sub-Tab 1: Targeted Site & Profile Search (`site:`)**:
  - Laser-targeted dork generator for platforms like LinkedIn (`site:linkedin.com/in/`), GitHub, StackOverflow, corporate domains, and government registries.
  - Multi-parameter filters: Organization/Company, Job Titles (with automatic boolean `OR` formatting), Geographic Locations, Negative Keyword Exclusions (`-`), Filetypes (`filetype:pdf`, `filetype:xlsx`), and Public Contact Dorks (hunting `@gmail`, `@outlook`, and phone numbers).
- **Sub-Tab 2: Generalized Multi-Group Boolean Query Builder**:
  - Constructs advanced multi-group queries across the open web to discover commercial facilities, regional hubs, corporate headquarters, and multi-site operations.
  - Combines Industry Keywords, Operational Scale Triggers (*"multiple sites"*, *"head office"*, *"nationwide"*), Geographic Filters, and Negative Noise Exclusions (*-jobs -careers -directory -news*).
- **Pre-Configured Dork Recipes**: Built-in 1-click templates for B2B Lead Generation, Cybersecurity OSINT, Developer Code & Error Hunting, and Public Registries.

### ⚡ 3. Automated Lead Parsing & Email Enrichment
- **Entity Parsing**: Automatically parses raw search result snippets to extract First Name, Last Name, Full Name, Job Role, and Company / Organisation.
- **Domain Resolution Engine**: Maps company and public sector names to verified corporate domain names via built-in and customizable sector dictionaries (`data/domains.json`).
- **Corporate Pattern Synthesizer**: Generates standard email permutations (`first.last@domain`, `flast@domain`, `firstlast@domain`, `first_last@domain`, `last.first@domain`, etc.).
- **DNS MX Mailbox Verification**: Resolves live DNS MX records in real-time via `dnspython` to verify active mail servers (Microsoft 365, Google Workspace, Mimecast, Proofpoint).
- **Deliverability Status Badges**:
  - `🟢 Valid (MX Verified)`: Mail server active and verified.
  - `🟡 Risky`: Catch-all domain or unconfirmed mailbox.
  - `⚪ Not Found`: Missing domain mapping.
  - `🔴 Invalid (No MX)`: Dead or non-existent mail domain.
- **Modular API Fallbacks**: Works 100% free with the built-in DNS MX synthesizer or integrates optionally with external enrichment APIs (Hunter.io, Apollo.io, Snov.io).

### 🛡️ 4. Bulk Email & CSV Deliverability Verifier (DNS MX & SMTP Handshake)
- **Flexible Input Methods**:
  - **Option A (CSV File Import)**: Upload any external `.csv` dataset, auto-detect the email column, and verify hundreds of addresses in bulk.
  - **Option B (Multi-Line Manual Paste)**: Paste raw emails, comma-separated lists, or `Name, email@domain.com` formatted lines.
- **Zero-Spam SMTP Handshake**: Connects directly to the recipient's mail exchange server on port 25 (`HELO` -> `MAIL FROM` -> `RCPT TO` -> `250 OK / 550 Mailbox Not Found`) without ever sending test messages.
- **⚡ Auto-Waterfall Permutation Discovery**: Automatically cycles through all corporate email formulas on `550 User Not Found` until finding the winning `🟢 250 OK` deliverable format, or flags as `🔴 All Formats Failed`.
- **🔄 Reformat & Retry Studio**: Interactive modal window to reformat undeliverable addresses and test live deliverability on the fly.
- **Preserves 100% Original CSV Data**: All original columns and metadata from imported spreadsheets are preserved with verification results appended (`Verification_Status`, `Deliverability_Badge`, `Primary_MX_Host`, `SMTP_Response_Code`, `Response_Time_MS`).

### 📥 5. Direct Open Data & Public Register Downloader
- **Bulk Dataset Ingestion**: Downloads complete national registers and open data archives (ZIP, CSV, XLSX) directly with zero search engine rate limits, blocks, or CAPTCHAs.
- **Custom URL & Local Importer**: Ingest any custom registry URL or local file from disk.
- **1-Click Bridges**: Send loaded open data records directly to the **Leads Table (Tab 2)** for email enrichment or to the **Verifier (Tab 3)** for mail server testing.

### 🌐 6. Embedded Background REST API Server
- Starts a lightweight local background REST API on `http://127.0.0.1:8765`:
  - `POST /api/enrich`: Programmatic contact enrichment endpoint.
  - `GET /api/health`: Health and status monitoring endpoint.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python**: 3.8 or higher
- **Google Chrome**: Installed on the host system (for Selenium web scraping)

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/cankalsoftware/Google-Scrape.git
cd Google-Scrape
pip install -r requirements.txt
```

### 3. Launch the Application
```bash
python scraper_gui.py
```

---

## 🛠️ General Usage Workflow

```mermaid
graph LR
    A["1. Build Query (Tab 1)"] --> B["2. Scrape & Extract"]
    B --> C["3. Batch Enrich (Tab 2)"]
    C --> D["4. Verify Mailboxes (Tab 3)"]
    D --> E["5. Export Enriched CSV"]
```

### 1. Build Query & Scrape Leads
1. In **Tab 1 (Query Builder & Presets)**, select your target search engine (Google, Bing, Brave, DuckDuckGo).
2. Choose your query strategy:
   - **Targeted Search**: Enter a target site (e.g. `site:linkedin.com/in/`), industry keyword, target job titles, and location.
   - **Generalized Boolean Search**: Combine industry terms, operational footprint scale keywords, and negative exclusions.
3. Set your desired **Pages to Scrape** and **Delay (sec)**.
4. Click **`🚀 Search & Extract Leads`**.

### 2. Enrich Leads & Synthesize Emails
1. Switch to **Tab 2 (Extracted Results & Text Box)**.
2. Review extracted contacts in the **Interactive Table** or switch views (Structured Cards, TSV, CSV, Emails Only).
3. Click **`⚡ Batch Enrich All`** to automatically resolve corporate domains, generate email address formulas, and verify DNS MX deliverability.
4. Click **`💾 Export Enriched CSV`** to save your clean dataset.

### 3. Bulk Verify External Email Lists
1. Switch to **Tab 3 (Email & CSV Verifier)**.
2. Choose **Option A (Import CSV File)** to load an external spreadsheet, or **Option B (Manual Paste)** to paste emails.
3. Click **`🚀 Start MX/SMTP Verification`** to execute live DNS MX checks and zero-spam SMTP handshakes.
4. Click **`💾 Export Verified CSV`** to save the verified dataset.

---

## 🌐 Local REST API Endpoint

The suite provides an embedded background REST API server running on port `8765`:

### Health Check
```bash
curl -X GET http://127.0.0.1:8765/api/health
```

### Contact Enrichment
```bash
curl -X POST http://127.0.0.1:8765/api/enrich \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Jane Doe",
    "headline": "Chief Technology Officer",
    "organisation": "Acme Global Technologies"
  }'
```

**Response:**
```json
{
  "status": "success",
  "first_name": "Jane",
  "last_name": "Doe",
  "domain": "acmeglobal.com",
  "email": "jane.doe@acmeglobal.com",
  "deliverability": "Valid (MX Verified)",
  "mx_host": "mail.protection.outlook.com"
}
```

---

## 🏗️ Architecture & Extensibility

```
Google Scrape/
├── scraper_gui.py             # Main Tkinter Desktop Application & UI Controller
├── data_loader.py             # JSON Configuration Loader & Fallback Manager
├── storage.py                 # SQLite Database Manager & Persistent MX Cache
│
├── data/                      # Configuration & Reference Dictionaries (JSON)
│   ├── domains.json           # Sector & company domain mappings
│   ├── presets.json           # Targeted profile & generalized search templates
│   ├── dorks_cheatsheet.json  # Search operators, dev recipes & OSINT templates
│   └── registry_sources.json  # Open data download sources & registry URLs
│
└── db/                        # Transactional State Persistence (SQLite)
    └── scraper_storage.db     # Persistent DNS MX Cache, Query History & Leads DB
```

### Customizing Configuration Files (`data/`)
- **`data/domains.json`**: Add new industry sectors or company name-to-domain mappings without editing Python code.
- **`data/presets.json`**: Add reusable query templates for specific industries or search patterns.
- **`data/dorks_cheatsheet.json`**: Expand the built-in search operator library and 1-click recipes.
- **`data/registry_sources.json`**: Save custom open data download links and register sources.

---

## 📄 License
MIT License. Free for personal, academic, and commercial use.
