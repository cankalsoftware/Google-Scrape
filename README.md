# ⚡ Multi-Engine Lead & Advanced Dork Extractor Suite

A modern Python & Tkinter desktop application for precision OSINT, advanced Google Dorking, multi-engine scraping, contact lead generation, and automated data extraction.

---

## 🌟 Key Features

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
- **📋 Lead Extraction & Multi-Format Exports**:
  - Extracts Name, Job Title / Role, Organisation, Email addresses, Phone numbers, and Source URLs.
  - Instant live search/filtering in results.
  - Export to **Structured Cards**, **Excel TSV (Tab-Separated)**, **CSV**, **Emails Only**, or **URLs Only**.
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

1. **Build Your Query**:
   - In **Tab 1 (Query Builder & Presets)**, select your target search engine (e.g. Google, DuckDuckGo, Bing).
   - Enter your target site (e.g. `site:linkedin.com/in/`), industry keywords, job titles, and location.
   - Click **+ Wrap site:** or **+ Quotes/OR** to auto-format boolean logic.
2. **Execute Search**:
   - Choose your page count and delay.
   - Click **🚀 Search & Extract Leads**.
3. **View & Export Leads**:
   - Switch to **Tab 2 (Extracted Results & Text Box)** to review structured lead cards.
   - Filter results live by typing in the filter box.
   - Click **📋 Copy All**, **✉️ Copy Emails List**, or **💾 Export CSV File**.

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
