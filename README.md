# ⚡ Multi-Engine Lead & Advanced Dork Extractor Suite

A modern Python & Tkinter desktop application for precision OSINT, advanced Google Dorking, multi-engine scraping, contact lead generation, automated email enrichment, and deliverability verification.

> 📖 **Looking for a beginner walkthrough?** Read the [Beginner's User Guide & Walkthrough (USER_GUIDE.md)](file:///c:/Users/uyko7/Documents/VSCode/Google%20Scrape/USER_GUIDE.md) for step-by-step instructions.

---

## 🌟 Key Features

- **⚡ Automated Email Enrichment & Deliverability Verification**:
  - **Entity Parsing**: Automatically extracts clean First Name, Surname, Job Role, and Organisation from LinkedIn snippets.
  - **UK Fire & Rescue Services Domain Normalizer**: Comprehensive built-in registry matching all 50+ UK Fire Services (London Fire Brigade, GMFRS, WMFS, HIWFRS, Scottish Fire, etc.) to official `.gov.uk`, `.org.uk`, and `.net` domains.
  - **Multi-Industry Support**: Extensible registry supporting NHS Trusts (`.nhs.uk`), Local Councils (`.gov.uk`), Police Constabularies (`.police.uk`), and custom corporate domains.
  - **DNS MX Mailbox Verification**: Resolves live DNS MX records via `dnspython` to verify active Microsoft 365, Mimecast, and government secure mail gateways before displaying emails.
  - **Deliverability Status Badges**: `🟢 Valid (MX Verified)`, `🟡 Risky`, `⚪ Not Found`, `🔴 Invalid (No MX)`.
  - **Modular API Integrations**: Works 100% free with the built-in MX pattern synthesizer or integrates seamlessly with external APIs (Hunter.io, Apollo.io, Snov.io).
  - **Embedded REST API Server**: Built-in background HTTP server exposing `POST /api/enrich` and `GET /api/health` on `http://127.0.0.1:8765`.
- **🛡️ Email & CSV Deliverability Verifier (DNS MX & SMTP Handshake)**:
  - **Option A (CSV File Import)**: Upload any external `.csv` (e.g., `Chief_Fire_Officers.csv`), auto-detect/select the email column, and verify hundreds of addresses in bulk.
  - **Option B (Multi-Line Manual Paste)**: Multi-line text field supporting raw emails, comma-separated lists, and `Name, email@domain.com` formatted strings.
  - **Full SMTP Handshake**: Performs live `HELO` -> `MAIL FROM` -> `RCPT TO` -> `250 OK / 550 Mailbox Not Found` verification without sending actual messages.
  - **Catch-All Detection & Greylist Handling**: Optional probe to identify catch-all servers.
  - **Preserves Original CSV Data on Export**: When exporting verified records to CSV, all original columns and metadata from your imported file are 100% preserved with new verification status columns appended (`Verification_Status`, `Deliverability_Badge`, `Primary_MX_Host`, `SMTP_Response_Code`, `Response_Time_MS`).
- **📋 Interactive Lead Table & Enriched CSV Exports**:
  - Dedicated interactive multi-column table (`ttk.Treeview`) with live sorting, color-coded badges, and 1-click **⚡ Batch Enrich** or **⚡ Enrich Selected** contact actions.
  - Export full enriched dataset with **💾 Export Enriched CSV** (First Name, Surname, Job Title, Organisation, Enriched Email, Deliverability Status, Domain, MX Server, Phone, URL).
- **🌐 Multi-Engine Search Support**:
  - Google, Bing, DuckDuckGo, Brave Search, Yahoo, Yandex, and Ahmia (Tor/Onion web).
- **🧅 Tor SOCKS5 Proxy Routing**:
  - 1-click option to route queries through Tor (`socks5://127.0.0.1:9150` or `9050`) for anonymous searches.
- **🛠️ Interactive Query Builder**:
  - Live query generator with support for manual `site:` restrictions, industry keywords, boolean `OR` groups, job titles, location filters, email & phone hunting dorks, and filetype filters.
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
1. In **Tab 1 (Query Builder & Presets)**, choose your search engine (Google, Bing, Brave, DuckDuckGo) or load a pre-configured template (e.g., *Fire & Rescue IT Leaders (UK)*).
2. Click **🚀 Search & Extract Leads**.

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

Alternatively, select **`🦆 DuckDuckGo`** or **`🟦 Bing`** from the Search Engine dropdown, which index web results without CAPTCHA restrictions.

---

## 📄 License
MIT License. Free for personal and commercial use.

