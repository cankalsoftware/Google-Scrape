# ⚡ Multi-Engine Lead & Advanced Dork Extractor Suite

A modern Python & Tkinter desktop application for precision OSINT, advanced Google Dorking, multi-engine scraping, contact lead generation, automated email enrichment, and deliverability verification.

> 📖 **Looking for a beginner walkthrough?** Read the [Beginner's User Guide & Walkthrough (USER_GUIDE.md)](file:///c:/Users/uyko7/Documents/VSCode/Google%20Scrape/USER_GUIDE.md) for step-by-step instructions.

---

## 🌟 Key Features

- **⚡ Automated Email Enrichment & Deliverability Verification**:
  - **Entity Parsing**: Automatically extracts clean First Name, Surname, Job Role, and Organisation from LinkedIn snippets.
  - **UK Public Sector & Environmental Domain Normalizers**: Comprehensive built-in registries matching:
    - **UK Fire & Rescue Services**: 50+ services (London Fire Brigade, GMFRS, WMFS, HIWFRS, Scottish Fire, etc.) to `.gov.uk`, `.org.uk`, and `.net`.
    - **UK Environmental Regulators & Waste Registers**: Environment Agency (`environment.data.gov.uk`), Scottish Environment Protection Agency (`sepa.org.uk`), and Natural Resources Wales / Cyfoeth Naturiol Cymru (`naturalresources.wales`).
    - **Public Sector & Healthcare**: NHS Trusts (`.nhs.uk`), Local Councils (`.gov.uk`), and Police Constabularies (`.police.uk`).
  - **DNS MX Mailbox Verification**: Resolves live DNS MX records via `dnspython` to verify active Microsoft 365, Mimecast, and government secure mail gateways before displaying emails.
  - **Deliverability Status Badges**: `🟢 Valid (MX Verified)`, `🟡 Risky`, `⚪ Not Found`, `🔴 Invalid (No MX)`.
  - **Modular API Integrations**: Works 100% free with the built-in MX pattern synthesizer or integrates seamlessly with external APIs (Hunter.io, Apollo.io, Snov.io).
  - **Embedded REST API Server**: Built-in background HTTP server exposing `POST /api/enrich` and `GET /api/health` on `http://127.0.0.1:8765`.
- **🛡️ Email & CSV Deliverability Verifier (DNS MX & SMTP Handshake)**:
  - **Option A (CSV File Import)**: Upload any external `.csv` (e.g., `Chief_Fire_Officers.csv`), auto-detect/select the email column, and verify hundreds of addresses in bulk.
  - **Option B (Multi-Line Manual Paste)**: Multi-line text field supporting raw emails, comma-separated lists, and `Name, email@domain.com` formatted strings.
  - **Full SMTP Handshake**: Performs live `HELO` -> `MAIL FROM` -> `RCPT TO` -> `250 OK / 550 Mailbox Not Found` verification without sending actual messages.
  - **⚡ Auto-Waterfall Permutation Discovery**: Automatically cycles through all corporate email formulas (`first.last`, `firstlast`, `flast`, `first_last`, `last.first`, `lastf`, `first`) when an address returns 550. Automatically updates to the winning `🟢 250 OK` deliverable format, or flags as `🔴 All Formats Failed` in red.
  - **🔄 Email Pattern Reformatting & Retry Studio**: 1-click modal window to convert undeliverable addresses (e.g. `ali.cankal` ➔ `alicankal`, `acankal`, `ali_cankal`, `cankal.ali`), test live MX/SMTP deliverability on the fly, and apply deliverable emails back to your dataset.
  - **Preserves Original CSV Data on Export**: When exporting verified records to CSV, all original columns and metadata from your imported file are 100% preserved with new verification status columns appended (`Verification_Status`, `Deliverability_Badge`, `Primary_MX_Host`, `SMTP_Response_Code`, `Response_Time_MS`).
- **📋 Interactive Lead Table & Enriched CSV Exports**:
  - Dedicated interactive multi-column table (`ttk.Treeview`) with live sorting, color-coded badges, and 1-click **⚡ Batch Enrich** or **⚡ Enrich Selected** contact actions.
  - Export full enriched dataset with **💾 Export Enriched CSV** (First Name, Surname, Job Title, Organisation, Enriched Email, Deliverability Status, Domain, MX Server, Phone, URL).
- **🌐 Multi-Engine Search Support**:
  - Google, Bing, DuckDuckGo, Brave Search, Yahoo, Yandex, and Ahmia (Tor/Onion web).
- **🧅 Tor SOCKS5 Proxy Routing**:
  - 1-click option to route queries through Tor (`socks5://127.0.0.1:9150` or `9050`) for anonymous searches.
- **🛠️ Dual-Strategy Query Builder & Ready Templates**:
  - **Sub-Tab 1 (Targeted Site & Profile Search)**: Live query generator for precision dorking with `site:` restrictions (LinkedIn, Environment Agency Public Register, SEPA, NRW, government portals), job titles, location filters, email & phone hunting dorks, and filetype filters.
  - **Sub-Tab 2 (Generalized Industry & Facility Search)**: Multi-group boolean query builder for discovering commercial facilities, distribution networks, fleet depots, and multi-site operations across the open web with 1-click facility templates, operational scale filters, regional boundary groups, and negative exclusions.
  - **Pre-Populated UK Environmental Register Searches**:
    1. *EA England Waste Permitting & Operations*: `site:environment.data.gov.uk/public-register/ ("Environmental Permitting Regulations – Waste Operations" OR "Materials recovery" OR "Waste transfer") -council -civic -household -tip -hwrc`
    2. *EA England Registered Carriers & Brokers*: `site:environment.data.gov.uk/public-register/ "Register of Waste Carriers, Brokers and Dealers" ("Carrier and Broker" OR "Dealer") ("Limited" OR "Ltd" OR "PLC") -council -individual`
    3. *SEPA Scotland Waste Authorisations*: `site:sepa.org.uk ("Register of Waste Carriers" OR "authorisations" OR "waste transfer" OR "materials recovery") ("Limited" OR "Ltd" OR "PLC") -council`
    4. *NRW Wales Waste Permitting*: `site:naturalresources.wales ("waste permitting" OR "waste carriers, brokers and dealers" OR "waste transfer") ("Limited" OR "Ltd" OR "PLC") -council -cyngor`
    5. *Combined UK Regulators*: `(site:environment.data.gov.uk/public-register/ OR site:sepa.org.uk OR site:naturalresources.wales) ("waste operations" OR "materials recovery" OR "waste transfer station" OR "waste carrier") ("Limited" OR "Ltd" OR "PLC") -council -cyngor -civic -household -tip -hwrc`
- **📥 Direct Open Data & Public Register Downloader (No Web Scraping Needed)**:
  - **Direct Bulk Dataset Downloads**: Pulls complete national registers directly via open data links and archives (ZIP/CSV) with zero CAPTCHAs, search engine rate limits, or blocks.
  - **Built-in Official Portals & Registries**:
    - *Environment Agency (England)*: Permitted Waste Operations dataset & Registered Waste Carriers/Brokers directory.
    - *NFCC (National Fire Chiefs Council)*: UK Chief Fire Officers Directory parser (extracts names, leadership titles, and fire services).
    - *SEPA (Scotland)*: Scottish Waste Carriers Register & Public Authorisations portal.
    - *Natural Resources Wales*: Welsh environmental permits, exemptions, and carrier registers.
    - *data.gov.uk*: Central UK open government data portal.
  - **Custom Link Fetcher & Local File Importer**: Paste ANY custom URL (direct `.csv`, `.zip`, `.xlsx`, or web directory page) or load local files from disk.
  - **Persistent Saved Sources (`registry_sources.json`)**: Save and manage custom registry URLs permanently in a convenient dropdown.
  - **1-Click Bridges**: Instantly send loaded registry records to **Tab 2 (Leads Table)** for automated domain resolution and email synthesis, or to **Tab 3 (Verifier)** for MX/SMTP mail server checks.
- **📖 Comprehensive Search Operators Cheat Sheet**:
  - Integrated cheatsheet with 1-click templates for developers, cybersecurity researchers, and lead generators.
  - Hover tooltips and `(?)` help badges explaining every search operator.
- **🔑 Google Authenticated Session Profile**:
  - 1-click Google login tool that stores trusted cookies and user credentials locally, permanently bypassing robotic reCAPTCHA blocks.
- **👻 Multi-Mode Browser Visibility**:
  - **Silent Headless Mode (Default)**: Runs 100% invisibly in the background.
  - **Minimized Corner Window**: Keeps the browser parked as a tiny widget in the bottom corner of your screen.
  - **Normal Window**: Opens full-size browser for manual inspection or complex CAPTCHA solving.
  - **Smart CAPTCHA Auto-Popup**: Automatically opens a visible window only when a CAPTCHA challenge is detected and auto-minimizes once completed.
- **📜 Query History Log**:
  - Automatically logs every query with timestamps and search engines to `search_history.log` with 1-click query recall.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.8+
- Google Chrome installed

### 2. Installation
Clone this repository and install the dependencies:
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

## 🛠️ Usage Guide

### 1. Build Your Query & Search
1. In **Tab 1 (Query Builder & Presets)**, choose your search engine (Google, Bing, Brave, DuckDuckGo) or load a pre-configured template.
2. Select your search strategy sub-tab:
   - **🎯 Tab 1 (Targeted Site & Profile Search)**: Restrict to specific sites like LinkedIn with job roles and location filters.
   - **🌐 Tab 2 (Generalized Industry & Facility Search)**: Build multi-group boolean searches combining facility types (e.g. *Materials Recovery Facilities*, *Distribution Hubs*), operational footprint (*multiple sites*, *depots across*), geographic scope (*UK*, *England*, *Scotland*, *Wales*), and negative exclusions (*-council -civic -household -tip -hwrc -.gov.uk*). Click **`⭐ Load Waste & Facility Example`** for 1-click loading.
3. Click **🚀 Search & Extract Leads**.

### 2. Enrich Leads & Verify Emails
1. Switch to **Tab 2 (Extracted Results & Text Box)**.
2. Review the scraped contacts in the **📋 Interactive Table**.
3. Click **`⚡ Batch Enrich Leads`** to resolve official domains, generate corporate email addresses (`first.last@domain`), and check DNS MX server deliverability.
4. Click **`💾 Export Enriched CSV`** to export a clean spreadsheet ready for CRM or outreach with columns:
   - `First Name`, `Last Name`, `Full Name`, `Job Title / Role`, `Organisation`, `Resolved Domain`, `Enriched Email`, `Deliverability Status`, `MX Server Host`, `Phone`, `LinkedIn Profile URL`.

### 3. Verify Emails via CSV Upload or Manual Paste
1. Switch to **Tab 3 (Email & CSV Verifier)**.
2. Select your input method:
   - **Option A (CSV File)**: Browse and select any `.csv` (e.g., `Chief_Fire_Officers.csv`). The app auto-detects your email column. Click **`⚡ Load CSV into Verifier`**.
   - **Option B (Manual Paste)**: Paste one or multiple lines containing email addresses or `Name, email@domain.com` lines, then click **`⚡ Load Pasted Emails into Verifier`**.
3. Click **`🚀 Start MX/SMTP Verification`** to perform live DNS MX and SMTP Handshake verification (`HELO` -> `MAIL FROM` -> `RCPT TO`).
4. Click **`💾 Export Verified CSV`** to save your verified file (all original columns from your CSV are 100% preserved with added verification columns).

---

## 🌐 Local REST API Endpoint

The application starts an embedded background REST API server on port `8765`:

- **Health Check**: `GET http://127.0.0.1:8765/api/health`
- **Enrich Contact**: `POST http://127.0.0.1:8765/api/enrich`
  ```bash
  curl -X POST http://127.0.0.1:8765/api/enrich \
    -H "Content-Type: application/json" \
    -d '{
      "full_name": "John Smith",
      "headline": "Head of IT",
      "organisation": "London Fire Brigade"
    }'
  ```

---

## 🔒 Google Login & Anti-Bot Protection

If you want to run heavy Google Dork queries without CAPTCHAs:
1. Click **`🔑 Log in to Google`** in Tab 1.
2. Log into your Google Account in the opened Chrome window and close it when finished.
3. The scraper will now automatically reuse your authenticated Google session.

---

## 🏗️ Modular Architecture & Hybrid Storage Model

The suite follows a **Hybrid Storage Model** separating UI presentation from dynamic configurations and transactional database state:

```
Google Scrape/
├── scraper_gui.py             # 🖥️ Main Tkinter Application & UI Controller
├── data_loader.py             # 🔄 Resilient JSON Configuration Loader & Fallback Manager
├── storage.py                 # 🗄️ SQLite Database Manager & Persistent MX Cache
│
├── data/                      # 📁 Configuration & Reference Data (JSON)
│   ├── domains.json           # UK Public Sector, Environment & Transport domain dictionaries
│   ├── presets.json           # Targeted profile and generalized multi-group search templates
│   ├── dorks_cheatsheet.json  # Search operators, dev dorks, and OSINT security recipes
│   └── registry_sources.json  # Pre-configured official open data and public register links
│
└── db/                        # 📁 Transactional State Storage (SQLite)
    └── scraper_storage.db     # Persistent DNS MX Cache, Search Query History & Leads DB
```

### 1. JSON Configuration Files (`data/`)
- **`data/domains.json`**: Contains structured domain mappings across sectors:
  - `fire_services`: 50+ UK Fire & Rescue Services (`.gov.uk`, `.org.uk`, `.net`).
  - `environment`: Environment Agency, SEPA, and Natural Resources Wales registers.
  - `transport_highways`: National Highways, Highways England, TfL, Network Rail, DVSA, DVLA.
  - `nhs`: NHS England, trusts, and healthcare authorities (`.nhs.uk`).
  - `councils`: City, borough, and county councils (`.gov.uk`).
  - `police`: UK police constabularies (`.police.uk`).
  - *Customization*: Add any company or sector domain directly to `data/domains.json` without modifying Python source code.
- **`data/presets.json`**: Pre-configured targeted and generalized search templates. Adding a new industry search to JSON automatically makes it available across all UI dropdowns.
- **`data/dorks_cheatsheet.json`**: Full reference of Google Dork operators, developer debugging recipes, and security patterns.
- **`data/registry_sources.json`**: Direct open data download portals for Tab 4.

### 2. SQLite Database Persistence (`db/scraper_storage.db`)
- **Persistent DNS MX Cache (`mx_cache`)**:
  - Automatically caches DNS MX lookups and Catch-All server tests across app restarts.
  - Subsequent verification runs on known domains execute at **0ms in-memory/disk speed** with zero network DNS round-trips.
- **Search Query History (`search_history`)**:
  - High-performance, timestamped audit log of all executed searches, engine types, and collected lead counts.
  - 1-click recall into Query Builder.
- **Saved Leads Table (`saved_leads`)**:
  - ACID-safe persistent backup for scraped contacts and enriched corporate email records.

---

## 📄 License
MIT License. Free for personal and commercial use.

