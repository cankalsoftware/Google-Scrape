import csv
import io
import json
import os
import re
import sys
import time
import urllib.parse
import threading
import http.server
import webbrowser
import socket
import smtplib
import zipfile
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

# Try importing dnspython for MX verification with standard library fallback
try:
    import dns
    import dns.resolver
    DNS_RESOLVER_AVAILABLE = True
except (ImportError, Exception):
    dns = None
    DNS_RESOLVER_AVAILABLE = False


# Regex patterns for contact information extraction
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

# Strict UK & International Phone Number Patterns with lookaround boundaries
UK_PHONE_REGEX = re.compile(
    r'(?<![\d.\-/])(?:'
    r'(?:\+44\s?(?:\(0\))?|\(\+44\)\s?(?:\(0\))?|0044\s?(?:\(0\))?)\s?[12378]\d{1,4}(?:[\s.-]?\d{3,4}){2}'
    r'|'
    r'0[12378]\d{1,4}(?:[\s.-]?\d{3,4}){2}'
    r')(?![\d.\-/])'
)

INTL_PHONE_REGEX = re.compile(
    r'(?<![\d.\-/])(?:\+\d{1,3}\s?(?:\(\d{1,4}\)|\d{1,4})[\s.-]?\d{2,4}[\s.-]?\d{2,4}(?:[\s.-]?\d{2,4})?)(?![\d.\-/])'
)

LABELLED_PHONE_REGEX = re.compile(
    r'(?:tel(?:ephone)?|phone|call(?:\s+us)?|mob(?:ile)?|direct|t|office|enquiries|contact|headquarters)\s*[:.\-]?\s*'
    r'([+\d\s().\-/]{9,25})(?![\d.\-/])',
    re.IGNORECASE
)

# Backward-compatible pattern
PHONE_PATTERN = UK_PHONE_REGEX

def clean_phone_candidate(ph_str: str) -> str:
    """Cleans up leading/trailing punctuation and labels from telephone string."""
    ph = ph_str.strip()
    ph = re.sub(r'^[^\d+]+', '', ph)
    ph = re.sub(r'[^\d)]+$', '', ph)
    return ph.strip()

def is_valid_phone_number(candidate: str) -> bool:
    """
    Validates whether a string is a genuine local or international phone number,
    strictly rejecting floating-point decimals, coordinates, research stats, years, and dates.
    """
    if not candidate:
        return False
    ph = clean_phone_candidate(candidate)
    digits = re.sub(r'\D', '', ph)
    digit_count = len(digits)
    
    # 1. Length check: between 9 and 15 digits
    if digit_count < 9 or digit_count > 15:
        return False
        
    # 2. Reject floating point / decimal numbers / coordinates / metrics (e.g. 3.189369679, 0.1279989399, 13.0923886189, 23.6273625)
    if '.' in ph:
        dot_parts = ph.split('.')
        for i, part in enumerate(dot_parts):
            if i > 0 and len(part) > 4:
                return False
        if any(ph.startswith(f"{d}.") for d in range(10)):
            if len(dot_parts) == 2 and len(dot_parts[1]) > 4:
                return False
                
    # 3. Reject years and date patterns (e.g. 2024, 2023, 2024-05-12, 12/04/2023)
    if re.fullmatch(r'^(?:19\d\d|20\d\d)$', digits):
        return False
    if re.search(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$', ph) or re.search(r'^\d{1,2}[-/]\d{1,2}[-/]\d{4}$', ph):
        return False
        
    # 4. Reject all identical digits (e.g. 0000000000, 1111111111)
    if len(set(digits)) <= 2 and digit_count > 8:
        return False
        
    # 5. Check structure
    if UK_PHONE_REGEX.search(ph):
        return True
    if INTL_PHONE_REGEX.search(ph):
        if ph.startswith('+') or ph.startswith('(+' ) or ph.startswith('00'):
            return True
        if ('(' in ph and ')' in ph) or ('-' in ph) or (' ' in ph):
            if digit_count >= 10:
                return True
                
    if digits.startswith('0') and digit_count in (10, 11):
        if digits[1] in ('1', '2', '3', '7', '8'):
            return True
            
    return False

def extract_phones_from_soup_or_text(soup=None, text="") -> list:
    """
    Extracts valid telephone numbers from HTML elements (tel links, footers, contact sections)
    and text, strictly filtering out statistics, decimals, years, and coordinates.
    """
    phones = []
    
    if soup:
        # 1. Priority 1: Check explicit tel: hyperlinks (often in header/footer)
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("tel:"):
                raw_tel = href.split("tel:")[1].split("?")[0].strip()
                a_text = clean_phone_candidate(a.get_text(strip=True))
                candidate = a_text if is_valid_phone_number(a_text) else clean_phone_candidate(raw_tel)
                if is_valid_phone_number(candidate):
                    phones.append(candidate)
                    
        # 2. Priority 2: Check footer, contact sections, and location containers
        contact_elements = soup.find_all(["footer", "section", "div", "aside"], class_=re.compile(r"footer|contact|location|header|depot", re.I))
        contact_elements += soup.find_all(["footer", "section", "div"], id=re.compile(r"footer|contact|location|header|depot", re.I))
        for el in contact_elements:
            el_text = el.get_text(separator=" ")
            for m in LABELLED_PHONE_REGEX.finditer(el_text):
                cleaned = clean_phone_candidate(m.group(1))
                if is_valid_phone_number(cleaned):
                    phones.append(cleaned)
            for m in UK_PHONE_REGEX.finditer(el_text):
                cleaned = clean_phone_candidate(m.group(0))
                if is_valid_phone_number(cleaned):
                    phones.append(cleaned)
                    
        text = soup.get_text(separator=" ")
        
    if text:
        for m in LABELLED_PHONE_REGEX.finditer(text):
            cleaned = clean_phone_candidate(m.group(1))
            if is_valid_phone_number(cleaned):
                phones.append(cleaned)
        for m in UK_PHONE_REGEX.finditer(text):
            cleaned = clean_phone_candidate(m.group(0))
            if is_valid_phone_number(cleaned):
                phones.append(cleaned)
        for m in INTL_PHONE_REGEX.finditer(text):
            cleaned = clean_phone_candidate(m.group(0))
            if is_valid_phone_number(cleaned):
                phones.append(cleaned)

    # Clean, format, and deduplicate
    unique = []
    seen_digits = set()
    for p in phones:
        digits = re.sub(r'\D', '', p)
        if digits not in seen_digits and digits[-9:] not in seen_digits:
            seen_digits.add(digits)
            seen_digits.add(digits[-9:])
            unique.append(p)
            
    return unique

# ---------------------------------------------------------------------------
# MODULAR DATA & STORAGE LAYER (JSON Configs + SQLite Persistence)
# ---------------------------------------------------------------------------
import data_loader
import storage

# History log file path & Auth Profile path & Registry Sources
HISTORY_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "search_history.log")
REGISTRY_SOURCES_FILE = data_loader.REGISTRY_SOURCES_FILE
AUTH_PROFILE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "GoogleScraperAuthProfile")
LOCAL_ENRICHMENT_PORT = 8765

# Pre-configured Official Open Data Registers and Directory Portals
DEFAULT_REGISTRY_SOURCES = data_loader.load_registry_sources()

def load_registry_sources():
    """Loads saved registry sources using data_loader."""
    return data_loader.load_registry_sources()

def save_registry_sources(sources_list):
    """Saves registry sources using data_loader."""
    return data_loader.save_registry_sources(sources_list)

# Backward-compatible dynamic domain lookups
UK_FIRE_SERVICES_DOMAINS = data_loader.get_domain_lookup("fire")
UK_NHS_DOMAINS = data_loader.get_domain_lookup("nhs")
UK_COUNCILS_DOMAINS = data_loader.get_domain_lookup("council")
UK_POLICE_DOMAINS = data_loader.get_domain_lookup("police")
UK_ENVIRONMENT_DOMAINS = data_loader.get_domain_lookup("environment")
UK_TRANSPORT_HIGHWAYS_DOMAINS = data_loader.get_domain_lookup("transport_highways")

HONORIFICS = {
    "dr", "dr.", "doctor", "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "miss",
    "prof", "prof.", "professor", "cllr", "cllr.", "councillor", "sir", "dame",
    "chief", "cfo", "cio", "cto", "ceo", "cso", "cpo", "cmo", "coo", "officer", "acfo", "dcfo"
}

POST_NOMINALS = {
    "obe", "mbe", "cbe", "kbe", "qfsm", "qgm", "qpm", "bsc", "msc", "phd", "ba",
    "ma", "beng", "meng", "mba", "ceng", "cism", "cisa", "cissp", "mifiree",
    "fifiree", "fism", "mbcs", "citp", "frsa", "fcipd", "mcipd", "cmgr", "fcmgr",
    "fimi", "mimi", "dip", "pgdip", "pge", "hnd", "hnc"
}

NON_PERSON_TOKENS = {
    "site", "contact", "contacts", "commercial", "enquiry", "enquiries",
    "customer", "service", "services", "head", "office", "headquarters",
    "sales", "team", "support", "helpdesk", "general", "operations",
    "facility", "facilities", "depot", "plant", "station", "centre", "center",
    "press", "media", "info", "admin", "administration", "recycling", "waste",
    "environmental", "management", "the", "heart", "of", "our", "lead", "leads",
    "about", "location", "locations", "depots", "manager", "director", "officer",
    "deputy", "assistant", "executive", "in", "london", "uk", "waste", "materials"
}

JOB_BOARD_DOMAINS = {
    "fish4.co.uk", "indeed.com", "indeed.co.uk", "reed.co.uk", "totaljobs.com",
    "cv-library.co.uk", "glassdoor.com", "glassdoor.co.uk", "jooble.org",
    "jobsite.co.uk", "ziprecruiter.com", "ziprecruiter.co.uk", "monster.co.uk",
    "monster.com", "simplyhired.com", "simplyhired.co.uk", "targetjobs.co.uk",
    "cwjobs.co.uk", "adzuna.co.uk", "guardianjobs.com", "jobs.theguardian.com",
    "jobserve.com", "jobstoday.co.uk", "bamboohr.com", "greenhouse.io",
    "lever.co", "workday.com", "workable.com", "jobrapido.com", "careers-page.com"
}

JOB_URL_PATTERNS = [
    r'/jobs?/', r'/vacanc(?:y|ies)/', r'/job-opportunity/', r'/employment-opportunity/'
]

def is_job_posting_url(url: str) -> bool:
    """Detects whether a URL originates from a job recruitment aggregator board."""
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = re.sub(r'^www\.', '', parsed.netloc.lower())
        if netloc in JOB_BOARD_DOMAINS or any(netloc.endswith("." + jb) for jb in JOB_BOARD_DOMAINS):
            return True
        if any(re.search(p, parsed.path, re.IGNORECASE) for p in JOB_URL_PATTERNS):
            if not any(k in parsed.path.lower() for k in ["/about", "/contact", "/facility", "/facilities", "/services", "/depot"]):
                return True
    except Exception:
        pass
    return False

_MX_CACHE = {}


def clean_org_text(text: str) -> str:
    """Cleans and standardizes organization strings for dictionary matching."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r'[\'\"’“”\(\)\[\],.;]', ' ', t)
    t = re.sub(r'&', ' and ', t)
    t = re.sub(r'\s+and\s+', ' and ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def parse_lead_name(full_name: str):
    """
    Parses a raw full name string into (First Name, Surname, Display Name).
    Strips titles, honorifics, post-nominal credentials, pronoun tags, and noise.
    Recognizes non-person entities and generic titles (e.g. 'Site Contact', 'Commercial Enquiries').
    """
    if not full_name:
        return "", "", ""
    
    # Remove unicode emojis and LinkedIn badges
    raw = re.sub(r'[\U00010000-\U0010ffff]', '', full_name)
    raw = raw.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()
    
    # Remove parenthesized pronouns or details (e.g. "John Smith (He/Him)" or "Site Contact (Lea Riverside)")
    raw = re.sub(r'\([^\)]*\)', '', raw)
    raw = re.sub(r'\[[^\]]*\]', '', raw)
    
    # Split by comma if contains qualifications
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    main_name = tokens[0] if tokens else raw
    
    words = main_name.split()
    clean_words = []
    
    for w in words:
        w_lower = re.sub(r'[^a-zA-Z0-9\'-]', '', w.lower()).strip('.')
        if w_lower in HONORIFICS or w_lower in POST_NOMINALS:
            continue
        cleaned = re.sub(r'[^a-zA-Z\'-]', '', w)
        if cleaned:
            clean_words.append(cleaned)
            
    if not clean_words:
        return "", "", main_name
        
    if len(clean_words) == 1:
        if clean_words[0].lower() in NON_PERSON_TOKENS:
            return "", "", main_name
        return clean_words[0].capitalize(), "", clean_words[0].capitalize()
        
    first_name = clean_words[0].capitalize()
    last_name = clean_words[-1].capitalize()
    
    # Check if this is a generic non-person entity (e.g. "Site Contact", "Commercial Enquiries", "The Heart of Our Operations", "Lea Riverside Facilities")
    if (first_name.lower() in NON_PERSON_TOKENS and last_name.lower() in NON_PERSON_TOKENS) or \
       last_name.lower() in ["facilities", "facility", "depot", "plant", "station", "centre", "center", "operations", "recycling", "services", "team", "office", "group", "ltd", "limited", "plc", "enquiries", "contact", "contacts", "management", "works", "manager", "officer", "director"] or \
       all(cw.lower() in NON_PERSON_TOKENS for cw in clean_words) or \
       main_name.lower().strip().startswith(("site contact", "commercial enquir", "general enquir", "customer service", "head office", "sales team", "the heart of", "deputy operations", "operations manager")):
        return "", "", main_name
        
    # Handle compound surnames (e.g. "van der Sar", "de Boer", "St. John")
    if len(clean_words) == 3 and clean_words[1].lower() in ["van", "de", "von", "del", "st", "st."]:
        last_name = f"{clean_words[1].capitalize()} {clean_words[2].capitalize()}"
        
    display_name = f"{first_name} {last_name}"
    return first_name, last_name, display_name


def resolve_organization_domain(org_text: str, headline: str = "", snippet: str = "", industry: str = "fire", custom_domain: str = "") -> str:
    """
    Resolves the official domain (.gov.uk / .org.uk / .net) for an organization.
    Multi-tier lookup: Exact -> Aliases/Acronyms -> Keyword -> Snippet extraction -> Custom Fallback.
    """
    if custom_domain and custom_domain.strip():
        return custom_domain.strip().lower().replace("@", "")
        
    # Select active lookup dictionary via data_loader
    lookup_dict = data_loader.get_domain_lookup(industry)
        
    clean_org = clean_org_text(org_text)
    combined = clean_org_text(f"{org_text} {headline} {snippet}")
    
    # 1. Check primary industry lookup dictionary (with exact match and whole-word regex matching)
    if clean_org in lookup_dict:
        return lookup_dict[clean_org]
    for key, dom in sorted(lookup_dict.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = rf'(?:^|[\s,.\-–—/])' + re.escape(key) + r'(?:$|[\s,.\-–—/])'
        if re.search(pattern, clean_org, re.IGNORECASE) or re.search(pattern, combined, re.IGNORECASE):
            return dom
            
    # 2. Check all sectors lookup dictionary as fallback
    all_dict = data_loader.get_domain_lookup("all")
    if clean_org in all_dict:
        return all_dict[clean_org]
    for key, dom in sorted(all_dict.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = rf'(?:^|[\s,.\-–—/])' + re.escape(key) + r'(?:$|[\s,.\-–—/])'
        if re.search(pattern, clean_org, re.IGNORECASE) or re.search(pattern, combined, re.IGNORECASE):
            return dom
            
    # 3. Check if any .gov.uk or .nhs.uk or .police.uk domain is mentioned directly in snippet
    domain_match = re.search(r'\b([a-zA-Z0-9.-]+\.(?:gov\.uk|nhs\.uk|police\.uk|org\.uk|ac\.uk))\b', f"{org_text} {snippet}")
    if domain_match:
        extracted_dom = domain_match.group(1).lower()
        if not any(se in extracted_dom for se in ["linkedin.", "google.", "bing.", "duckduckgo.", "brave.", "yahoo.", "yandex."]):
            return extracted_dom
            
    return ""


def verify_domain_mx(domain: str):
    """
    Queries DNS MX records to verify active mail exchangers with SQLite persistent cache.
    Returns: (is_valid: bool, status_label: str, mx_hosts: list)
    """
    if not domain:
        return False, "No Domain", []
    domain = domain.lower().strip()
    
    # 1. In-Memory Cache Check
    if domain in _MX_CACHE:
        return _MX_CACHE[domain]
        
    # 2. SQLite Persistent Cache Check
    cached = storage.get_cached_mx(domain)
    if cached is not None:
        hosts = [cached["mx_host"]] if cached["mx_host"] else []
        status = "Valid (MX Verified)" if cached["has_mx"] else "Invalid (No MX)"
        res = (cached["has_mx"], status, hosts)
        _MX_CACHE[domain] = res
        return res
        
    if DNS_RESOLVER_AVAILABLE and dns is not None:
        try:
            answers = dns.resolver.resolve(domain, 'MX', lifetime=4.0)
            mx_list = [str(r.exchange).rstrip('.') for r in answers]
            if mx_list:
                res = (True, "Valid (MX Verified)", mx_list)
                _MX_CACHE[domain] = res
                return res
        except Exception:
            try:
                dns.resolver.resolve(domain, 'A', lifetime=3.0)
                res = (True, "Risky (A Record Fallback)", [])
                _MX_CACHE[domain] = res
                return res
            except Exception:
                pass
                
    # Standard library socket fallback (requires zero external packages)
    try:
        import socket
        ip = socket.gethostbyname(domain)
        res = (True, "Valid (Host Active)", [f"IP: {ip}"])
    except Exception:
        res = (False, "Invalid (Host Unreachable)", [])
        
    _MX_CACHE[domain] = res
    try:
        primary_host = res[2][0] if (len(res) > 2 and res[2]) else ""
        storage.set_cached_mx(domain, res[0], False, primary_host)
    except Exception:
        pass
    return res



def scrape_website_contacts(url: str, timeout: int = 8) -> dict:
    """
    Visits a company/facility website (and common contact/about pages)
    to discover live corporate contact emails, telephone numbers, and site contact info.
    """
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return {"emails": [], "phones": [], "primary_email": "", "primary_phone": ""}
        
    emails = []
    phones = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9"
    }
    
    try:
        parsed_url = urllib.parse.urlparse(url)
        base_domain = re.sub(r'^www\.', '', parsed_url.netloc.lower())
        base_origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        visited = set()
        pages_to_check = [url]
        
        for p in ["/contact", "/contact-us", "/contactus", "/about", "/about-us", "/locations", "/get-in-touch"]:
            pages_to_check.append(urllib.parse.urljoin(base_origin, p))
            
        checked_count = 0
        for target_page in pages_to_check:
            if target_page in visited or checked_count >= 3:
                continue
            visited.add(target_page)
            checked_count += 1
            
            try:
                resp = requests.get(target_page, headers=headers, timeout=timeout, allow_redirects=True)
                if resp.status_code == 200 and "text/html" in resp.headers.get("Content-Type", ""):
                    soup = BeautifulSoup(resp.text, "html.parser")
                    
                    # 1. Parse mailto hyperlinks
                    for a in soup.find_all("a", href=True):
                        href_val = a["href"].strip()
                        if href_val.lower().startswith("mailto:"):
                            raw_mail = href_val.split("mailto:")[1].split("?")[0].strip().lower()
                            if EMAIL_PATTERN.match(raw_mail) and not any(junk in raw_mail for junk in ["example.com", "domain.com", "wixpress.com", "sentry.io", "wordpress.org"]):
                                emails.append(raw_mail)
                                
                    # 2. Extract validated telephone numbers from HTML elements (tel links, footer, contact sections) and text
                    page_phones = extract_phones_from_soup_or_text(soup=soup)
                    phones.extend(page_phones)
                    
                    # 3. Text regex scan for emails
                    page_text = soup.get_text(separator=" ")
                    found_emails = EMAIL_PATTERN.findall(page_text)
                    for em in found_emails:
                        em_clean = em.strip().lower()
                        if not any(junk in em_clean for junk in ["example.com", "domain.com", "wixpress.com", "sentry.io", "wordpress.org", "schema.org"]):
                            emails.append(em_clean)
                            
                    # 3. If homepage, discover on-page contact links
                    if checked_count == 1:
                        for a in soup.find_all("a", href=True):
                            a_href = a["href"].strip()
                            a_text = a.get_text(strip=True).lower()
                            if any(k in a_text or k in a_href.lower() for k in ["contact", "get in touch", "locations", "about us", "depots"]):
                                full_link = urllib.parse.urljoin(target_page, a_href)
                                if urllib.parse.urlparse(full_link).netloc.lower() == parsed_url.netloc.lower():
                                    if full_link not in visited and full_link not in pages_to_check:
                                        pages_to_check.insert(checked_count, full_link)
            except Exception:
                continue
                
            domain_specific_emails = [e for e in emails if base_domain in e]
            if domain_specific_emails and phones:
                break
    except Exception:
        pass
        
    unique_emails = list(dict.fromkeys(emails))
    unique_phones = list(dict.fromkeys(phones))
    
    if base_domain:
        matched = [e for e in unique_emails if base_domain in e]
        other = [e for e in unique_emails if base_domain not in e]
        unique_emails = matched + other
        
    primary_email = unique_emails[0] if unique_emails else ""
    primary_phone = unique_phones[0] if unique_phones else ""
    
    return {
        "emails": unique_emails,
        "phones": unique_phones,
        "primary_email": primary_email,
        "primary_phone": primary_phone
    }


def synthesize_email(first_name: str, last_name: str, domain: str, pattern: str = "{first}.{last}@{domain}") -> str:
    """
    Synthesizes corporate/public sector email based on naming pattern formula.
    """
    if not domain:
        return ""
    domain = domain.lower().strip()
    
    if not first_name and not last_name:
        return f"info@{domain}"
        
    f_clean = re.sub(r'[^a-zA-Z0-9]', '', (first_name or "").lower())
    l_clean = re.sub(r'[^a-zA-Z0-9]', '', (last_name or "").lower())
    
    if not f_clean and not l_clean:
        return f"info@{domain}"
    if not f_clean:
        return f"{l_clean}@{domain}"
    if not l_clean:
        return f"{f_clean}@{domain}"
        
    f_initial = f_clean[0]
    l_initial = l_clean[0]
    
    try:
        formatted = pattern.format(
            first=f_clean,
            last=l_clean,
            f=f_initial,
            l=l_initial,
            domain=domain
        )
        return formatted
    except Exception:
        return f"{f_clean}.{l_clean}@{domain}"


def api_enrich_lead(lead_dict: dict, provider: str = "builtin", api_key: str = "", pattern: str = "{first}.{last}@{domain}", industry: str = "fire", custom_domain: str = "") -> dict:
    """
    Core enrichment function supporting Built-in MX Engine, Hunter.io, Apollo, and Snov.io.
    """
    full_name = lead_dict.get("Name", "")
    headline = lead_dict.get("Headline / Role", "")
    org = lead_dict.get("Organisation", "")
    snippet = lead_dict.get("Snippet", "")
    url = lead_dict.get("URL", "")
    
    first_name, last_name, display_name = parse_lead_name(full_name)
    if not first_name and lead_dict.get("First Name"):
        first_name = lead_dict.get("First Name")
    if not last_name and lead_dict.get("Last Name"):
        last_name = lead_dict.get("Last Name")
        
    # Domain resolution prioritization
    domain = lead_dict.get("Domain", "")
    if not domain and url:
        try:
            parsed_netloc = urllib.parse.urlparse(url).netloc.lower()
            clean_netloc = re.sub(r'^www\.', '', parsed_netloc)
            non_corporate = ['google.', 'bing.', 'duckduckgo.', 'brave.', 'yahoo.', 'yandex.', 'ahmia.', 'linkedin.', 'youtube.', 'facebook.', 'twitter.', 'x.com', 'instagram.', 'wikipedia.']
            if clean_netloc and not any(se in clean_netloc for se in non_corporate):
                domain = clean_netloc
        except Exception:
            pass
    if not domain:
        domain = resolve_organization_domain(org, headline, snippet, industry, custom_domain)
        
    raw_email = lead_dict.get("Email", "")
    if not raw_email and lead_dict.get("Enriched Email"):
        existing_e = lead_dict.get("Enriched Email", "")
        if "info@" not in existing_e and "Pending" not in lead_dict.get("Deliverability", ""):
            raw_email = existing_e
            
    # Auto scrape site contacts if open-web URL and no real email yet
    if not raw_email and url and "linkedin.com" not in url and (url.startswith("http://") or url.startswith("https://")):
        try:
            site_res = scrape_website_contacts(url, timeout=8)
            if site_res.get("emails"):
                raw_email = ", ".join(site_res["emails"])
                if not lead_dict.get("Phone") and site_res.get("phones"):
                    lead_dict["Phone"] = ", ".join(site_res["phones"])
        except Exception:
            pass
            
    # 1. External API: Hunter.io
    if provider == "hunter" and api_key and domain and (first_name or last_name):
        try:
            url_h = f"https://api.hunter.io/v2/email-finder?domain={domain}&first_name={first_name}&last_name={last_name}&api_key={api_key}"
            resp = requests.get(url_h, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                email = data.get("email", "")
                score = data.get("score", 0)
                status = "Valid (Hunter.io)" if score >= 70 else "Risky (Hunter.io)"
                badge = "🟢 Valid (Hunter)" if score >= 70 else "🟡 Risky"
                return {
                    "First Name": first_name,
                    "Last Name": last_name,
                    "Domain": domain,
                    "Enriched Email": email,
                    "Email": raw_email or email,
                    "Phone": lead_dict.get("Phone", ""),
                    "Deliverability": status,
                    "Deliverability Badge": badge,
                    "MX Server": "Hunter.io Verified",
                    "Score": score
                }
        except Exception:
            pass
            
    # 2. External API: Apollo.io
    if provider == "apollo" and api_key and domain and (first_name or last_name):
        try:
            url_a = "https://api.apollo.io/v1/people/match"
            payload = {"api_key": api_key, "first_name": first_name, "last_name": last_name, "domain": domain}
            resp = requests.post(url_a, json=payload, timeout=10)
            if resp.status_code == 200:
                person = resp.json().get("person", {})
                email = person.get("email", "")
                if email:
                    return {
                        "First Name": first_name,
                        "Last Name": last_name,
                        "Domain": domain,
                        "Enriched Email": email,
                        "Email": raw_email or email,
                        "Phone": lead_dict.get("Phone", ""),
                        "Deliverability": "Valid (Apollo)",
                        "Deliverability Badge": "🟢 Valid (Apollo)",
                        "MX Server": "Apollo.io Verified",
                        "Score": 90
                    }
        except Exception:
            pass

    # 3. Built-in MX & Pattern Engine (Default - Instant, Free, Reliable)
    if domain:
        is_mx_valid, mx_status, mx_servers = verify_domain_mx(domain)
        if raw_email:
            primary_e = raw_email.split(',')[0].strip()
            email = primary_e
            deliverability = "Valid (Scraped from Site)" if is_mx_valid else "Valid (Scraped)"
            badge = "🟢 Scraped"
        else:
            if first_name and last_name:
                email = synthesize_email(first_name, last_name, domain, pattern)
                if is_mx_valid:
                    badge = "🟢 Valid (MX)"
                    deliverability = "Valid (MX Verified)"
                else:
                    badge = "🔴 No MX"
                    deliverability = "Invalid (No MX)"
            else:
                email = f"info@{domain.lower()}"
                if is_mx_valid:
                    badge = "🟢 Valid (MX)"
                    deliverability = "Valid (MX Verified)"
                else:
                    badge = "🔴 No MX"
                    deliverability = "Invalid (No MX)"
            
        mx_host = mx_servers[0] if mx_servers else "None"
        return {
            "First Name": first_name,
            "Last Name": last_name,
            "Domain": domain,
            "Enriched Email": email,
            "Email": raw_email or email,
            "Phone": lead_dict.get("Phone", ""),
            "Deliverability": deliverability,
            "Deliverability Badge": badge,
            "MX Server": mx_host,
            "Score": 95 if is_mx_valid else 20
        }
    else:
        return {
            "First Name": first_name,
            "Last Name": last_name,
            "Domain": "",
            "Enriched Email": raw_email,
            "Email": raw_email,
            "Phone": lead_dict.get("Phone", ""),
            "Deliverability": "Not Found (Unknown Domain)" if not raw_email else "Valid (Scraped)",
            "Deliverability Badge": "⚪ Not Found" if not raw_email else "🟢 Scraped",
            "MX Server": "None",
            "Score": 0
        }


def reformat_email_string(email: str, pattern: str = "{first}{last}@{domain}", info: str = "", raw_row: dict = None) -> str:
    """
    Transforms an email address into a new naming pattern (e.g. ali.cankal@domain.com -> alicankal@domain.com or acankal@domain.com).
    Extracts name parts from metadata, or decomposes the original email username.
    """
    if not email or "@" not in email:
        return email
    
    parts = email.strip().split("@")
    user_part = parts[0].strip().lower()
    domain = parts[1].strip().lower()
    
    first = ""
    last = ""
    
    # 1. Try to extract first and last name from raw_row dictionary if available
    if raw_row and isinstance(raw_row, dict):
        for k in ["First Name", "First_Name", "first_name", "firstname", "Forename"]:
            if k in raw_row and raw_row[k]:
                first = str(raw_row[k]).strip()
                break
        for k in ["Surname", "Last Name", "Last_Name", "last_name", "lastname", "Family_Name"]:
            if k in raw_row and raw_row[k]:
                last = str(raw_row[k]).strip()
                break
        if not (first and last):
            for k in ["Name", "Full Name", "Full_Name", "full_name", "Contact"]:
                if k in raw_row and raw_row[k]:
                    f, l, _ = parse_lead_name(str(raw_row[k]))
                    if f: first = f
                    if l: last = l
                    break

    # 2. Try to extract from info string if still missing
    if not (first and last) and info:
        f, l, _ = parse_lead_name(info)
        if f: first = f
        if l: last = l

    # 3. If still missing, parse username part before @
    if not (first and last):
        clean_u = re.sub(r'[^a-zA-Z0-9._-]', '', user_part)
        if "." in clean_u:
            u_parts = [p for p in clean_u.split(".") if p]
            if len(u_parts) >= 2:
                first = u_parts[0]
                last = u_parts[-1]
            elif len(u_parts) == 1:
                first = u_parts[0]
        elif "_" in clean_u:
            u_parts = [p for p in clean_u.split("_") if p]
            if len(u_parts) >= 2:
                first = u_parts[0]
                last = u_parts[-1]
            elif len(u_parts) == 1:
                first = u_parts[0]
        elif "-" in clean_u:
            u_parts = [p for p in clean_u.split("-") if p]
            if len(u_parts) >= 2:
                first = u_parts[0]
                last = u_parts[-1]
            elif len(u_parts) == 1:
                first = u_parts[0]
        else:
            first = clean_u
            last = ""

    first_clean = re.sub(r'[^a-zA-Z0-9]', '', first.lower())
    last_clean = re.sub(r'[^a-zA-Z0-9]', '', last.lower())
    
    f_init = first_clean[0] if first_clean else ""
    l_init = last_clean[0] if last_clean else ""
    
    # Handle pattern evaluation
    try:
        new_email = pattern.format(
            first=first_clean,
            last=last_clean,
            f=f_init,
            l=l_init,
            domain=domain
        )
        return new_email
    except Exception:
        if first_clean and last_clean:
            return f"{first_clean}{last_clean}@{domain}"
        elif first_clean:
            return f"{first_clean}@{domain}"
        return email


def verify_email_smtp_handshake(email: str, timeout: int = 8, check_catchall: bool = False) -> dict:
    """
    Performs full DNS MX resolution + SMTP Handshake verification (HELO -> MAIL FROM -> RCPT TO).
    Returns a structured dictionary with deliverability status, badge, mx host, code, and response time.
    """
    start_time = time.time()
    clean_email = str(email).strip()
    
    if not clean_email or "@" not in clean_email:
        return {
            "email": clean_email,
            "domain": "",
            "mx_host": "None",
            "smtp_code": 0,
            "status": "Invalid Format",
            "badge": "⚪ Invalid Email",
            "deliverable": False,
            "details": "Missing @ symbol or malformed email string",
            "response_time_ms": int((time.time() - start_time) * 1000)
        }
        
    parts = clean_email.split("@")
    user_part = parts[0].strip()
    domain_part = parts[1].strip().lower()
    
    # 1. Resolve DNS MX records
    mx_hosts = []
    if DNS_RESOLVER_AVAILABLE:
        try:
            records = dns.resolver.resolve(domain_part, 'MX', lifetime=timeout)
            sorted_records = sorted(records, key=lambda r: r.preference)
            for r in sorted_records:
                mx_hosts.append(str(r.exchange).rstrip('.'))
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, Exception):
            pass
            
    if not mx_hosts:
        # Fallback to direct domain check
        try:
            socket.gethostbyname(domain_part)
            mx_hosts = [domain_part]
        except Exception:
            return {
                "email": clean_email,
                "domain": domain_part,
                "mx_host": "None",
                "smtp_code": 0,
                "status": "Domain Not Found (No MX)",
                "badge": "🔴 No MX Record",
                "deliverable": False,
                "details": f"No active MX records or DNS host found for {domain_part}",
                "response_time_ms": int((time.time() - start_time) * 1000)
            }

    target_mx = mx_hosts[0]
    
    # 2. SMTP Handshake Verification
    smtp_code = 0
    smtp_msg = ""
    is_deliverable = False
    status_label = ""
    badge_label = ""
    
    try:
        server = smtplib.SMTP(timeout=timeout)
        server.connect(target_mx, 25)
        server.helo('check.local')
        server.mail('probe@check.local')
        code, msg = server.rcpt(clean_email)
        smtp_code = code
        smtp_msg = msg.decode('utf-8', errors='ignore') if isinstance(msg, bytes) else str(msg)
        
        # Check catch-all if requested and response code is 250
        is_catchall = False
        if code == 250 and check_catchall:
            try:
                fake_user = f"nonexistent_probe_{int(time.time())}@{domain_part}"
                f_code, _ = server.rcpt(fake_user)
                if f_code == 250:
                    is_catchall = True
            except Exception:
                pass
                
        try:
            server.quit()
        except Exception:
            pass
            
        if is_catchall:
            status_label = "Catch-All Domain (Accepts All Mailboxes)"
            badge_label = "🟡 Catch-All"
            is_deliverable = True
        elif code == 250:
            status_label = "Deliverable (250 OK - Mailbox Verified)"
            badge_label = "🟢 Deliverable"
            is_deliverable = True
        elif code in [450, 451, 452]:
            status_label = f"Greylisted / Temporary Error ({code})"
            badge_label = "🟡 Greylisted"
            is_deliverable = False
        elif code >= 500:
            status_label = f"Undeliverable ({code} Mailbox Not Found)"
            badge_label = f"🔴 Undeliverable ({code})"
            is_deliverable = False
        else:
            status_label = f"SMTP Response: {code}"
            badge_label = f"🟡 Code {code}"
            is_deliverable = False
            
    except (socket.timeout, TimeoutError):
        status_label = "MX Server Active (SMTP Timeout)"
        badge_label = "🟡 MX Active"
        smtp_msg = "SMTP port 25 connection timed out (often throttled by ISP/firewall)"
        is_deliverable = True  # MX exists
    except (ConnectionRefusedError, OSError) as e:
        status_label = "MX Server Active (Port 25 Filtered)"
        badge_label = "🟡 MX Active"
        smtp_msg = f"Port 25 blocked by local network/ISP ({type(e).__name__})"
        is_deliverable = True  # MX exists
    except Exception as e:
        status_label = f"Check Failed: {type(e).__name__}"
        badge_label = "⚪ Check Error"
        smtp_msg = str(e)
        
    return {
        "email": clean_email,
        "domain": domain_part,
        "mx_host": target_mx,
        "smtp_code": smtp_code,
        "status": status_label,
        "badge": badge_label,
        "deliverable": is_deliverable,
        "details": smtp_msg,
        "response_time_ms": int((time.time() - start_time) * 1000)
    }


DEFAULT_WATERFALL_PATTERNS = [
    ("{first}.{last}@{domain}", "first.last"),
    ("{first}{last}@{domain}", "firstlast (no dot)"),
    ("{f}{last}@{domain}", "flast (initial+last)"),
    ("{first}_{last}@{domain}", "first_last (underscore)"),
    ("{last}.{first}@{domain}", "last.first"),
    ("{last}{first}@{domain}", "lastfirst"),
    ("{last}{f}@{domain}", "lastf (last+initial)"),
    ("{first}@{domain}", "first only"),
    ("{f}.{last}@{domain}", "f.last (initial.last)")
]


def verify_email_waterfall_permutations(
    email: str,
    raw_row: dict = None,
    info: str = "",
    timeout: int = 8,
    check_catchall: bool = False,
    patterns: list = None
) -> dict:
    """
    Tests an email across all naming permutations in an automated waterfall sequence:
    Tries 1) first.last -> 2) firstlast -> 3) flast -> 4) first_last -> 5) last.first -> 6) lastf ...
    As soon as ANY permutation returns 250 OK (Deliverable), immediately returns that winning email!
    If all permutations return 550 or fail, marks as Undeliverable.
    """
    if patterns is None:
        patterns = DEFAULT_WATERFALL_PATTERNS

    clean_orig = str(email).strip()
    if not clean_orig or "@" not in clean_orig:
        return {
            "email": clean_orig,
            "original_email": clean_orig,
            "domain": "",
            "mx_host": "None",
            "smtp_code": 0,
            "status": "Invalid Format",
            "badge": "⚪ Invalid Email",
            "deliverable": False,
            "permutations_tested": 0,
            "details": "Malformed email address",
            "response_time_ms": 0
        }

    # Generate unique candidate emails in prioritized order
    candidates = []
    seen = set()
    
    # 1. First candidate is the original input email
    candidates.append((clean_orig, "original"))
    seen.add(clean_orig.lower())
    
    # 2. Add waterfall permutations
    for pat_fmt, pat_label in patterns:
        cand = reformat_email_string(clean_orig, pattern=pat_fmt, info=info, raw_row=raw_row)
        cand_clean = cand.strip()
        if cand_clean and cand_clean.lower() not in seen and "@" in cand_clean:
            seen.add(cand_clean.lower())
            candidates.append((cand_clean, pat_label))

    last_res = None
    tested_count = 0
    start_all = time.time()

    for cand_email, cand_label in candidates:
        tested_count += 1
        res = verify_email_smtp_handshake(cand_email, timeout=timeout, check_catchall=check_catchall)
        last_res = res
        
        # If Deliverable (250 OK) or Catch-All
        if res.get("deliverable"):
            return {
                "email": cand_email,
                "original_email": clean_orig,
                "winning_pattern": cand_label,
                "domain": res["domain"],
                "mx_host": res["mx_host"],
                "smtp_code": res["smtp_code"],
                "status": f"Deliverable (250 OK - Format: {cand_label})",
                "badge": "🟢 Deliverable",
                "deliverable": True,
                "permutations_tested": tested_count,
                "details": f"Auto-discovered working format '{cand_label}' on test #{tested_count}/{len(candidates)}: {res['details']}",
                "response_time_ms": int((time.time() - start_all) * 1000)
            }
            
        # If DNS MX completely failed, stop testing further permutations
        if "No MX" in res.get("status", "") or "Domain Not Found" in res.get("status", ""):
            break

    # If all permutations failed:
    return {
        "email": clean_orig,
        "original_email": clean_orig,
        "winning_pattern": "none",
        "domain": last_res["domain"] if last_res else clean_orig.split("@")[1],
        "mx_host": last_res["mx_host"] if last_res else "None",
        "smtp_code": last_res["smtp_code"] if last_res else 550,
        "status": f"Undeliverable (All {tested_count} Formats Failed)",
        "badge": f"🔴 Undeliverable ({tested_count} Failed)",
        "deliverable": False,
        "permutations_tested": tested_count,
        "details": f"Tested {tested_count} candidate formats ({', '.join([c[1] for c in candidates[:4]])}...) — all rejected with 550 / mailbox not found.",
        "response_time_ms": int((time.time() - start_all) * 1000)
    }


class LocalEnrichmentHandler(http.server.BaseHTTPRequestHandler):
    """Embedded HTTP REST endpoint for server-side /api/enrich queries."""
    def log_message(self, format, *args):
        pass  # Quiet HTTP server logging

    def do_POST(self):
        if self.path == "/api/enrich":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode('utf-8'))
                full_name = data.get("full_name") or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                lead_in = {
                    "Name": full_name,
                    "First Name": data.get("first_name", ""),
                    "Last Name": data.get("last_name", ""),
                    "Headline / Role": data.get("headline", "") or data.get("job_title", ""),
                    "Organisation": data.get("organisation", "") or data.get("organization", ""),
                    "Domain": data.get("domain", ""),
                    "Snippet": data.get("snippet", "")
                }
                res = api_enrich_lead(
                    lead_in,
                    provider=data.get("provider", "builtin"),
                    api_key=data.get("api_key", ""),
                    pattern=data.get("pattern", "{first}.{last}@{domain}"),
                    industry=data.get("industry", "fire"),
                    custom_domain=data.get("custom_domain", "")
                )
                response_data = {
                    "status": "success",
                    "result": {
                        "first_name": res["First Name"],
                        "last_name": res["Last Name"],
                        "full_name": full_name,
                        "organisation": lead_in["Organisation"],
                        "domain": res["Domain"],
                        "enriched_email": res["Enriched Email"],
                        "deliverability": res["Deliverability"],
                        "deliverability_badge": res["Deliverability Badge"],
                        "mx_server": res["MX Server"],
                        "confidence_score": res["Score"]
                    }
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            info = {
                "status": "running",
                "service": "Multi-Engine Lead & Email Enrichment API",
                "port": LOCAL_ENRICHMENT_PORT,
                "endpoints": ["/api/enrich", "/api/health"],
                "fire_services_registered": len(UK_FIRE_SERVICES_DOMAINS)
            }
            self.wfile.write(json.dumps(info).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


def start_local_enrichment_server(port=LOCAL_ENRICHMENT_PORT):
    """Starts the embedded /api/enrich HTTP server in a background daemon thread."""
    try:
        server = http.server.HTTPServer(("127.0.0.1", port), LocalEnrichmentHandler)
        server.serve_forever()
    except Exception:
        pass


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


def make_combobox_adaptive(combo: ttk.Combobox):
    """
    Dynamically expands the popdown dropdown listbox width of a ttk.Combobox so that
    long options, presets, queries, and descriptions are 100% visible without text truncation.
    """
    def _adjust(event=None):
        try:
            vals = combo['values']
            if not vals:
                return
            max_len = max(len(str(v)) for v in vals)
            target_char_w = max(int(combo.cget("width")), max_len + 4)
            popdown_path = combo.tk.eval(f"ttk::combobox::PopdownWindow {combo}")
            listbox_path = f"{popdown_path}.f.l"
            combo.tk.call(listbox_path, "configure", "-width", target_char_w)
        except Exception:
            pass

    combo.bind("<ButtonPress-1>", _adjust, add="+")
    combo.bind("<Down>", _adjust, add="+")
    combo.bind("<Key-F4>", _adjust, add="+")
    
    try:
        existing_post = combo.cget("postcommand")
        if existing_post:
            def _chained():
                _adjust()
                if callable(existing_post):
                    existing_post()
                elif isinstance(existing_post, str) and existing_post:
                    combo.tk.eval(existing_post)
            combo.configure(postcommand=_chained)
        else:
            combo.configure(postcommand=_adjust)
    except Exception:
        pass
        
    return combo


class ToolTip:
    """
    Modern, adaptable, screen-boundary-aware hover tooltip helper for Tkinter widgets.
    Dynamically calculates wraplength and clamps/inverts coordinates so text is never cut off.
    """
    def __init__(self, widget, text, delay=220):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip_window = None
        self.schedule_id = None
        
        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")
        self.widget.bind("<Destroy>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        self._cancel_schedule()
        self.schedule_id = self.widget.after(self.delay, self._show_tip)

    def _on_leave(self, event=None):
        self._cancel_schedule()
        self._hide_tip()

    def _cancel_schedule(self):
        if self.schedule_id:
            try:
                self.widget.after_cancel(self.schedule_id)
            except Exception:
                pass
            self.schedule_id = None

    def _show_tip(self):
        if self.tip_window or not self.text:
            return
        tip_text = self.text() if callable(self.text) else str(self.text)
        if not tip_text.strip():
            return
            
        try:
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.attributes("-topmost", True)
            try:
                tw.attributes("-alpha", 0.98)
            except Exception:
                pass
            
            # High-contrast slate card with subtle border
            border_frame = tk.Frame(tw, background="#334155", borderwidth=1, relief=tk.SOLID)
            border_frame.pack(fill=tk.BOTH, expand=True)
            
            screen_w = tw.winfo_screenwidth()
            screen_h = tw.winfo_screenheight()
            
            t_len = len(tip_text)
            if t_len < 60:
                wrap_w = 300
            elif t_len < 160:
                wrap_w = 400
            elif t_len < 350:
                wrap_w = 520
            else:
                wrap_w = min(620, max(380, screen_w - 80))
                
            lbl = tk.Label(
                border_frame,
                text=tip_text,
                justify=tk.LEFT,
                background="#0F172A",
                foreground="#F8FAFC",
                font=("Segoe UI", 9),
                padx=10,
                pady=6,
                wraplength=wrap_w
            )
            lbl.pack(fill=tk.BOTH, expand=True)
            
            tw.update_idletasks()
            req_w = tw.winfo_reqwidth()
            req_h = tw.winfo_reqheight()
            
            # Position relative to target widget
            x = self.widget.winfo_rootx() + 10
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            
            # Position safely relative to parent window bounds (works seamlessly across multi-monitors)
            try:
                top = self.widget.winfo_toplevel()
                top_r = top.winfo_rootx() + top.winfo_width()
                if x + req_w > top_r - 10:
                    x = max(top.winfo_rootx() + 10, top_r - req_w - 10)
                top_b = top.winfo_rooty() + top.winfo_height()
                if y + req_h > top_b - 10:
                    y = max(top.winfo_rooty() + 10, self.widget.winfo_rooty() - req_h - 6)
            except Exception:
                pass
                
            tw.wm_geometry(f"{req_w}x{req_h}+{int(x)}+{int(y)}")
            tw.lift()
        except Exception:
            self._hide_tip()

    def _hide_tip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            try:
                tw.destroy()
            except Exception:
                pass


class TreeviewHoverToolTip:
    """
    Displays an adaptive tooltip preview for Treeview rows on mouse hover
    to reveal full, untruncated content, emails, phone numbers, and status logs.
    """
    def __init__(self, tree, get_tooltip_text_fn, delay=350):
        self.tree = tree
        self.get_text_fn = get_tooltip_text_fn
        self.delay = delay
        self.tip_window = None
        self.schedule_id = None
        self.last_item = None
        
        self.tree.bind("<Motion>", self._on_motion, add="+")
        self.tree.bind("<Leave>", self._on_leave, add="+")
        self.tree.bind("<ButtonPress>", self._on_leave, add="+")
        self.tree.bind("<MouseWheel>", self._on_leave, add="+")

    def _on_motion(self, event):
        item = self.tree.identify_row(event.y)
        if not item or item != self.last_item:
            self._cancel_schedule()
            self._hide_tip()
            self.last_item = item
            if item:
                self.schedule_id = self.tree.after(self.delay, lambda: self._show_tip(item, event.x_root, event.y_root))

    def _on_leave(self, event=None):
        self._cancel_schedule()
        self._hide_tip()
        self.last_item = None

    def _cancel_schedule(self):
        if self.schedule_id:
            try:
                self.tree.after_cancel(self.schedule_id)
            except Exception:
                pass
            self.schedule_id = None

    def _show_tip(self, item, mouse_x, mouse_y):
        if self.tip_window or not item:
            return
        tip_text = self.get_text_fn(item)
        if not tip_text or not str(tip_text).strip():
            return
            
        try:
            tw = tk.Toplevel(self.tree)
            self.tip_window = tw
            tw.wm_overrideredirect(True)
            tw.attributes("-topmost", True)
            try:
                tw.attributes("-alpha", 0.98)
            except Exception:
                pass
                
            border = tk.Frame(tw, background="#334155", borderwidth=1, relief=tk.SOLID)
            border.pack(fill=tk.BOTH, expand=True)
            
            wrap_w = 540
            lbl = tk.Label(
                border,
                text=str(tip_text).strip(),
                justify=tk.LEFT,
                background="#0F172A",
                foreground="#F8FAFC",
                font=("Segoe UI", 9),
                padx=10,
                pady=7,
                wraplength=wrap_w
            )
            lbl.pack(fill=tk.BOTH, expand=True)
            
            tw.update_idletasks()
            req_w = tw.winfo_reqwidth()
            req_h = tw.winfo_reqheight()
            
            x = mouse_x + 14
            y = mouse_y + 16
            
            # Position safely relative to parent window bounds
            try:
                top = self.tree.winfo_toplevel()
                top_r = top.winfo_rootx() + top.winfo_width()
                if x + req_w > top_r - 10:
                    x = max(top.winfo_rootx() + 10, top_r - req_w - 10)
                top_b = top.winfo_rooty() + top.winfo_height()
                if y + req_h > top_b - 10:
                    y = max(top.winfo_rooty() + 10, mouse_y - req_h - 10)
            except Exception:
                pass
                
            tw.wm_geometry(f"{req_w}x{req_h}+{int(x)}+{int(y)}")
            tw.lift()
        except Exception:
            self._hide_tip()

    def _hide_tip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            try:
                tw.destroy()
            except Exception:
                pass



class GoogleLeadScraperSuite(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Multi-Engine Lead & Advanced Dork Extractor Suite")
        
        # Adaptive screen geometry sizing (fits any screen resolution / DPI scaling)
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            init_w = min(1200, max(920, screen_w - 60))
            init_h = min(860, max(600, screen_h - 90))
            self.geometry(f"{init_w}x{init_h}")
        except Exception:
            self.geometry("1160x820")
        self.minsize(800, 500)
        
        # Application State
        self.is_running = False
        self.stop_requested = False
        self.results_data = []  # list of lead dicts
        self.driver = None
        self._updating_query = False
        self.search_history = self._load_search_history()
        
        # Search Criteria Strategy State (targeted vs generalized)
        self.active_criteria_mode = "targeted"
        
        # Generalized Multi-Group Boolean Search Criteria State
        self.gen_industry_var = tk.StringVar(value="")
        self.gen_scale_var = tk.StringVar(value="")
        self.gen_geo_var = tk.StringVar(value="")
        self.gen_exclude_var = tk.StringVar(value="")
        self.gen_intext_var = tk.StringVar(value="")
        self.gen_inurl_var = tk.StringVar(value="")
        self.gen_filetype_var = tk.StringVar(value="None")
        self.gen_site_var = tk.StringVar(value="")
        self.gen_email_dork_var = tk.BooleanVar(value=False)
        self.gen_phone_dork_var = tk.BooleanVar(value=False)
        
        # Enrichment Configuration State
        self.enrich_industry_var = tk.StringVar(value="fire")
        self.enrich_pattern_var = tk.StringVar(value="{first}.{last}@{domain}")
        self.enrich_provider_var = tk.StringVar(value="builtin")
        self.enrich_api_key_var = tk.StringVar(value="")
        self.enrich_custom_domain_var = tk.StringVar(value="")
        self.is_enriching = False

        # Sorting & Categorisation Filter State
        self.sort_column = None
        self.sort_reverse = False
        self.filter_company_var = tk.StringVar(value="(All Organisations)")
        self.filter_status_var = tk.StringVar(value="(All Statuses)")

        # Email & CSV Verifier State
        self.verifier_data = []           # List of dicts for verification
        self.verifier_raw_rows = []       # Original CSV rows for preserving columns
        self.verifier_csv_fieldnames = [] # Original CSV fieldnames
        self.verifier_is_running = False
        self.verifier_stop_requested = False
        self.verifier_sort_col = None
        self.verifier_sort_rev = False
        self.verifier_input_mode = tk.StringVar(value="csv")
        self.verifier_csv_path_var = tk.StringVar(value="")
        self.verifier_selected_col_var = tk.StringVar(value="")
        self.verifier_timeout_var = tk.IntVar(value=8)
        self.verifier_catchall_var = tk.BooleanVar(value=False)
        self.verifier_waterfall_var = tk.BooleanVar(value=True)
        self.verifier_filter_var = tk.StringVar(value="")

        # Direct Open Data & Public Registry State
        self.opendata_sources = load_registry_sources()
        self.opendata_selected_var = tk.StringVar(value=self.opendata_sources[0]["name"] if self.opendata_sources else "")
        self.opendata_url_var = tk.StringVar(value=self.opendata_sources[0]["url"] if self.opendata_sources else "")
        self.opendata_name_var = tk.StringVar(value=self.opendata_sources[0]["name"] if self.opendata_sources else "")
        self.opendata_filter_var = tk.StringVar(value="")
        self.opendata_max_rows_var = tk.IntVar(value=500)
        self.opendata_raw_records = []
        self.opendata_headers = []
        self.opendata_filtered_records = []
        self.opendata_is_fetching = False
        self.opendata_stop_requested = False
        self.opendata_sort_col = None
        self.opendata_sort_rev = False

        # Start Local Enrichment REST Server in background thread
        threading.Thread(target=start_local_enrichment_server, daemon=True).start()

        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Global auto-adapt hooks for all Combobox dropdown lists across the app
        def _global_combobox_adapt_hook(event):
            try:
                w = event.widget
                vals = w['values']
                if vals:
                    max_len = max(len(str(v)) for v in vals)
                    target_w = max(int(w.cget('width')), max_len + 4)
                    popdown = w.tk.eval(f"ttk::combobox::PopdownWindow {w}")
                    listbox = f"{popdown}.f.l"
                    w.tk.call(listbox, "configure", "-width", target_w)
            except Exception:
                pass

        self.bind_class("TCombobox", "<ButtonPress-1>", _global_combobox_adapt_hook, add="+")
        self.bind_class("TCombobox", "<Down>", _global_combobox_adapt_hook, add="+")
        self.bind_class("TCombobox", "<Key-F4>", _global_combobox_adapt_hook, add="+")
        
        self._setup_styles()
        self._build_ui()
        self._reset_builder()  # Start with completely clean/empty textboxes (no hardcoded defaults)
        
    def _setup_styles(self):
        self.configure(bg="#F1F5F9")
        self.style = ttk.Style(self)
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")
            
        # Ensure Tcl combobox popdown placement engine dynamically resizes to fit full text strings
        try:
            self.tk.eval("""
proc ::ttk::combobox::PlacePopdown {cb popdown} {
    set x [winfo rootx $cb]
    set y [winfo rooty $cb]
    set w [winfo width $cb]
    set h [winfo height $cb]
    set style [$cb cget -style]
    set postoffset [ttk::style lookup $style -postoffset {} {0 0 0 0}]
    foreach var {x y w h} delta $postoffset {
    	incr $var $delta
    }

    # Automatically widen listbox to fit longest value
    set values [$cb cget -values]
    set maxLen 0
    foreach v $values {
        set vLen [string length $v]
        if {$vLen > $maxLen} {
            set maxLen $vLen
        }
    }
    set cbWidth [$cb cget -width]
    if {$maxLen > $cbWidth} {
        $popdown.f.l configure -width [expr {$maxLen + 4}]
    }

    update idletasks
    set H [winfo reqheight $popdown]
    set reqW [winfo reqwidth $popdown]
    if {$reqW > $w} {
        set w $reqW
    }

    # Position directly below the combobox at its exact root coordinates on the current screen/monitor
    set Y [expr {$y + $h}]

    wm geometry $popdown ${w}x${H}+${x}+${Y}
}
""")
        except Exception:
            pass

        # Base colors & Widget Font Options
        self.style.configure("TFrame", background="#F1F5F9")
        self.style.configure("TLabelframe", background="#F1F5F9")
        self.style.configure("TLabelframe.Label", background="#F1F5F9", foreground="#0F172A", font=("Segoe UI", 10, "bold"))
        self.style.configure("TLabel", background="#F1F5F9", foreground="#334155", font=("Segoe UI", 9))
        self.style.configure("TCheckbutton", background="#F1F5F9", foreground="#1E293B", font=("Segoe UI", 9))
        self.style.configure("TRadiobutton", background="#F1F5F9", foreground="#1E293B", font=("Segoe UI", 9))
        self.style.configure("TCombobox", font=("Segoe UI", 9))
        
        # Option Database settings to ensure Combobox Popdown listboxes are styled and fully readable
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 9))
        self.option_add("*ComboboxPopdown*Listbox.font", ("Segoe UI", 9))
        self.option_add("*TCombobox*Listbox.selectBackground", "#3B82F6")
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        self.option_add("*ComboboxPopdown*Listbox.selectBackground", "#3B82F6")
        self.option_add("*ComboboxPopdown*Listbox.selectForeground", "#FFFFFF")


        
        # Main Notebook (Tabs)
        self.style.configure("TNotebook", background="#E2E8F0", borderwidth=0)
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 9, "bold"), padding=[14, 7], background="#CBD5E1", foreground="#475569")
        self.style.map("TNotebook.Tab", 
                       background=[("selected", "#FFFFFF"), ("active", "#E2E8F0")], 
                       foreground=[("selected", "#2563EB"), ("active", "#0F172A")])
        
        # Sub-Notebook (Criteria Subtabs)
        self.style.configure("Sub.TNotebook", background="#F1F5F9", borderwidth=0)
        self.style.configure("Sub.TNotebook.Tab", font=("Segoe UI", 9, "bold"), padding=[12, 6], background="#E2E8F0", foreground="#475569")
        self.style.map("Sub.TNotebook.Tab", 
                       background=[("selected", "#FFFFFF"), ("active", "#F8FAFC")], 
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

        # Recalled Query Feedback Styles
        self.style.configure("RecalledSuccess.TEntry", fieldbackground="#DCFCE7", foreground="#065F46")
        self.style.configure("RecalledNotice.TLabel", font=("Segoe UI", 9, "bold"), foreground="#059669", background="#F1F5F9")

    def _build_ui(self):
        # --- Native Application Menu Bar ---
        menubar = tk.Menu(self)
        
        # 1. File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="💾 Export Enriched Leads CSV (Tab 2)", command=self._save_to_enriched_csv)
        file_menu.add_command(label="🛡️ Export Verified CSV (Tab 3)", command=self._export_verified_csv)
        file_menu.add_command(label="📥 Export Open Data CSV (Tab 4)", command=self._export_opendata_csv)
        file_menu.add_separator()
        file_menu.add_command(label="🔄 Reset All Search Criteria", command=self._reset_builder)
        file_menu.add_command(label="🗑️ Clear Results Table", command=self._clear_results)
        file_menu.add_separator()
        file_menu.add_command(label="❌ Exit", command=self._on_closing)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # 2. Templates Menu (Organized by Strategy & Industry Risk)
        templates_menu = tk.Menu(menubar, tearoff=0)
        
        # Sub-Menu: 🔥 High Fire & Smoke Risk Multi-Site Industries
        fire_risk_menu = tk.Menu(templates_menu, tearoff=0)
        fire_risk_menu.add_command(label="♻️ Materials Recovery & Waste Facilities", command=lambda: self._load_preset("gen_waste"))
        fire_risk_menu.add_command(label="🧴 Plastics Recycling & Polymer Reprocessing", command=lambda: self._load_preset("gen_plastics"))
        fire_risk_menu.add_command(label="🪵 Wood, Timber & Paper Recycling", command=lambda: self._load_preset("gen_wood_paper"))
        fire_risk_menu.add_command(label="🌾 Farms, Agriculture & Grain Silos", command=lambda: self._load_preset("gen_farms"))
        fire_risk_menu.add_command(label="📦 Warehouse Management & 3PL Logistics", command=lambda: self._load_preset("gen_warehouses"))
        fire_risk_menu.add_command(label="🏗️ Outside Storage & Open Yard Storage", command=lambda: self._load_preset("gen_outside_storage"))
        fire_risk_menu.add_command(label="🛞 Tyre Recycling & Rubber Pyrolysis", command=lambda: self._load_preset("gen_tyres"))
        fire_risk_menu.add_command(label="🔋 Battery Storage (BESS) & Lithium-Ion", command=lambda: self._load_preset("gen_batteries"))
        fire_risk_menu.add_command(label="🧵 Textiles, Fabric & Rag Baling", command=lambda: self._load_preset("gen_textiles"))
        fire_risk_menu.add_command(label="🌾 Food Processing, Mills & Bakeries (Dust)", command=lambda: self._load_preset("gen_food_mills"))
        fire_risk_menu.add_command(label="🛢️ Chemical & Hazmat Storage (COMAH)", command=lambda: self._load_preset("gen_chemical"))
        fire_risk_menu.add_command(label="🚗 Metal Scrap & Vehicle Dismantlers (ATF)", command=lambda: self._load_preset("gen_scrap"))
        fire_risk_menu.add_command(label="🚛 Transport & Fleet Operating Depots", command=lambda: self._load_preset("gen_fleet"))
        fire_risk_menu.add_command(label="🏭 Manufacturing & Industrial Processing", command=lambda: self._load_preset("gen_manufacturing"))
        fire_risk_menu.add_command(label="⚡ Energy, Biomass & EfW Plants", command=lambda: self._load_preset("gen_energy"))
        fire_risk_menu.add_command(label="🖥️ Data Centers & Colocation Infrastructure", command=lambda: self._load_preset("gen_datacenters"))
        templates_menu.add_cascade(label="🔥 High Fire & Smoke Hazard Industries", menu=fire_risk_menu)
        
        # Sub-Menu: ♻️ UK Environmental Registers (EA / SEPA / NRW)
        env_menu = tk.Menu(templates_menu, tearoff=0)
        env_menu.add_command(label="🏴󠁧󠁢󠁥󠁮󠁧󠁿 EA: Waste Permitting & Operations (England)", command=lambda: self._load_preset("ea_waste_ops"))
        env_menu.add_command(label="🏴󠁧󠁢󠁥󠁮󠁧󠁿 EA: Waste Carriers, Brokers & Dealers", command=lambda: self._load_preset("ea_waste_carriers"))
        env_menu.add_command(label="🏴󠁧󠁢󠁳󠁣󠁴󠁿 SEPA: Waste Carriers & Authorisations (Scotland)", command=lambda: self._load_preset("sepa_waste"))
        env_menu.add_command(label="🏴󠁧󠁢󠁷󠁬󠁳󠁿 NRW: Waste Permitting & Carriers (Wales)", command=lambda: self._load_preset("nrw_waste"))
        env_menu.add_command(label="🇬🇧 Combined UK Regulators (EA / SEPA / NRW)", command=lambda: self._load_preset("combined_uk_env_registers"))
        templates_menu.add_cascade(label="♻️ UK Environmental Registers", menu=env_menu)
        
        # Sub-Menu: 🛣️ National Highways & Road Network
        highways_menu = tk.Menu(templates_menu, tearoff=0)
        highways_menu.add_command(label="🛣️ National Highways Leaders & Project Directors", command=lambda: self._load_preset("national_highways_leaders"))
        highways_menu.add_command(label="🛣️ National Highways: Schemes, Tenders & Contacts", command=lambda: self._load_preset("national_highways_gov"))
        highways_menu.add_command(label="🛣️ National Highways & Road Network Depots", command=lambda: self._load_preset("gen_highways"))
        templates_menu.add_cascade(label="🛣️ National Highways & Roads", menu=highways_menu)
        
        # Sub-Menu: 🎯 Targeted Profile & Lead Searches
        leads_menu = tk.Menu(templates_menu, tearoff=0)
        leads_menu.add_command(label="🔥 Fire & Rescue IT Leaders (UK)", command=lambda: self._load_preset("fire_it"))
        leads_menu.add_command(label="🏥 NHS & Healthcare IT Heads", command=lambda: self._load_preset("nhs_it"))
        leads_menu.add_command(label="🏛️ Local Council & Gov IT Directors", command=lambda: self._load_preset("gov_it"))
        leads_menu.add_command(label="🚀 Tech Startup Founders / CTOs", command=lambda: self._load_preset("tech_founders"))
        leads_menu.add_command(label="📦 Procurement & Supply Chain Heads", command=lambda: self._load_preset("procurement"))
        leads_menu.add_command(label="📧 Public Email Hunter (@gmail/@outlook)", command=lambda: self._load_preset("email_hunter"))
        templates_menu.add_cascade(label="🎯 Targeted Profile & Lead Searches", menu=leads_menu)
        
        templates_menu.add_separator()
        templates_menu.add_command(label="🔄 Reset to Blank Form", command=self._reset_builder)
        menubar.add_cascade(label="Templates", menu=templates_menu)

        # 3. Tools Menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="🔑 Log in to Google (CAPTCHA Bypass)", command=self._open_google_login)
        tools_menu.add_command(label="⚡ Batch Enrich Leads (Tab 2)", command=self._start_batch_enrich)
        tools_menu.add_command(label="🔄 Reformat & Retry Studio (Tab 3)", command=lambda: self._open_reformat_retry_window("undeliverables"))
        tools_menu.add_command(label="⚙️ Enrichment Settings", command=self._open_enrichment_settings)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # 4. Help Menu (User Guide & Walkthroughs)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="📖 Complete Beginner's User Guide (In-App Reader)...", command=self._open_user_guide_dialog)
        help_menu.add_command(label="🌐 Open USER_GUIDE.md in Default Viewer", command=self._open_user_guide_external)
        help_menu.add_command(label="📄 Open README.md in Default Viewer", command=self._open_readme_external)
        help_menu.add_separator()
        help_menu.add_command(label="⚡ Quick Start 4-Step Walkthrough", command=self._show_quick_start_dialog)
        help_menu.add_command(label="🛡️ Deliverability Badges & SMTP Guide", command=self._show_deliverability_guide)
        help_menu.add_command(label="📥 Direct Open Data & Public Registers Guide", command=self._show_opendata_guide)
        help_menu.add_separator()
        help_menu.add_command(label="ℹ️ About Suite", command=self._show_about_dialog)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- Top Banner ---
        top_banner = ttk.Frame(main_frame)
        top_banner.pack(fill=tk.X, pady=(0, 8))
        
        banner_left = ttk.Frame(top_banner)
        banner_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        title_lbl = ttk.Label(banner_left, text="⚡ Multi-Engine Lead & Advanced Dork Suite", style="Header.TLabel")
        title_lbl.pack(anchor=tk.W)
        sub_lbl = ttk.Label(banner_left, text="Search Google, Bing, DuckDuckGo, Brave, Yahoo, Tor/Onion with precision Dorks, extract contacts, and export with 1 click.", style="SubHeader.TLabel")
        sub_lbl.pack(anchor=tk.W)
        
        # Top Banner Quick Action Buttons (Always visible across all tabs and screen sizes)
        banner_right = ttk.Frame(top_banner)
        banner_right.pack(side=tk.RIGHT)
        
        self.top_search_btn = ttk.Button(banner_right, text="🚀 Search Leads", style="Success.TButton", command=self._start_search)
        self.top_search_btn.pack(side=tk.RIGHT, padx=(0, 6))
        ToolTip(self.top_search_btn, "Executes the search query and begins lead extraction immediately.")
        
        self.top_stop_btn = ttk.Button(banner_right, text="⏹ Stop", style="Danger.TButton", command=self._stop_search, state=tk.DISABLED)
        self.top_stop_btn.pack(side=tk.RIGHT, padx=(0, 6))
        ToolTip(self.top_stop_btn, "Stops the active search operation.")
        
        btn_guide = ttk.Button(banner_right, text="📖 User Guide", style="Primary.TButton", command=self._open_user_guide_dialog)
        btn_guide.pack(side=tk.RIGHT, padx=(0, 4))
        ToolTip(btn_guide, "Open the complete interactive beginner's guide, dummy-proof walkthrough, and search strategies.")

        # --- Main Notebook (Tabs) ---
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        # Tab 1: Interactive Query Builder
        self.tab_builder = ttk.Frame(self.notebook, padding="2")
        self.notebook.add(self.tab_builder, text=" 🛠️ Query Builder & Presets ")
        self._build_tab_builder()
        
        # Tab 2: Results & Extractor Output
        self.tab_results = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.tab_results, text=" 📋 Extracted Results & Text Box ")
        self._build_tab_results()
        
        # Tab 3: Email & CSV Verifier (MX & SMTP Handshake)
        self.tab_verifier = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.tab_verifier, text=" 🛡️ Email & CSV Verifier (MX/SMTP) ")
        self._build_tab_verifier()
        
        # Tab 4: Direct Open Data & Public Registers (CSV/ZIP/Directories)
        self.tab_opendata = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.tab_opendata, text=" 📥 Direct Open Data & Public Registers ")
        self._build_tab_opendata()
        
        # Tab 5: Search Operators Cheat Sheet
        self.tab_cheatsheet = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.tab_cheatsheet, text=" 📖 Search Operators Cheat Sheet ")
        self._build_tab_cheatsheet()
        
        # Tab 6: Search Query History Log
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
        # Scrollable container for Query Builder & Presets tab (Adapts to any screen resolution / window maximize)
        self.builder_canvas = tk.Canvas(self.tab_builder, bg="#F1F5F9", highlightthickness=0)
        self.builder_scrollbar = ttk.Scrollbar(self.tab_builder, orient="vertical", command=self.builder_canvas.yview)
        self.builder_scroll_frame = ttk.Frame(self.builder_canvas, padding="6")
        
        self.builder_scroll_frame.bind(
            "<Configure>",
            lambda e: self.builder_canvas.configure(scrollregion=self.builder_canvas.bbox("all"))
        )
        self.builder_canvas_win = self.builder_canvas.create_window((0, 0), window=self.builder_scroll_frame, anchor="nw")
        self.builder_canvas.configure(yscrollcommand=self.builder_scrollbar.set)
        
        # Auto-expand inner frame to match full canvas width when window is maximized or resized
        self.builder_canvas.bind("<Configure>", lambda e: self.builder_canvas.itemconfig(self.builder_canvas_win, width=e.width))
        
        self.builder_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.builder_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Smooth Mouse Wheel scrolling handlers
        def _on_builder_mousewheel(event):
            try:
                if event.delta:
                    self.builder_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                elif event.num == 4:
                    self.builder_canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.builder_canvas.yview_scroll(1, "units")
            except Exception:
                pass

        def _bind_builder_mousewheel(event=None):
            self.builder_canvas.bind_all("<MouseWheel>", _on_builder_mousewheel)
            self.builder_canvas.bind_all("<Button-4>", _on_builder_mousewheel)
            self.builder_canvas.bind_all("<Button-5>", _on_builder_mousewheel)

        def _unbind_builder_mousewheel(event=None):
            self.builder_canvas.unbind_all("<MouseWheel>")
            self.builder_canvas.unbind_all("<Button-4>")
            self.builder_canvas.unbind_all("<Button-5>")

        self.builder_canvas.bind("<Enter>", _bind_builder_mousewheel)
        self.builder_canvas.bind("<Leave>", _unbind_builder_mousewheel)
        self.builder_scroll_frame.bind("<Enter>", _bind_builder_mousewheel)
        self.builder_scroll_frame.bind("<Leave>", _unbind_builder_mousewheel)

        # 1. Search Engine & History Row
        engine_preset_frame = ttk.LabelFrame(self.builder_scroll_frame, text=" 🌐 Search Engine & Template Selector ", padding="8")
        engine_preset_frame.pack(fill=tk.X, pady=(0, 6))
        
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
        
        hl_pre = self._create_help_label(r_pre, "Load Template:", "Pre-configured industry search templates (Targeted Profile Searches & Generalized Facility Queries).")
        hl_pre.pack(side=tk.LEFT)
        
        self.preset_var = tk.StringVar(value="custom")
        presets = [
            ("-- Clean / Blank Form --", "custom"),
            ("--- 🔥 HIGH FIRE & SMOKE HAZARD MULTI-SITE INDUSTRIES ---", "header_fire"),
            ("♻️ Materials Recovery & Waste Facilities (UK)", "gen_waste"),
            ("🧴 Plastics Recycling & Polymer Reprocessing", "gen_plastics"),
            ("🪵 Wood, Timber & Paper Recycling", "gen_wood_paper"),
            ("🌾 Farms, Agriculture & Grain Silos", "gen_farms"),
            ("📦 Warehouse Management & 3PL Logistics", "gen_warehouses"),
            ("🏗️ Outside Storage & Open Yard Storage", "gen_outside_storage"),
            ("🛞 Tyre Recycling & Rubber Pyrolysis", "gen_tyres"),
            ("🔋 Battery Storage (BESS) & Lithium-Ion", "gen_batteries"),
            ("🧵 Textiles, Fabric & Rag Baling", "gen_textiles"),
            ("🌾 Food Processing, Mills & Bakeries (Dust)", "gen_food_mills"),
            ("🛢️ Chemical & Hazmat Storage (COMAH)", "gen_chemical"),
            ("🚗 Metal Scrap & Vehicle Dismantlers (ATF)", "gen_scrap"),
            ("🚛 Commercial Transport & Fleet Depots", "gen_fleet"),
            ("🏭 Manufacturing & Industrial Processing", "gen_manufacturing"),
            ("⚡ Energy, Biomass & EfW Plants", "gen_energy"),
            ("🖥️ Data Centers & Colocation Infrastructure", "gen_datacenters"),
            ("--- ♻️ UK ENVIRONMENTAL REGISTERS (EA / SEPA / NRW) ---", "header_env"),
            ("🏴󠁧󠁢󠁥󠁮󠁧󠁿 EA: Waste Permitting & Operations (England)", "ea_waste_ops"),
            ("🏴󠁧󠁢󠁥󠁮󠁧󠁿 EA: Waste Carriers, Brokers & Dealers", "ea_waste_carriers"),
            ("🏴󠁧󠁢󠁳󠁣󠁴󠁿 SEPA: Waste Carriers & Authorisations (Scotland)", "sepa_waste"),
            ("🏴󠁧󠁢󠁷󠁬󠁳󠁿 NRW: Waste Permitting & Carriers (Wales)", "nrw_waste"),
            ("🇬🇧 Combined UK Regulators (EA / SEPA / NRW)", "combined_uk_env_registers"),
            ("🛣️ National Highways Leaders & Project Directors (UK)", "national_highways_leaders"),
            ("🛣️ National Highways: Schemes, Tenders & Contacts", "national_highways_gov"),
            ("🛣️ National Highways & Road Network Depots (UK)", "gen_highways"),
            ("--- 🎯 TARGETED PROFILE / LEAD TEMPLATES ---", "header1"),
            ("🔥 Fire & Rescue IT Leaders (UK)", "fire_it"),
            ("🏥 NHS & Healthcare IT Heads", "nhs_it"),
            ("🏛️ Local Council & Gov IT Directors", "gov_it"),
            ("🚀 Tech Startup Founders / CTOs", "tech_founders"),
            ("📦 Procurement & Supply Chain Heads", "procurement"),
            ("📧 Public Email Hunter (@gmail/@outlook)", "email_hunter"),
            ("💻 Developer Code Solutions (StackOverflow/GitHub)", "dev_code"),
            ("📚 Recent Tech Tutorials (after:2023)", "recent_tutorials"),
            ("📄 Official Documentation (MDN/Microsoft)", "official_docs"),
            ("📂 Open Directory Search (Index of /)", "index_of"),
            ("🔒 Confidential Salary & Budgets", "confidential_docs"),
            ("⚙️ Server Configs & Exposed FTP", "server_configs"),
            ("💲 Price/Number Range ($100..$500)", "number_range"),
            ("📑 PDF Resumes & CVs", "resumes")
        ]
        
        self.preset_combo = ttk.Combobox(r_pre, values=[p[0] for p in presets], state="readonly", width=48)
        self.preset_combo.current(0)
        self.preset_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)
        
        load_btn = ttk.Button(r_pre, text="Apply Template", style="Secondary.TButton", command=lambda: self._on_preset_selected(None))
        load_btn.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(load_btn, "Loads selected template parameters into the builder form below.")
        
        # History recall dropdown
        hist_lbl = ttk.Label(r_pre, text="📜 Recall Past Query:", style="Section.TLabel")
        hist_lbl.pack(side=tk.LEFT, padx=(5, 4))
        
        self.history_combo = ttk.Combobox(r_pre, state="readonly", width=36)
        self._refresh_history_combo()
        self.history_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.history_combo.bind("<<ComboboxSelected>>", self._on_history_combo_selected)
        ToolTip(self.history_combo, "Select any past logged search query to recall it directly into the builder.")

        # 2. Builder Form Panes - Tabbed Criteria Selector
        self.criteria_frame = ttk.LabelFrame(self.builder_scroll_frame, text=" 🎯 Search Criteria & Strategy Selector ", padding="6")
        self.criteria_frame.pack(fill=tk.X, pady=(0, 6))
        
        self.criteria_notebook = ttk.Notebook(self.criteria_frame, style="Sub.TNotebook")
        self.criteria_notebook.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Sub-Tab 1: Targeted Site & Profile Search
        self.subtab_targeted = ttk.Frame(self.criteria_notebook, padding="6")
        self.criteria_notebook.add(self.subtab_targeted, text=" 🎯 Tab 1: Targeted Site & Profile Search (site:) ")
        self._build_subtab_targeted()
        
        # Sub-Tab 2: Generalized Industry & Facility Search
        self.subtab_generalized = ttk.Frame(self.criteria_notebook, padding="6")
        self.criteria_notebook.add(self.subtab_generalized, text=" 🌐 Tab 2: Generalized Industry & Facility Search (Multi-Group Boolean) ")
        self._build_subtab_generalized()
        
        self.criteria_notebook.bind("<<NotebookTabChanged>>", self._on_criteria_tab_changed)

        # 3. Live Assembled Dork Preview Box
        query_preview_frame = ttk.LabelFrame(self.builder_scroll_frame, text=" Live Assembled Search Query (Auto-Generated) ", padding="8")
        query_preview_frame.pack(fill=tk.X, pady=(0, 6))
        
        self.assembled_query_var = tk.StringVar()
        self.query_preview_entry = ttk.Entry(query_preview_frame, textvariable=self.assembled_query_var, font=("Consolas", 10, "bold"), foreground="#1E293B")
        self.query_preview_entry.pack(fill=tk.X, pady=(0, 4))
        self.query_preview_entry.bind("<Return>", lambda event: self._start_search())
        ToolTip(self.query_preview_entry, "This query updates in real-time as you edit form fields above. You can also edit it directly here.")
        
        self.recalled_notice_lbl = ttk.Label(query_preview_frame, text="", style="RecalledNotice.TLabel")
        self.recalled_notice_lbl.pack(anchor=tk.W, pady=(0, 4))
        
        preview_btn_bar = ttk.Frame(query_preview_frame)
        preview_btn_bar.pack(fill=tk.X)
        
        btn_copy_query = ttk.Button(preview_btn_bar, text="📋 Copy Query", style="Secondary.TButton", command=self._copy_query_to_clipboard)
        btn_copy_query.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(btn_copy_query, "Copies the complete assembled search string to clipboard.")
        
        btn_reset_query = ttk.Button(preview_btn_bar, text="🔄 Clear All Fields / Reset", style="Secondary.TButton", command=self._reset_builder)
        btn_reset_query.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(btn_reset_query, "Clears all textboxes and query fields back to a blank canvas.")
        
        lbl_hint_live = ttk.Label(preview_btn_bar, text="✨ Updates live as you change fields in either tab. You can also edit it directly in the text box above.", foreground="#64748B")
        lbl_hint_live.pack(side=tk.LEFT)
        
        # 4. Search Execution Controls
        exec_frame = ttk.LabelFrame(self.builder_scroll_frame, text=" Search Execution Controls ", padding="10")
        exec_frame.pack(fill=tk.X, pady=(0, 4))
        
        # Row 1: Parameters & Browser Window Mode
        r_params = ttk.Frame(exec_frame)
        r_params.pack(fill=tk.X, pady=(0, 4))
        
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
        
        # Row 2: Deep Extraction & Job Board Filter Options
        r_opts = ttk.Frame(exec_frame)
        r_opts.pack(fill=tk.X, pady=(2, 6))
        
        self.auto_scrape_site_var = tk.BooleanVar(value=True)
        chk_autocrawl = ttk.Checkbutton(r_opts, text="🌐 Auto-Crawl Website Contacts (Fetch real emails & phones from /contact pages)", variable=self.auto_scrape_site_var)
        chk_autocrawl.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(chk_autocrawl, "Automatically crawls /contact, /about, and /facilities pages on each discovered domain to extract verified real emails (e.g. enquiries@domain.co.uk) and telephone numbers.")
        
        self.exclude_job_boards_var = tk.BooleanVar(value=True)
        chk_no_jobs = ttk.Checkbutton(r_opts, text="🚫 Exclude Job Boards (Fish4, Indeed, Reed, Totaljobs, Vacancies)", variable=self.exclude_job_boards_var, command=self._rebuild_query)
        chk_no_jobs.pack(side=tk.LEFT)
        ToolTip(chk_no_jobs, "Excludes recruitment aggregator job boards (Fish4, Indeed, Reed, Totaljobs, etc.) so you only get actual commercial facilities and businesses.")

        # Row 3: Action Buttons
        r_actions = ttk.Frame(exec_frame)
        r_actions.pack(fill=tk.X, pady=(2, 0))
        
        self.search_btn = ttk.Button(r_actions, text="🚀 Search & Extract Leads", style="Primary.TButton", command=self._start_search)
        self.search_btn.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(self.search_btn, "Executes search on selected engine and extracts structured contact leads.")
        
        self.stop_btn = ttk.Button(r_actions, text="⏹ Stop Search", style="Danger.TButton", command=self._stop_search, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(self.stop_btn, "Stops the active search immediately.")
        
        hint_exec = ttk.Label(r_actions, text="💡 Live progress bar and search activity spinner will appear in the Results tab during extraction.", foreground="#64748B", font=("Segoe UI", 8, "italic"))
        hint_exec.pack(side=tk.LEFT)

    def _build_subtab_targeted(self):
        """Builds Tab 1 of Search Criteria: Single site/profile dorking parameters (LinkedIn, gov.uk, etc.)."""
        # Row 1: Target Platform / Site (MANUAL & PRESETS)
        r1 = ttk.Frame(self.subtab_targeted)
        r1.pack(fill=tk.X, pady=2)
        
        hl_site = self._create_help_label(r1, "Target Site (site:):", "Restricts results to a specific website or domain. Type any domain manually or pick from presets.")
        hl_site.pack(side=tk.LEFT)
        
        self.site_preset_var = tk.StringVar(value="")
        self.site_combo = ttk.Combobox(r1, textvariable=self.site_preset_var, width=32)
        self.site_combo['values'] = (
            "site:linkedin.com/in/",
            "site:linkedin.com/company/",
            "site:environment.data.gov.uk/public-register/",
            "site:sepa.org.uk",
            "site:naturalresources.wales",
            "(site:environment.data.gov.uk/public-register/ OR site:sepa.org.uk OR site:naturalresources.wales)",
            "site:nationalhighways.co.uk",
            "site:nationalhighways.co.uk OR site:highwaysengland.co.uk",
            "site:gov.uk",
            "site:github.com",
            "site:stackoverflow.com OR site:github.com",
            "site:twitter.com OR site:x.com",
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
        r2 = ttk.Frame(self.subtab_targeted)
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
        r3 = ttk.Frame(self.subtab_targeted)
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
        r4 = ttk.Frame(self.subtab_targeted)
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
        r5 = ttk.Frame(self.subtab_targeted)
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
        r6 = ttk.Frame(self.subtab_targeted)
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
        r7 = ttk.Frame(self.subtab_targeted)
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

    def _build_subtab_generalized(self):
        """Builds Tab 2 of Search Criteria: Generalized multi-group boolean query builder for facilities & industry."""
        # Strategy Intro & Quick Action Banner
        intro_frame = ttk.Frame(self.subtab_generalized)
        intro_frame.pack(fill=tk.X, pady=(0, 4))
        
        lbl_intro = ttk.Label(intro_frame, text="ℹ️ Strategy: Build broad multi-concept queries for facilities, depots, commercial sites & nationwide infrastructure with boolean OR groups and negative exclusions.", foreground="#475569", font=("Segoe UI", 8, "italic"))
        lbl_intro.pack(side=tk.LEFT)
        
        btn_quick_waste = ttk.Button(intro_frame, text="⭐ Load Waste & Facility Example", style="Accent.TButton", command=self._load_waste_facility_example)
        btn_quick_waste.pack(side=tk.RIGHT)
        ToolTip(btn_quick_waste, "Instantly loads the Materials Recovery & Waste Facilities search with multiple sites, UK regions, and council exclusions.")

        # Row 1: Facility / Industry / Sector Terms (Group 1 - OR)
        r1 = ttk.Frame(self.subtab_generalized)
        r1.pack(fill=tk.X, pady=2)
        
        hl_ind = self._create_help_label(r1, "Facility / Industry (OR):", "Group 1: Target facility types, industry activities, or site operations. Multiple terms are combined with OR.", width=21)
        hl_ind.pack(side=tk.LEFT)
        
        gen_ind_entry = ttk.Entry(r1, textvariable=self.gen_industry_var, font=("Segoe UI", 9), width=38)
        gen_ind_entry.pack(side=tk.LEFT, padx=(0, 6), fill=tk.X, expand=True)
        gen_ind_entry.bind("<KeyRelease>", lambda e: self._rebuild_query())
        ToolTip(gen_ind_entry, 'Enter facility/industry terms e.g. ("Materials Recovery Facility" OR "waste transfer station" OR "commercial recycling facility") or comma-separated.')
        
        self.gen_category_combo = ttk.Combobox(r1, values=[
            "Choose Preset Category...",
            "♻️ Materials Recovery & Waste Facilities",
            "🧴 Plastics Recycling & Polymer Processing",
            "🪵 Wood, Timber & Paper Recycling",
            "🌾 Farms, Agriculture & Grain Silos",
            "📦 Warehouse Management & 3PL Logistics",
            "🏗️ Outside Storage & Open Yard Storage",
            "🛞 Tyre Recycling & Rubber Pyrolysis",
            "🔋 Battery Storage (BESS) & Lithium-Ion",
            "🧵 Textiles, Fabric & Rag Baling",
            "🌾 Food Processing, Mills & Bakeries (Dust)",
            "🛢️ Chemical & Hazmat Storage (COMAH)",
            "🚗 Metal Scrap & Vehicle Dismantlers (ATF)",
            "🚛 Transport & Fleet Operating Depots",
            "🏭 Industrial Manufacturing & Processing",
            "⚡ Energy, Biomass & EfW Plants",
            "🖥️ Data Centers & Colocation Infrastructure",
            "(Clear Category)"
        ], state="readonly", width=38)
        self.gen_category_combo.current(0)
        self.gen_category_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.gen_category_combo.bind("<<ComboboxSelected>>", self._on_gen_category_selected)
        ToolTip(self.gen_category_combo, "Select pre-built facility or industry keyword groups.")
        
        btn_ind_add = ttk.Button(r1, text="+ Quotes/OR", style="Secondary.TButton", command=lambda: self._format_as_or_group(self.gen_industry_var))
        btn_ind_add.pack(side=tk.RIGHT)
        ToolTip(btn_ind_add, "Converts comma-separated words into quoted OR group.")

        # Row 2: Operational Scale & Multi-Site Scope (Group 2 - OR)
        r2 = ttk.Frame(self.subtab_generalized)
        r2.pack(fill=tk.X, pady=2)
        
        hl_scale = self._create_help_label(r2, "Scale / Multi-Site (OR):", "Group 2: Target footprint, multi-location indicators, depots, headquarters, or national operations.", width=21)
        hl_scale.pack(side=tk.LEFT)
        
        gen_scale_entry = ttk.Entry(r2, textvariable=self.gen_scale_var, font=("Segoe UI", 9), width=38)
        gen_scale_entry.pack(side=tk.LEFT, padx=(0, 6), fill=tk.X, expand=True)
        gen_scale_entry.bind("<KeyRelease>", lambda e: self._rebuild_query())
        ToolTip(gen_scale_entry, 'Enter operational footprint terms e.g. ("multiple sites" OR "depots across" OR "nationwide" OR "head office").')
        
        self.gen_scale_combo = ttk.Combobox(r2, values=[
            "Choose Scale...",
            "🏢 Multi-Site, Depots & Nationwide",
            "📍 Regional Hubs & Operating Centres",
            "🏛️ Corporate HQ & Group Operations",
            "🌐 UK-Wide & National Coverage",
            "(None / Open Scale)"
        ], state="readonly", width=38)
        self.gen_scale_combo.current(0)
        self.gen_scale_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.gen_scale_combo.bind("<<ComboboxSelected>>", self._on_gen_scale_selected)
        ToolTip(self.gen_scale_combo, "Select pre-built operational footprint or scale filters.")
        
        btn_scale_add = ttk.Button(r2, text="+ Quotes/OR", style="Secondary.TButton", command=lambda: self._format_as_or_group(self.gen_scale_var))
        btn_scale_add.pack(side=tk.RIGHT)
        ToolTip(btn_scale_add, "Converts comma-separated words into quoted OR group.")

        # Row 3: Geographic & Country Filter (Group 3 - OR)
        r3 = ttk.Frame(self.subtab_generalized)
        r3.pack(fill=tk.X, pady=2)
        
        hl_geo = self._create_help_label(r3, "Country / Region (OR):", "Group 3: Target countries, home nations, counties, or regional territories.", width=21)
        hl_geo.pack(side=tk.LEFT)
        
        gen_geo_entry = ttk.Entry(r3, textvariable=self.gen_geo_var, font=("Segoe UI", 9), width=38)
        gen_geo_entry.pack(side=tk.LEFT, padx=(0, 6), fill=tk.X, expand=True)
        gen_geo_entry.bind("<KeyRelease>", lambda e: self._rebuild_query())
        ToolTip(gen_geo_entry, 'Enter location terms e.g. ("United Kingdom" OR "UK" OR "England" OR "Scotland" OR "Wales").')
        
        self.gen_geo_combo = ttk.Combobox(r3, values=[
            "Choose Region...",
            "🇬🇧 United Kingdom & Home Nations",
            "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England & Greater London",
            "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland & Northern Ireland",
            "🇺🇸 United States Nationwide",
            "🇪🇺 Europe & Major Nations",
            "(Worldwide / Open Region)"
        ], state="readonly", width=38)
        self.gen_geo_combo.current(0)
        self.gen_geo_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.gen_geo_combo.bind("<<ComboboxSelected>>", self._on_gen_geo_selected)
        ToolTip(self.gen_geo_combo, "Select geographic and regional boundary filters.")
        
        btn_geo_add = ttk.Button(r3, text="+ Quotes/OR", style="Secondary.TButton", command=lambda: self._format_as_or_group(self.gen_geo_var))
        btn_geo_add.pack(side=tk.RIGHT)
        ToolTip(btn_geo_add, "Converts comma-separated words into quoted OR group.")

        # Row 4: Negative Exclusions & Cleaners (-)
        r4 = ttk.Frame(self.subtab_generalized)
        r4.pack(fill=tk.X, pady=2)
        
        hl_ex = self._create_help_label(r4, "Negative Exclusions (-):", "Words or domains prefixed with minus '-' will be completely removed from results (e.g. municipal tips, public council pages, job boards).", width=21)
        hl_ex.pack(side=tk.LEFT)
        
        gen_ex_entry = ttk.Entry(r4, textvariable=self.gen_exclude_var, font=("Segoe UI", 9), width=38)
        gen_ex_entry.pack(side=tk.LEFT, padx=(0, 6), fill=tk.X, expand=True)
        gen_ex_entry.bind("<KeyRelease>", lambda e: self._rebuild_query())
        ToolTip(gen_ex_entry, 'Enter negative exclusion terms e.g. -council -civic -household -tip -hwrc -.gov.uk')
        
        self.gen_exclude_combo = ttk.Combobox(r4, values=[
            "Choose Exclusion Pattern...",
            "🛡️ Exclude Municipal/Council Tips & .gov.uk",
            "🛡️ Exclude Council Tips + Job Boards",
            "🛡️ Exclude Job & Recruitment Boards Only",
            "🛡️ Exclude Public Sector / Government",
            "🛡️ Exclude Directory & Aggregator Sites",
            "(No Exclusions)"
        ], state="readonly", width=38)
        self.gen_exclude_combo.current(0)
        self.gen_exclude_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.gen_exclude_combo.bind("<<ComboboxSelected>>", self._on_gen_exclude_selected)
        ToolTip(self.gen_exclude_combo, "Select pre-configured negative exclusion cleaners.")
        
        btn_clear_ex = ttk.Button(r4, text="Clear Exclude", style="Secondary.TButton", command=lambda: (self.gen_exclude_var.set(""), self._rebuild_query()))
        btn_clear_ex.pack(side=tk.RIGHT)
        ToolTip(btn_clear_ex, "Clears negative exclusion filters.")

        # Row 5: Optional Modifiers & Contact Filters
        r5 = ttk.Frame(self.subtab_generalized)
        r5.pack(fill=tk.X, pady=(3, 1))
        
        hl_mod = self._create_help_label(r5, "Optional Modifiers:", "Optional text or URL requirements, file types, or contact hunters.", width=21)
        hl_mod.pack(side=tk.LEFT)
        
        # intext modifier
        lbl_intext = ttk.Label(r5, text="intext:")
        lbl_intext.pack(side=tk.LEFT, padx=(0, 2))
        gen_intext_entry = ttk.Entry(r5, textvariable=self.gen_intext_var, width=12)
        gen_intext_entry.pack(side=tk.LEFT, padx=(0, 8))
        gen_intext_entry.bind("<KeyRelease>", lambda e: self._rebuild_query())
        ToolTip(gen_intext_entry, "Optional keyword required in body text (e.g. permit or contact).")
        
        # inurl modifier
        lbl_inurl = ttk.Label(r5, text="inurl:")
        lbl_inurl.pack(side=tk.LEFT, padx=(0, 2))
        gen_inurl_entry = ttk.Entry(r5, textvariable=self.gen_inurl_var, width=12)
        gen_inurl_entry.pack(side=tk.LEFT, padx=(0, 8))
        gen_inurl_entry.bind("<KeyRelease>", lambda e: self._rebuild_query())
        ToolTip(gen_inurl_entry, "Optional keyword required in URL path (e.g. facilities or locations).")
        
        # Filetype
        lbl_ft = ttk.Label(r5, text="filetype:")
        lbl_ft.pack(side=tk.LEFT, padx=(0, 2))
        gen_ft_combo = ttk.Combobox(r5, textvariable=self.gen_filetype_var, values=["None", "filetype:pdf", "filetype:xls OR filetype:xlsx", "filetype:doc OR filetype:docx"], width=13, state="readonly")
        gen_ft_combo.pack(side=tk.LEFT, padx=(0, 8))
        gen_ft_combo.bind("<<ComboboxSelected>>", lambda e: self._rebuild_query())
        
        # Public emails & phone dorks
        chk_gen_email = ttk.Checkbutton(r5, text="Public Emails", variable=self.gen_email_dork_var, command=self._rebuild_query)
        chk_gen_email.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(chk_gen_email, "Appends public email hunting dork (@gmail.com OR @outlook.com OR @yahoo.com).")
        
        chk_gen_phone = ttk.Checkbutton(r5, text="Phone / Tel", variable=self.gen_phone_dork_var, command=self._rebuild_query)
        chk_gen_phone.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(chk_gen_phone, "Appends phone number indicator terms.")

        # Row 6: Quick Generalized Toolbar
        r6 = ttk.Frame(self.subtab_generalized)
        r6.pack(fill=tk.X, pady=(4, 0))
        
        btn_reset_gen = ttk.Button(r6, text="🔄 Reset Generalized Form", style="Secondary.TButton", command=self._reset_generalized_form)
        btn_reset_gen.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(btn_reset_gen, "Clears all Generalized Search fields back to empty.")
        
        btn_copy_gen = ttk.Button(r6, text="📋 Copy Query", style="Secondary.TButton", command=self._copy_query_to_clipboard)
        btn_copy_gen.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(btn_copy_gen, "Copies assembled search query to clipboard.")
        
        lbl_tip_gen = ttk.Label(r6, text="💡 Click '🚀 Search & Extract Leads' below to execute this query across your selected search engine.", foreground="#64748B", font=("Segoe UI", 8, "italic"))
        lbl_tip_gen.pack(side=tk.LEFT)

    def _reset_builder(self):
        """Clears all textboxes, criteria fields, and search query to a completely blank state across all tabs."""
        self._updating_query = True
        # Targeted fields (Tab 1)
        self.site_preset_var.set("")
        self.org_var.set("")
        self.titles_var.set("")
        self.location_var.set("")
        self.email_dork_var.set(False)
        self.phone_dork_var.set(False)
        self.custom_email_domain_var.set("")
        self.exclude_var.set("")
        self.filetype_var.set("None")
        
        # Generalized fields (Tab 2)
        self.gen_industry_var.set("")
        self.gen_scale_var.set("")
        self.gen_geo_var.set("")
        self.gen_exclude_var.set("")
        self.gen_intext_var.set("")
        self.gen_inurl_var.set("")
        self.gen_site_var.set("")
        self.gen_filetype_var.set("None")
        self.gen_email_dork_var.set(False)
        self.gen_phone_dork_var.set(False)
        if hasattr(self, "gen_category_combo"):
            self.gen_category_combo.set("Choose Preset Category...")
        if hasattr(self, "gen_scale_combo"):
            self.gen_scale_combo.set("Choose Scale...")
        if hasattr(self, "gen_geo_combo"):
            self.gen_geo_combo.set("Choose Region...")
        if hasattr(self, "gen_exclude_combo"):
            self.gen_exclude_combo.set("Choose Exclusion Pattern...")
            
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
    # TAB 2: RESULTS & ENRICHED LEAD EXTRACTOR
    # -------------------------------------------------------------
    def _build_tab_results(self):
        # 1. Format Toolbar & Stats
        toolbar = ttk.Frame(self.tab_results)
        toolbar.pack(fill=tk.X, pady=(0, 4))
        
        fmt_lbl = ttk.Label(toolbar, text="Display View:", style="Section.TLabel")
        fmt_lbl.pack(side=tk.LEFT, padx=(0, 6))
        
        self.format_var = tk.StringVar(value="table")
        
        r0 = ttk.Radiobutton(toolbar, text="📋 Interactive Table", value="table", variable=self.format_var, command=self._refresh_text_display)
        r0.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(r0, "Interactive multi-column lead table with live column header sorting, deliverability badges, and multi-lead selection.")
        
        r1 = ttk.Radiobutton(toolbar, text="🃏 Structured Cards", value="formatted", variable=self.format_var, command=self._refresh_text_display)
        r1.pack(side=tk.LEFT, padx=(0, 8))
        
        r2 = ttk.Radiobutton(toolbar, text="📊 Excel TSV", value="tsv", variable=self.format_var, command=self._refresh_text_display)
        r2.pack(side=tk.LEFT, padx=(0, 8))
        
        r3 = ttk.Radiobutton(toolbar, text="📑 CSV Format", value="csv", variable=self.format_var, command=self._refresh_text_display)
        r3.pack(side=tk.LEFT, padx=(0, 8))
        
        r4 = ttk.Radiobutton(toolbar, text="✉️ Emails Only", value="emails", variable=self.format_var, command=self._refresh_text_display)
        r4.pack(side=tk.LEFT, padx=(0, 8))
        
        r5 = ttk.Radiobutton(toolbar, text="🔗 URLs Only", value="urls", variable=self.format_var, command=self._refresh_text_display)
        r5.pack(side=tk.LEFT)
        
        self.count_badge = ttk.Label(toolbar, text="0 leads collected", style="Badge.TLabel")
        self.count_badge.pack(side=tk.RIGHT)
        
        # 2. Filter & Categorisation Bar (Row 1)
        filter_bar = ttk.Frame(self.tab_results)
        filter_bar.pack(fill=tk.X, pady=(2, 3))
        
        filter_lbl = ttk.Label(filter_bar, text="🔍 Search Filter:")
        filter_lbl.pack(side=tk.LEFT, padx=(0, 4))
        
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *args: self._refresh_text_display())
        filter_entry = ttk.Entry(filter_bar, textvariable=self.filter_var, font=("Segoe UI", 9), width=18)
        filter_entry.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(filter_entry, "Filter live results by any keyword, name, job title, domain, or email.")
        
        # Organisation / Company Categorisation Dropdown Filter
        comp_lbl = ttk.Label(filter_bar, text="🏢 Organisation:")
        comp_lbl.pack(side=tk.LEFT, padx=(0, 4))
        
        self.company_filter_combo = ttk.Combobox(filter_bar, textvariable=self.filter_company_var, state="readonly", width=26)
        self.company_filter_combo['values'] = ("(All Organisations)",)
        self.company_filter_combo.current(0)
        self.company_filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.company_filter_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_text_display())
        ToolTip(self.company_filter_combo, "Categorise and filter results to show only contacts from a specific company or service.")
        
        # Deliverability Status Filter
        stat_lbl = ttk.Label(filter_bar, text="🛡️ Status:")
        stat_lbl.pack(side=tk.LEFT, padx=(0, 4))
        
        self.status_filter_combo = ttk.Combobox(filter_bar, textvariable=self.filter_status_var, state="readonly", width=18)
        self.status_filter_combo['values'] = (
            "(All Statuses)",
            "🟢 Valid Only",
            "🟡 Risky Only",
            "⚪ Not Found Only",
            "🔴 Invalid Only"
        )
        self.status_filter_combo.current(0)
        self.status_filter_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.status_filter_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_text_display())
        ToolTip(self.status_filter_combo, "Filter results by MX deliverability verification status.")
        
        btn_reset_filters = ttk.Button(filter_bar, text="🔄 Reset Filters", style="Secondary.TButton", command=self._reset_results_filters)
        btn_reset_filters.pack(side=tk.LEFT)
        ToolTip(btn_reset_filters, "Clears text filter, organisation dropdown, and status filter back to default.")
        
        # 3. Action Toolbar (Row 2)
        enrich_bar = ttk.Frame(self.tab_results)
        enrich_bar.pack(fill=tk.X, pady=(2, 6))
        
        self.batch_enrich_btn = ttk.Button(enrich_bar, text="⚡ Batch Enrich All", style="Primary.TButton", command=self._start_batch_enrich)
        self.batch_enrich_btn.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(self.batch_enrich_btn, "Automatically resolves official domains, synthesizes work emails, and checks DNS MX deliverability for ALL contacts in list.")
        
        self.scrape_sites_btn = ttk.Button(enrich_bar, text="🌐 Scrape Site Contacts", style="Accent.TButton", command=self._start_batch_site_scrape)
        self.scrape_sites_btn.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(self.scrape_sites_btn, "Visits the company websites / contact pages of all leads to discover live contact emails, phone numbers, and site personnel.")
        
        self.single_enrich_btn = ttk.Button(enrich_bar, text="⚡ Enrich Selected", style="Secondary.TButton", command=self._enrich_selected_lead)
        self.single_enrich_btn.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(self.single_enrich_btn, "Enriches email & verifies MX deliverability for all selected rows (Hold Ctrl or Shift to select multiple lines).")
        
        self.settings_enrich_btn = ttk.Button(enrich_bar, text="⚙️ Enrichment Settings", style="Secondary.TButton", command=self._open_enrichment_settings)
        self.settings_enrich_btn.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(self.settings_enrich_btn, "Configure target industry domain registry (UK Fire Services, NHS, Councils), email pattern formulas, and optional external API keys.")
        
        hint_sort = ttk.Label(enrich_bar, text="💡 Click any column title to sort (A-Z / Z-A). Hold Ctrl/Shift for multi-row selection.", foreground="#64748B", font=("Segoe UI", 8, "italic"))
        hint_sort.pack(side=tk.LEFT)
        
        self.save_enriched_btn = ttk.Button(enrich_bar, text="💾 Export Enriched CSV", style="Success.TButton", command=self._save_to_enriched_csv)
        self.save_enriched_btn.pack(side=tk.RIGHT)
        ToolTip(self.save_enriched_btn, "Exports clean, enriched spreadsheet with First Name, Surname, Job Role, Organisation, Email, Domain, and MX Status.")
        
        # 3b. Active Search Progress Banner (Animated Visual Aid)
        self.search_progress_frame = ttk.Frame(self.tab_results, padding="4")
        
        self.search_progress_lbl = ttk.Label(self.search_progress_frame, text="🔄 Searching background engine & crawling website contacts...", font=("Segoe UI", 9, "bold"), foreground="#2563EB")
        self.search_progress_lbl.pack(side=tk.LEFT, padx=(0, 10))
        
        self.search_progress_bar = ttk.Progressbar(self.search_progress_frame, mode="indeterminate", length=260)
        self.search_progress_bar.pack(side=tk.LEFT, padx=(0, 10))
        
        self.search_progress_detail_lbl = ttk.Label(self.search_progress_frame, text="Initializing...", foreground="#64748B", font=("Segoe UI", 8, "italic"))
        self.search_progress_detail_lbl.pack(side=tk.LEFT)

        # 4. Main View Container (Holds both Interactive Treeview Table and Text Box)
        self.view_container = ttk.Frame(self.tab_results)
        self.view_container.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        
        # A. Interactive Table View (ttk.Treeview)
        self.tree_frame = ttk.Frame(self.view_container)
        
        tree_cols = ("#", "first_name", "last_name", "role", "org", "email", "phone", "status", "domain", "url")
        self.col_titles = {
            "#": "#",
            "first_name": "First Name",
            "last_name": "Surname",
            "role": "Job Role / Title",
            "org": "Organisation / Service",
            "email": "Email / Contact",
            "phone": "Phone / Tel",
            "status": "Deliverability",
            "domain": "Resolved Domain",
            "url": "Source URL"
        }
        
        self.tree = ttk.Treeview(self.tree_frame, columns=tree_cols, show="headings", selectmode="extended")
        
        for col in tree_cols:
            self.tree.heading(col, text=self.col_titles[col], command=lambda c=col: self._sort_by_column(c))
        
        self.tree.column("#", width=38, minwidth=28, anchor="center")
        self.tree.column("first_name", width=85, minwidth=65, anchor="w")
        self.tree.column("last_name", width=95, minwidth=70, anchor="w")
        self.tree.column("role", width=155, minwidth=100, anchor="w")
        self.tree.column("org", width=170, minwidth=110, anchor="w")
        self.tree.column("email", width=195, minwidth=135, anchor="w")
        self.tree.column("phone", width=130, minwidth=90, anchor="w")
        self.tree.column("status", width=125, minwidth=95, anchor="center")
        self.tree.column("domain", width=135, minwidth=95, anchor="w")
        self.tree.column("url", width=120, minwidth=85, anchor="w")
        
        tree_vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        tree_hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_vsb.set, xscrollcommand=tree_hsb.set)
        
        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        tree_vsb.grid(row=0, column=1, sticky=tk.NS)
        tree_hsb.grid(row=1, column=0, sticky=tk.EW)
        
        self.tree_frame.rowconfigure(0, weight=1)
        self.tree_frame.columnconfigure(0, weight=1)
        
        # Tags for colored deliverability badges
        self.tree.tag_configure("valid", background="#ECFDF5", foreground="#065F46")
        self.tree.tag_configure("risky", background="#FFFBEB", foreground="#92400E")
        self.tree.tag_configure("not_found", background="#F8FAFC", foreground="#475569")
        self.tree.tag_configure("invalid", background="#FEF2F2", foreground="#991B1B")
        
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree_hover_tip = TreeviewHoverToolTip(self.tree, self._get_leads_tree_row_tooltip)
        
        # Right-click context menu
        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label="⚡ Enrich Selected Contact(s)", command=self._enrich_selected_lead)
        self.tree_menu.add_command(label="🌐 Scrape Contacts from this Website", command=self._scrape_selected_site_contacts)
        self.tree_menu.add_command(label="🏢 Filter Table by this Organisation", command=self._filter_by_selected_org)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="✉️ Copy Email", command=self._copy_selected_email)
        self.tree_menu.add_command(label="📞 Copy Phone / Contact", command=self._copy_selected_phone)
        self.tree_menu.add_command(label="📋 Copy Row Details", command=self._copy_selected_row)
        self.tree_menu.add_command(label="🌐 Open Profile / Website URL in Browser", command=self._open_selected_url)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="🔄 Clear Filters / Show All", command=self._reset_results_filters)
        
        self.tree.bind("<Button-3>", self._show_tree_context_menu)
        
        # B. Text Box View (for Cards, TSV, CSV, Emails Only, URLs Only)
        self.text_container = ttk.Frame(self.view_container)
        
        self.results_text = tk.Text(
            self.text_container,
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
        
        txt_vsb = ttk.Scrollbar(self.text_container, orient="vertical", command=self.results_text.yview)
        txt_hsb = ttk.Scrollbar(self.text_container, orient="horizontal", command=self.results_text.xview)
        self.results_text.configure(yscrollcommand=txt_vsb.set, xscrollcommand=txt_hsb.set)
        
        self.results_text.grid(row=0, column=0, sticky=tk.NSEW)
        txt_vsb.grid(row=0, column=1, sticky=tk.NS)
        txt_hsb.grid(row=1, column=0, sticky=tk.EW)
        
        self.text_container.rowconfigure(0, weight=1)
        self.text_container.columnconfigure(0, weight=1)
        
        # Default view is Table
        self.tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # 4. Bottom Action Buttons
        action_bar = ttk.Frame(self.tab_results)
        action_bar.pack(fill=tk.X)
        
        self.copy_all_btn = ttk.Button(action_bar, text="📋 Copy All Text", style="Secondary.TButton", command=self._copy_to_clipboard)
        self.copy_all_btn.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(self.copy_all_btn, "Copies current results text to clipboard.")
        
        self.copy_emails_btn = ttk.Button(action_bar, text="✉️ Copy Emails List", style="Secondary.TButton", command=self._copy_emails_only)
        self.copy_emails_btn.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(self.copy_emails_btn, "Extracts and copies only verified email addresses found.")
        
        self.save_csv_btn = ttk.Button(action_bar, text="💾 Export Basic CSV", style="Secondary.TButton", command=self._save_to_csv)
        self.save_csv_btn.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(self.save_csv_btn, "Exports scraped leads to basic CSV.")
        
        self.clear_btn = ttk.Button(action_bar, text="🗑 Clear Results", style="Secondary.TButton", command=self._clear_results)
        self.clear_btn.pack(side=tk.LEFT)
        ToolTip(self.clear_btn, "Clears all current leads and resets results table.")


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
        canvas_win = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Auto-expand inner frame to match canvas width
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Smooth Mouse Wheel scrolling handlers
        def _on_cheatsheet_mousewheel(event):
            try:
                if event.delta:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                elif event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")
            except Exception:
                pass

        def _bind_cheatsheet_mousewheel(event=None):
            canvas.bind_all("<MouseWheel>", _on_cheatsheet_mousewheel)
            canvas.bind_all("<Button-4>", _on_cheatsheet_mousewheel)
            canvas.bind_all("<Button-5>", _on_cheatsheet_mousewheel)

        def _unbind_cheatsheet_mousewheel(event=None):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_cheatsheet_mousewheel)
        canvas.bind("<Leave>", _unbind_cheatsheet_mousewheel)
        scrollable_frame.bind("<Enter>", _bind_cheatsheet_mousewheel)
        scrollable_frame.bind("<Leave>", _unbind_cheatsheet_mousewheel)
        
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

        # 5. UK Environmental Protection Agencies & Waste Registers
        env_frame = ttk.LabelFrame(scrollable_frame, text=" ♻️ UK Environmental Protection Agencies & Waste Registers (EA / SEPA / NRW) ", padding="8")
        env_frame.pack(fill=tk.X, pady=(0, 8), padx=4)
        
        env_recipes = [
            (
                "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Environment Agency: Waste Permitting & Operations (England)",
                'site:environment.data.gov.uk/public-register/ ("Environmental Permitting Regulations – Waste Operations" OR "Materials recovery" OR "Waste transfer") -council -civic -household -tip -hwrc',
                "Official EA public register for commercial materials recovery, waste transfer stations, and permitted facilities."
            ),
            (
                "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Environment Agency: Waste Carriers, Brokers & Dealers (England)",
                'site:environment.data.gov.uk/public-register/ "Register of Waste Carriers, Brokers and Dealers" ("Carrier and Broker" OR "Dealer") ("Limited" OR "Ltd" OR "PLC") -council -individual',
                "Registered commercial waste carriers and brokers across England (filtered for Ltd/PLC registered companies)."
            ),
            (
                "🏴󠁧󠁢󠁳󠁣󠁴󠁿 SEPA: Scottish Environment Protection Agency (Scotland)",
                'site:sepa.org.uk ("Register of Waste Carriers" OR "authorisations" OR "waste transfer" OR "materials recovery") ("Limited" OR "Ltd" OR "PLC") -council',
                "SEPA public register for waste transfer, recycling authorisations, and commercial carriers in Scotland."
            ),
            (
                "🏴󠁧󠁢󠁷󠁬󠁳󠁿 Natural Resources Wales / Cyfoeth Naturiol Cymru (Wales)",
                'site:naturalresources.wales ("waste permitting" OR "waste carriers, brokers and dealers" OR "waste transfer") ("Limited" OR "Ltd" OR "PLC") -council -cyngor',
                "NRW official waste permitting and carrier register in Wales with bilingual council exclusions."
            ),
            (
                "🇬🇧 Combined UK Regulators (EA England + SEPA Scotland + NRW Wales)",
                '(site:environment.data.gov.uk/public-register/ OR site:sepa.org.uk OR site:naturalresources.wales) ("waste operations" OR "materials recovery" OR "waste transfer station" OR "waste carrier") ("Limited" OR "Ltd" OR "PLC") -council -cyngor -civic -household -tip -hwrc',
                "Cross-UK unified register search across England, Scotland, and Wales for commercial waste operators."
            )
        ]
        
        for title, dork, desc in env_recipes:
            item_frame = ttk.Frame(env_frame, padding="4")
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
    # HISTORY LOGGING & RECALL ENGINE (SQLITE ACID STORAGE)
    # -------------------------------------------------------------
    def _load_search_history(self):
        """Loads search query history lines from SQLite storage with file fallback."""
        history = []
        try:
            db_entries = storage.get_search_history(250)
            if db_entries:
                for item in db_entries:
                    st = item.get("search_type", "generalized")
                    tag = "TAB1: TARGETED" if st == "targeted" else "TAB2: GENERALIZED"
                    entry_str = f"[{item.get('timestamp', '')}] [{item.get('engine', 'Google')}] [{tag}] {item.get('query', '')}"
                    history.append(entry_str)
                return history
        except Exception:
            pass

        if os.path.exists(HISTORY_LOG_FILE):
            try:
                with open(HISTORY_LOG_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            history.append(line)
                            # Migrate unlogged file entries into SQLite database
                            engine, st_type, q = self._extract_query_from_log_entry(line)
                            storage.log_search_query(engine, q, 0, st_type)
            except Exception:
                pass
        return history

    def _log_search_query(self, engine, query):
        """Appends an executed search query to SQLite persistent storage, in-memory history, and log file."""
        if not query or not query.strip():
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        st = getattr(self, "active_criteria_mode", "generalized")
        tag = "TAB1: TARGETED" if st == "targeted" else "TAB2: GENERALIZED"
        clean_q = query.strip()
        
        # 1. Store in ACID-safe SQLite Database
        try:
            storage.log_search_query(
                engine=engine,
                query=clean_q,
                leads_count=len(getattr(self, "results_data", [])),
                search_type=st
            )
        except Exception:
            pass
            
        # 2. Update in-memory search history
        entry = f"[{timestamp}] [{engine}] [{tag}] {clean_q}"
        # Deduplicate identical recent queries in display
        self.search_history = [x for x in self.search_history if not x.endswith(clean_q)]
        self.search_history.insert(0, entry)
        
        # 3. Append to flat log file for fallback redundancy
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
        for item in self.search_history[:35]:
            display_vals.append(item)
        if hasattr(self, "history_combo"):
            self.history_combo['values'] = display_vals
            if display_vals:
                self.history_combo.current(0)

    def _refresh_history_listbox(self):
        """Refreshes the history listbox in Tab 6 with search filter support."""
        if not hasattr(self, "history_listbox"):
            return
        filt = self.hist_filter_var.get().lower().strip() if hasattr(self, "hist_filter_var") else ""
        self.history_listbox.delete(0, tk.END)
        for item in self.search_history:
            if not filt or filt in item.lower():
                self.history_listbox.insert(tk.END, item)

    def _extract_query_from_log_entry(self, log_entry):
        """Extracts engine, search_type, and query string from formatted log entry."""
        if not log_entry:
            return "Google", "generalized", ""
        
        # Format 1: [2026-10-03 06:50:00] [Google] [TAB1: TARGETED] query...
        m3 = re.match(r'\[.*?\]\s*\[(.*?)\]\s*\[(.*?)\]\s*(.*)', log_entry)
        if m3:
            engine = m3.group(1).strip()
            type_tag = m3.group(2).strip().lower()
            query = m3.group(3).strip()
            search_type = "targeted" if ("target" in type_tag or "tab1" in type_tag) else "generalized"
            return engine, search_type, query

        # Format 2: [2026-09-25 15:30:00] [Google] query...
        m2 = re.match(r'\[.*?\]\s*\[(.*?)\]\s*(.*)', log_entry)
        if m2:
            engine = m2.group(1).strip()
            query = m2.group(2).strip()
            # Heuristic detection for older entries
            q_lower = query.lower()
            if "site:linkedin.com" in q_lower or "site:github.com" in q_lower or "site:environment.data.gov.uk" in q_lower or q_lower.startswith("site:"):
                search_type = "targeted"
            else:
                search_type = "generalized"
            return engine, search_type, query

        return "Google", "generalized", log_entry.strip()

    def _deconstruct_and_populate_query(self, query: str, search_type: str = "targeted"):
        """
        Deconstructs a raw recalled query string and populates the individual
        input fields of Tab 1 (Targeted) or Tab 2 (Generalized).
        """
        self._updating_query = True
        try:
            if search_type == "targeted":
                self.active_criteria_mode = "targeted"
                self.criteria_notebook.select(self.subtab_targeted)
                
                # Reset targeted fields before populating
                self.site_preset_var.set("")
                self.org_var.set("")
                self.titles_var.set("")
                self.location_var.set("")
                self.email_dork_var.set(False)
                self.custom_email_domain_var.set("")
                self.phone_dork_var.set(False)
                self.exclude_var.set("")
                self.filetype_var.set("None")
                
                working_q = query.strip()
                
                # 1. Filetype: filetype:...
                ft_match = re.search(r'(?:filetype:[a-zA-Z0-9]+(?:\s+OR\s+filetype:[a-zA-Z0-9]+)*)', working_q, re.IGNORECASE)
                if ft_match:
                    self.filetype_var.set(ft_match.group(0).strip())
                    working_q = working_q[:ft_match.start()] + " " + working_q[ft_match.end():]
                    
                # 2. Target Site: site:...
                site_match = re.search(r'\((?:site:[^\)]+)\)|site:[^\s()]+(?:\s+OR\s+site:[^\s()]+)*', working_q, re.IGNORECASE)
                if site_match:
                    self.site_preset_var.set(site_match.group(0).strip())
                    working_q = working_q[:site_match.start()] + " " + working_q[site_match.end():]
                    
                # 3. Negative Exclusions: -keyword
                ex_tokens = re.findall(r'(?:^|\s)(-[^\s]+)', working_q)
                if ex_tokens:
                    self.exclude_var.set(" ".join(t.strip() for t in ex_tokens))
                    for t in ex_tokens:
                        working_q = re.sub(r'(?:^|\s)' + re.escape(t) + r'(?=\s|$)', ' ', working_q)
                        
                # 4. Public Email dork
                if re.search(r'@(?:gmail|outlook|yahoo|hotmail)\.com', working_q, re.IGNORECASE):
                    self.email_dork_var.set(True)
                    working_q = re.sub(r'\([^\)]*@(?:gmail|outlook|yahoo|hotmail)\.com[^\)]*\)', ' ', working_q, flags=re.IGNORECASE)
                    working_q = re.sub(r'"@(?:gmail|outlook|yahoo|hotmail)\.com"', ' ', working_q, flags=re.IGNORECASE)
                    
                # Custom domain dork: "@acme.com"
                custom_dom_match = re.search(r'"@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"', working_q)
                if custom_dom_match:
                    self.custom_email_domain_var.set(custom_dom_match.group(1))
                    working_q = working_q[:custom_dom_match.start()] + " " + working_q[custom_dom_match.end():]
                    
                # 5. Phone dork
                if re.search(r'\([^\)]*(?:"phone"|"tel"|"mobile"|"contact")[^\)]*\)', working_q, re.IGNORECASE):
                    self.phone_dork_var.set(True)
                    working_q = re.sub(r'\([^\)]*(?:"phone"|"tel"|"mobile"|"contact")[^\)]*\)', ' ', working_q, flags=re.IGNORECASE)
                    
                # 6. Location
                loc_pattern = r'("United Kingdom"|"London"|"Greater London"|"Manchester"|"Birmingham"|"Leeds"|"United States"|"Canada"|"Australia"|"Europe"|"England"|"Scotland"|"Wales"|"Northern Ireland")'
                loc_matches = re.findall(loc_pattern, working_q, re.IGNORECASE)
                if loc_matches:
                    self.location_var.set(loc_matches[0])
                    for lm in loc_matches:
                        working_q = working_q.replace(lm, ' ')
                        
                # 7. Remaining groups -> Org vs Titles
                bracketed = re.findall(r'\(([^)]+)\)', working_q)
                for b in bracketed:
                    working_q = working_q.replace(f"({b})", " ")
                    
                quotes = re.findall(r'"([^"]+)"', working_q)
                for q in quotes:
                    working_q = working_q.replace(f'"{q}"', " ")
                    
                rem_tokens = [t.strip() for t in working_q.split() if t.strip()]
                
                phrases = []
                for b in bracketed:
                    phrases.append(f"({b})" if " OR " in b else b)
                for q in quotes:
                    phrases.append(f'"{q}"')
                if rem_tokens:
                    phrases.append(" ".join(rem_tokens))
                    
                role_keywords = ["manager", "director", "officer", "head of", "lead", "engineer", "chief", "executive", "vp", "supervisor", "coordinator", "specialist", "worker"]
                
                for phrase in phrases:
                    p_lower = phrase.lower()
                    if any(rk in p_lower for rk in role_keywords):
                        if not self.titles_var.get():
                            self.titles_var.set(phrase)
                        else:
                            self.titles_var.set(self.titles_var.get() + f" {phrase}")
                    else:
                        if not self.org_var.get():
                            self.org_var.set(phrase)
                        elif not self.titles_var.get():
                            self.titles_var.set(phrase)
                        elif not self.location_var.get():
                            self.location_var.set(phrase)
                        else:
                            self.org_var.set(self.org_var.get() + f" {phrase}")
                            
            else:
                # GENERALIZED SEARCH MODE (Tab 2)
                self.active_criteria_mode = "generalized"
                self.criteria_notebook.select(self.subtab_generalized)
                
                # Reset generalized fields before populating
                self.gen_industry_var.set("")
                self.gen_scale_var.set("")
                self.gen_geo_var.set("")
                self.gen_exclude_var.set("")
                self.gen_intext_var.set("")
                self.gen_inurl_var.set("")
                self.gen_site_var.set("")
                self.gen_filetype_var.set("None")
                self.gen_email_dork_var.set(False)
                self.gen_phone_dork_var.set(False)
                
                working_q = query.strip()
                
                # 1. Filetype
                ft_match = re.search(r'(?:filetype:[a-zA-Z0-9]+(?:\s+OR\s+filetype:[a-zA-Z0-9]+)*)', working_q, re.IGNORECASE)
                if ft_match:
                    self.gen_filetype_var.set(ft_match.group(0).strip())
                    working_q = working_q[:ft_match.start()] + " " + working_q[ft_match.end():]
                    
                # 2. intext
                intext_match = re.search(r'intext:(?:"([^"]+)"|(\S+))', working_q, re.IGNORECASE)
                if intext_match:
                    self.gen_intext_var.set((intext_match.group(1) or intext_match.group(2)).strip())
                    working_q = working_q[:intext_match.start()] + " " + working_q[intext_match.end():]
                    
                # 3. inurl
                inurl_match = re.search(r'inurl:(?:"([^"]+)"|(\S+))', working_q, re.IGNORECASE)
                if inurl_match:
                    self.gen_inurl_var.set((inurl_match.group(1) or inurl_match.group(2)).strip())
                    working_q = working_q[:inurl_match.start()] + " " + working_q[inurl_match.end():]
                    
                # 4. site
                site_match = re.search(r'site:[^\s()]+', working_q, re.IGNORECASE)
                if site_match:
                    self.gen_site_var.set(site_match.group(0).strip())
                    working_q = working_q[:site_match.start()] + " " + working_q[site_match.end():]
                    
                # 5. Negative Exclusions
                ex_tokens = re.findall(r'(?:^|\s)(-[^\s]+)', working_q)
                if ex_tokens:
                    self.gen_exclude_var.set(" ".join(t.strip() for t in ex_tokens))
                    for t in ex_tokens:
                        working_q = re.sub(r'(?:^|\s)' + re.escape(t) + r'(?=\s|$)', ' ', working_q)
                        
                # 6. Email hunting
                if re.search(r'@(?:gmail|outlook|yahoo|hotmail)\.com', working_q, re.IGNORECASE):
                    self.gen_email_dork_var.set(True)
                    working_q = re.sub(r'\([^\)]*@(?:gmail|outlook|yahoo|hotmail)\.com[^\)]*\)', ' ', working_q, flags=re.IGNORECASE)
                    working_q = re.sub(r'"@(?:gmail|outlook|yahoo|hotmail)\.com"', ' ', working_q, flags=re.IGNORECASE)
                    
                # 7. Phone hunting
                if re.search(r'\([^\)]*(?:"phone"|"tel"|"mobile"|"contact")[^\)]*\)', working_q, re.IGNORECASE):
                    self.gen_phone_dork_var.set(True)
                    working_q = re.sub(r'\([^\)]*(?:"phone"|"tel"|"mobile"|"contact")[^\)]*\)', ' ', working_q, flags=re.IGNORECASE)
                    
                # 8. Groups for Industry, Scale, Geo
                bracketed_groups = re.findall(r'\(([^)]+)\)', working_q)
                for b in bracketed_groups:
                    working_q = working_q.replace(f"({b})", " ")
                    
                remaining_quotes = re.findall(r'"([^"]+)"', working_q)
                for q in remaining_quotes:
                    working_q = working_q.replace(f'"{q}"', " ")
                    
                rem_words = [w.strip() for w in working_q.split() if w.strip()]
                
                groups = [f"({b})" if " OR " in b else b for b in bracketed_groups]
                for q in remaining_quotes:
                    groups.append(f'"{q}"')
                if rem_words:
                    groups.append(" ".join(rem_words))
                    
                unassigned = []
                for g in groups:
                    g_lower = g.lower()
                    if any(geo in g_lower for geo in ["united kingdom", "uk", "england", "scotland", "wales", "ireland", "london", "europe", "united states", "usa"]):
                        if not self.gen_geo_var.get():
                            self.gen_geo_var.set(g)
                            continue
                    if any(si in g_lower for si in ["multiple sites", "depots across", "regional hubs", "corporate hq", "group operations", "national coverage"]):
                        if not self.gen_scale_var.get():
                            self.gen_scale_var.set(g)
                            continue
                    unassigned.append(g)
                    
                for g in unassigned:
                    if not self.gen_industry_var.get():
                        self.gen_industry_var.set(g)
                    elif not self.gen_scale_var.get():
                        self.gen_scale_var.set(g)
                    elif not self.gen_geo_var.get():
                        self.gen_geo_var.set(g)
                    else:
                        self.gen_industry_var.set(self.gen_industry_var.get() + f" {g}")

        finally:
            self._updating_query = False

    def _flash_query_preview_recalled(self, subtab_name="Tab 1: Targeted Search"):
        """Provides prominent visual feedback highlighting that a past query was recalled."""
        try:
            self.query_preview_entry.configure(style="RecalledSuccess.TEntry")
        except Exception:
            pass
            
        if hasattr(self, "recalled_notice_lbl"):
            self.recalled_notice_lbl.configure(
                text=f"✨ Recalled past query into {subtab_name} and populated form fields!",
                foreground="#059669"
            )
            
        def _restore_style():
            try:
                self.query_preview_entry.configure(style="TEntry")
            except Exception:
                pass
            if hasattr(self, "recalled_notice_lbl"):
                self.recalled_notice_lbl.configure(text="")
                
        self.after(2500, _restore_style)

    def _on_history_combo_selected(self, event=None):
        val = self.history_combo.get()
        if not val:
            return
        engine, search_type, query = self._extract_query_from_log_entry(val)
        self._load_recalled_query(engine, val)

    def _recall_selected_from_listbox(self):
        sel = self.history_listbox.curselection()
        if not sel:
            messagebox.showinfo("History", "Please select a query line from the history list.")
            return
        val = self.history_listbox.get(sel[0])
        engine, search_type, query = self._extract_query_from_log_entry(val)
        self._load_recalled_query(engine, val)

    def _copy_selected_history(self):
        sel = self.history_listbox.curselection()
        if not sel:
            messagebox.showinfo("History", "Please select a query line from the list.")
            return
        val = self.history_listbox.get(sel[0])
        _, _, query = self._extract_query_from_log_entry(val)
        self.clipboard_clear()
        self.clipboard_append(query)
        messagebox.showinfo("Copied", f"Copied search query to clipboard:\n\n{query}")

    def _load_recalled_query(self, engine, log_entry_or_query):
        """Loads a past query into the Query Builder, switches to the correct subtab, and populates form fields."""
        if not log_entry_or_query:
            return
            
        engine_detected, search_type, query = self._extract_query_from_log_entry(log_entry_or_query)
        target_engine = engine or engine_detected
        
        # Switch to Query Builder main tab
        self.notebook.select(self.tab_builder)
        
        # Deconstruct query and populate subtab form fields
        self._deconstruct_and_populate_query(query, search_type)
        
        # Set the exact assembled query
        self._updating_query = True
        self.assembled_query_var.set(query)
        self._updating_query = False
        
        # Set engine combobox
        if target_engine in ["Google", "Bing", "DuckDuckGo", "Brave", "Yahoo", "Ahmia", "Yandex"]:
            self.engine_var.set(target_engine)
            if hasattr(self, "engine_combo"):
                for idx, item in enumerate(self.engine_combo['values']):
                    if target_engine in item:
                        self.engine_combo.current(idx)
                        break
                        
        tab_label = "Tab 1 (Targeted Site & Profiles)" if search_type == "targeted" else "Tab 2 (Generalized Industry & Facilities)"
        self.status_var.set(f"📥 Recalled {target_engine} query into {tab_label}: {query[:50]}...")
        
        # Flash visual feedback
        self._flash_query_preview_recalled(tab_label)

    def _clear_history_log(self):
        if messagebox.askyesno("Clear History", "Are you sure you want to clear all logged search queries from SQLite and history?"):
            self.search_history.clear()
            try:
                storage.clear_search_history()
            except Exception:
                pass
            try:
                with open(HISTORY_LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                pass
            self._refresh_history_combo()
            self._refresh_history_listbox()
            self.status_var.set("Search history log cleared.")

    # -------------------------------------------------------------
    # TAB: EMAIL & CSV VERIFIER (DNS MX + SMTP HANDSHAKE)
    # -------------------------------------------------------------
    def _build_tab_verifier(self):
        # Header
        v_header = ttk.Label(self.tab_verifier, text="🛡️ Email & CSV Deliverability Verifier (DNS MX & SMTP Handshake)", style="Header.TLabel")
        v_header.pack(anchor=tk.W, pady=(0, 2))
        
        v_sub = ttk.Label(self.tab_verifier, text="Verify deliverability by testing live DNS MX records and performing direct SMTP server handshakes (HELO -> MAIL FROM -> RCPT TO).", style="SubHeader.TLabel")
        v_sub.pack(anchor=tk.W, pady=(0, 8))
        
        # 1. Input Source Selector (CSV File vs Manual Paste)
        mode_frame = ttk.LabelFrame(self.tab_verifier, text=" 📥 Choose Input Source (CSV Upload or Manual Paste) ", padding="8")
        mode_frame.pack(fill=tk.X, pady=(0, 6))
        
        mode_radio_bar = ttk.Frame(mode_frame)
        mode_radio_bar.pack(fill=tk.X, pady=(0, 6))
        
        r_csv = ttk.Radiobutton(mode_radio_bar, text="📂 Option A: Import CSV File (Preserves all original columns upon export)", value="csv", variable=self.verifier_input_mode, command=self._on_verifier_mode_changed)
        r_csv.pack(side=tk.LEFT, padx=(0, 20))
        
        r_paste = ttk.Radiobutton(mode_radio_bar, text="✍️ Option B: Paste Multiple Emails / Text Box", value="paste", variable=self.verifier_input_mode, command=self._on_verifier_mode_changed)
        r_paste.pack(side=tk.LEFT)
        
        # Mode A Pane: CSV File Upload Pane
        self.v_csv_pane = ttk.Frame(mode_frame)
        
        r_csv_1 = ttk.Frame(self.v_csv_pane)
        r_csv_1.pack(fill=tk.X, pady=2)
        
        lbl_cpath = ttk.Label(r_csv_1, text="Select CSV File:", width=16)
        lbl_cpath.pack(side=tk.LEFT)
        
        self.v_csv_entry = ttk.Entry(r_csv_1, textvariable=self.verifier_csv_path_var, font=("Segoe UI", 9), width=45)
        self.v_csv_entry.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)
        
        btn_browse_csv = ttk.Button(r_csv_1, text="📂 Browse CSV...", style="Primary.TButton", command=self._browse_verifier_csv)
        btn_browse_csv.pack(side=tk.LEFT, padx=(0, 8))
        
        r_csv_2 = ttk.Frame(self.v_csv_pane)
        r_csv_2.pack(fill=tk.X, pady=4)
        
        lbl_col = ttk.Label(r_csv_2, text="Email Column:", width=16)
        lbl_col.pack(side=tk.LEFT)
        
        self.v_col_combo = ttk.Combobox(r_csv_2, textvariable=self.verifier_selected_col_var, state="readonly", width=26)
        self.v_col_combo.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(self.v_col_combo, "Select which column in your CSV contains the email addresses to test.")
        
        btn_load_csv = ttk.Button(r_csv_2, text="⚡ Load CSV into Verifier", style="Success.TButton", command=self._load_csv_to_verifier)
        btn_load_csv.pack(side=tk.LEFT, padx=(0, 10))
        
        self.v_csv_info_lbl = ttk.Label(r_csv_2, text="No CSV file loaded yet.", foreground="#64748B")
        self.v_csv_info_lbl.pack(side=tk.LEFT)
        
        # Mode B Pane: Manual Paste Text Area Pane
        self.v_paste_pane = ttk.Frame(mode_frame)
        
        paste_top = ttk.Frame(self.v_paste_pane)
        paste_top.pack(fill=tk.X, pady=(0, 4))
        
        lbl_paste_hint = ttk.Label(paste_top, text="Paste multiple emails below (supports one per line, comma-separated, or 'Name, email@domain' lines):", foreground="#475569")
        lbl_paste_hint.pack(side=tk.LEFT)
        
        btn_paste_clip = ttk.Button(paste_top, text="📋 Paste from Clipboard", style="Secondary.TButton", command=self._paste_from_clipboard_verifier)
        btn_paste_clip.pack(side=tk.RIGHT, padx=(4, 0))
        
        btn_clear_ptxt = ttk.Button(paste_top, text="🧹 Clear Text", style="Secondary.TButton", command=self._clear_verifier_pasted_text)
        btn_clear_ptxt.pack(side=tk.RIGHT)
        
        self.verifier_paste_text = tk.Text(
            self.v_paste_pane,
            wrap=tk.NONE,
            font=("Consolas", 9),
            height=4,
            bg="#FFFFFF",
            fg="#0F172A",
            relief=tk.SOLID,
            borderwidth=1
        )
        self.verifier_paste_text.pack(fill=tk.X, pady=(0, 4))
        
        paste_bot = ttk.Frame(self.v_paste_pane)
        paste_bot.pack(fill=tk.X)
        
        btn_load_pasted = ttk.Button(paste_bot, text="⚡ Load Pasted Emails into Verifier", style="Success.TButton", command=self._load_pasted_to_verifier)
        btn_load_pasted.pack(side=tk.LEFT, padx=(0, 10))
        
        self.v_paste_info_lbl = ttk.Label(paste_bot, text="0 emails parsed from text.", foreground="#64748B")
        self.v_paste_info_lbl.pack(side=tk.LEFT)
        
        # Default view is CSV mode
        self.v_csv_pane.pack(fill=tk.X)
        
        # 2. Controls & Verification Options Bar
        v_ctl_frame = ttk.LabelFrame(self.tab_verifier, text=" ⚙️ Verification Controls & Execution ", padding="8")
        v_ctl_frame.pack(fill=tk.X, pady=(0, 6))
        
        ctl_row1 = ttk.Frame(v_ctl_frame)
        ctl_row1.pack(fill=tk.X, pady=(0, 4))
        
        self.v_start_btn = ttk.Button(ctl_row1, text="🚀 Start MX/SMTP Verification", style="Primary.TButton", command=self._start_email_verification)
        self.v_start_btn.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(self.v_start_btn, "Tests DNS MX records and initiates direct SMTP handshakes for all loaded emails.")
        
        self.v_stop_btn = ttk.Button(ctl_row1, text="⏹ Stop", style="Danger.TButton", command=self._stop_email_verification, state=tk.DISABLED)
        self.v_stop_btn.pack(side=tk.LEFT, padx=(0, 12))
        
        self.v_reformat_btn = ttk.Button(ctl_row1, text="🔄 Reformat & Retry Undeliverables...", style="Accent.TButton", command=lambda: self._open_reformat_retry_window("undeliverables"))
        self.v_reformat_btn.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(self.v_reformat_btn, "Open modal to reformat undeliverable emails (e.g. without dot 'alicankal' or 'acankal') and test live deliverability.")
        
        lbl_tout = ttk.Label(ctl_row1, text="Timeout (sec):")
        lbl_tout.pack(side=tk.LEFT, padx=(0, 4))
        
        tout_spin = ttk.Spinbox(ctl_row1, from_=2, to=30, textvariable=self.verifier_timeout_var, width=4)
        tout_spin.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(tout_spin, "SMTP handshake connection timeout in seconds (8s is recommended).")
        
        chk_call = ttk.Checkbutton(ctl_row1, text="Detect Catch-All Mailboxes", variable=self.verifier_catchall_var)
        chk_call.pack(side=tk.LEFT, padx=(0, 12))
        ToolTip(chk_call, "Tests a randomized non-existent address on the domain to detect catch-all mail servers.")
        
        chk_waterfall = ttk.Checkbutton(ctl_row1, text="⚡ Auto-Waterfall Retry on 550", variable=self.verifier_waterfall_var)
        chk_waterfall.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(chk_waterfall, "When enabled, if an email returns 550 (mailbox not found), automatically tests alternate formats (firstlast, flast, underscore, etc.) in a waterfall until a deliverable mailbox is found!")
        
        self.v_export_csv_btn = ttk.Button(ctl_row1, text="💾 Export Verified CSV", style="Success.TButton", command=self._export_verified_csv)
        self.v_export_csv_btn.pack(side=tk.RIGHT, padx=(4, 0))
        ToolTip(self.v_export_csv_btn, "Exports results as CSV with verification status and MX server responses.")
        
        self.v_copy_valid_btn = ttk.Button(ctl_row1, text="✉️ Copy Deliverable Only", style="Secondary.TButton", command=self._copy_deliverable_verifier_emails)
        self.v_copy_valid_btn.pack(side=tk.RIGHT, padx=(4, 0))
        
        self.v_clear_btn = ttk.Button(ctl_row1, text="🗑 Clear Table", style="Secondary.TButton", command=self._clear_verifier_table)
        self.v_clear_btn.pack(side=tk.RIGHT)
        
        # Progress & Live Stats Row
        ctl_row2 = ttk.Frame(v_ctl_frame)
        ctl_row2.pack(fill=tk.X, pady=(3, 0))
        
        self.v_progressbar = ttk.Progressbar(ctl_row2, orient="horizontal", mode="determinate", length=220)
        self.v_progressbar.pack(side=tk.LEFT, padx=(0, 12), fill=tk.X, expand=True)
        
        self.v_stats_lbl = ttk.Label(ctl_row2, text="Total: 0 | 🟢 Deliverable: 0 | 🟡 Risky: 0 | 🔴 Undeliverable: 0", font=("Segoe UI", 9, "bold"), foreground="#2563EB")
        self.v_stats_lbl.pack(side=tk.RIGHT)
        
        # 3. Interactive Verification Results Table
        v_table_frame = ttk.Frame(self.tab_verifier)
        v_table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Table Filter bar
        v_tbl_filter_bar = ttk.Frame(v_table_frame)
        v_tbl_filter_bar.pack(fill=tk.X, pady=(0, 4))
        
        lbl_vfilt = ttk.Label(v_tbl_filter_bar, text="Filter Table:")
        lbl_vfilt.pack(side=tk.LEFT, padx=(0, 4))
        
        self.v_filter_entry = ttk.Entry(v_tbl_filter_bar, textvariable=self.verifier_filter_var, font=("Segoe UI", 9), width=24)
        self.v_filter_entry.pack(side=tk.LEFT, padx=(0, 8))
        self.v_filter_entry.bind("<KeyRelease>", lambda e: self._refresh_verifier_display())
        
        v_tbl_hint = ttk.Label(v_tbl_filter_bar, text="💡 Click any column title to sort. Double-click any row to view full server SMTP handshake response.", foreground="#64748B", font=("Segoe UI", 8, "italic"))
        v_tbl_hint.pack(side=tk.LEFT)
        
        # Treeview
        tree_container = ttk.Frame(v_table_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)
        
        v_cols = ("#", "email", "info", "domain", "mx_host", "smtp_code", "status", "latency")
        self.v_col_titles = {
            "#": "#",
            "email": "Email Address",
            "info": "Contact / Extra Info",
            "domain": "Domain",
            "mx_host": "Primary MX Host",
            "smtp_code": "SMTP Code",
            "status": "Verification Status",
            "latency": "Response"
        }
        
        self.verifier_tree = ttk.Treeview(tree_container, columns=v_cols, show="headings", selectmode="extended")
        
        for col in v_cols:
            self.verifier_tree.heading(col, text=self.v_col_titles[col], command=lambda c=col: self._sort_verifier_by_col(c))
            
        self.verifier_tree.column("#", width=38, minwidth=30, anchor="center")
        self.verifier_tree.column("email", width=220, minwidth=140, anchor="w")
        self.verifier_tree.column("info", width=160, minwidth=100, anchor="w")
        self.verifier_tree.column("domain", width=140, minwidth=90, anchor="w")
        self.verifier_tree.column("mx_host", width=180, minwidth=120, anchor="w")
        self.verifier_tree.column("smtp_code", width=75, minwidth=60, anchor="center")
        self.verifier_tree.column("status", width=180, minwidth=120, anchor="w")
        self.verifier_tree.column("latency", width=75, minwidth=50, anchor="center")
        
        v_vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.verifier_tree.yview)
        v_hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.verifier_tree.xview)
        self.verifier_tree.configure(yscrollcommand=v_vsb.set, xscrollcommand=v_hsb.set)
        
        self.verifier_tree.grid(row=0, column=0, sticky=tk.NSEW)
        v_vsb.grid(row=0, column=1, sticky=tk.NS)
        v_hsb.grid(row=1, column=0, sticky=tk.EW)
        
        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)
        
        # Tags for colored status badges
        self.verifier_tree.tag_configure("deliverable", background="#ECFDF5", foreground="#065F46")
        self.verifier_tree.tag_configure("risky", background="#FFFBEB", foreground="#92400E")
        self.verifier_tree.tag_configure("undeliverable", background="#FEF2F2", foreground="#991B1B")
        self.verifier_tree.tag_configure("invalid", background="#F8FAFC", foreground="#64748B")
        
        self.verifier_tree.bind("<Double-1>", self._on_verifier_row_double_click)
        self.verifier_tree_hover_tip = TreeviewHoverToolTip(self.verifier_tree, self._get_verifier_tree_row_tooltip)
        
        # Right-click context menu
        self.v_tree_menu = tk.Menu(self, tearoff=0)
        self.v_tree_menu.add_command(label="🔍 Inspect Full Handshake Details", command=lambda: self._on_verifier_row_double_click(None))
        self.v_tree_menu.add_command(label="✉️ Copy Email Address", command=self._copy_selected_verifier_email)
        self.v_tree_menu.add_command(label="📋 Copy Row Details", command=self._copy_selected_verifier_row)
        self.v_tree_menu.add_separator()
        self.v_tree_menu.add_command(label="🔄 Reformat & Retry Selected Email(s)...", command=lambda: self._open_reformat_retry_window("selected"))
        self.v_tree_menu.add_command(label="🔄 Reformat & Retry All Undeliverables...", command=lambda: self._open_reformat_retry_window("undeliverables"))
        
        self.verifier_tree.bind("<Button-3>", self._show_verifier_context_menu)

    def _on_verifier_mode_changed(self):
        mode = self.verifier_input_mode.get()
        if mode == "csv":
            self.v_paste_pane.pack_forget()
            self.v_csv_pane.pack(fill=tk.X)
        else:
            self.v_csv_pane.pack_forget()
            self.v_paste_pane.pack(fill=tk.X)

    def _browse_verifier_csv(self):
        filepath = filedialog.askopenfilename(
            title="Select CSV File to Verify",
            filetypes=[("CSV Files (*.csv)", "*.csv"), ("All Files (*.*)", "*.*")]
        )
        if not filepath:
            return
        self.verifier_csv_path_var.set(filepath)
        
        try:
            with open(filepath, "r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                
            if not headers:
                messagebox.showerror("Invalid CSV", "The selected CSV file appears to be empty or has no header row.")
                return
                
            self.verifier_csv_fieldnames = headers
            self.v_col_combo['values'] = headers
            
            # Auto-detect email column
            detected_col = None
            email_candidates = ["email", "emails", "enriched email", "enriched_email", "mail", "contact_email", "e-mail", "primary email", "email address"]
            for h in headers:
                clean_h = h.strip().lower()
                if clean_h in email_candidates:
                    detected_col = h
                    break
            if not detected_col:
                for h in headers:
                    if "email" in h.lower() or "mail" in h.lower():
                        detected_col = h
                        break
                        
            if detected_col:
                self.verifier_selected_col_var.set(detected_col)
            else:
                self.verifier_selected_col_var.set(headers[0])
                
            self.v_csv_info_lbl.configure(text=f"Detected {len(headers)} columns. Click '⚡ Load CSV into Verifier'.", foreground="#059669")
        except Exception as e:
            messagebox.showerror("CSV Read Error", f"Could not read CSV header:\n{e}")

    def _load_csv_to_verifier(self):
        filepath = self.verifier_csv_path_var.get().strip()
        if not filepath or not os.path.exists(filepath):
            messagebox.showwarning("Missing File", "Please browse and select a valid CSV file first.")
            return
            
        email_col = self.verifier_selected_col_var.get().strip()
        if not email_col:
            messagebox.showwarning("Select Column", "Please select the column containing email addresses.")
            return
            
        try:
            self.verifier_data.clear()
            self.verifier_raw_rows.clear()
            
            with open(filepath, "r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                self.verifier_csv_fieldnames = reader.fieldnames or []
                for idx, row in enumerate(reader, 1):
                    raw_email = row.get(email_col, "").strip()
                    first_email = raw_email.split(",")[0].strip() if "," in raw_email else raw_email
                    
                    info_parts = []
                    for k in ["Name", "Full Name", "First Name", "Surname", "Organisation", "Company", "Job Title", "Headline / Role"]:
                        if k in row and row[k]:
                            info_parts.append(str(row[k]))
                            if len(info_parts) >= 2:
                                break
                    info_str = " | ".join(info_parts) if info_parts else ""
                    
                    domain = first_email.split("@")[1] if "@" in first_email else ""
                    item = {
                        "id": idx,
                        "email": first_email,
                        "info": info_str,
                        "domain": domain,
                        "mx_host": "-",
                        "smtp_code": "-",
                        "status": "Ready to verify",
                        "badge": "⚪ Pending",
                        "deliverable": False,
                        "details": "Pending verification",
                        "response_time_ms": 0,
                        "raw_row": row
                    }
                    self.verifier_data.append(item)
                    self.verifier_raw_rows.append(row)
                    
            self.v_csv_info_lbl.configure(text=f"Loaded {len(self.verifier_data)} contacts from CSV.", foreground="#059669")
            self._refresh_verifier_display()
            self.status_var.set(f"Loaded {len(self.verifier_data)} contacts from {os.path.basename(filepath)}. Click '🚀 Start MX/SMTP Verification'.")
            messagebox.showinfo("CSV Loaded", f"Successfully loaded {len(self.verifier_data)} email rows from:\n\n{os.path.basename(filepath)}\n\nReady to verify deliverability.")
        except Exception as e:
            messagebox.showerror("Error Loading CSV", f"Could not parse CSV file:\n{e}")

    def _paste_from_clipboard_verifier(self):
        try:
            clip = self.clipboard_get()
            if clip:
                self.verifier_paste_text.insert(tk.END, ("\n" if self.verifier_paste_text.get("1.0", tk.END).strip() else "") + clip.strip())
                lines_count = len([l for l in self.verifier_paste_text.get("1.0", tk.END).split("\n") if l.strip()])
                self.v_paste_info_lbl.configure(text=f"{lines_count} lines in text area. Click '⚡ Load Pasted Emails'.", foreground="#2563EB")
        except Exception as e:
            messagebox.showinfo("Clipboard", f"Could not paste from clipboard:\n{e}")

    def _clear_verifier_pasted_text(self):
        self.verifier_paste_text.delete("1.0", tk.END)
        self.v_paste_info_lbl.configure(text="0 emails parsed from text.", foreground="#64748B")

    def _load_pasted_to_verifier(self):
        text = self.verifier_paste_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Empty Text", "Please paste one or more email addresses into the text box.")
            return
            
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        self.verifier_data.clear()
        self.verifier_raw_rows.clear()
        self.verifier_csv_fieldnames = []
        
        parsed_count = 0
        for idx, line in enumerate(lines, 1):
            found_emails = EMAIL_PATTERN.findall(line)
            if found_emails:
                target_email = found_emails[0].strip()
                info_text = line.replace(target_email, "").strip(",; \t-|")
            else:
                target_email = line.strip()
                info_text = ""
                
            domain = target_email.split("@")[1] if "@" in target_email else ""
            item = {
                "id": idx,
                "email": target_email,
                "info": info_text,
                "domain": domain,
                "mx_host": "-",
                "smtp_code": "-",
                "status": "Ready to verify",
                "badge": "⚪ Pending",
                "deliverable": False,
                "details": "Pending verification",
                "response_time_ms": 0,
                "raw_row": {"Email": target_email, "Info": info_text}
            }
            self.verifier_data.append(item)
            parsed_count += 1
            
        self.v_paste_info_lbl.configure(text=f"Loaded {parsed_count} pasted emails.", foreground="#059669")
        self._refresh_verifier_display()
        self.status_var.set(f"Loaded {parsed_count} pasted contacts. Click '🚀 Start MX/SMTP Verification'.")
        messagebox.showinfo("Emails Loaded", f"Successfully parsed {parsed_count} email addresses.\n\nReady to start verification.")

    def _start_email_verification(self):
        if not self.verifier_data:
            messagebox.showwarning("No Data", "Please import a CSV file or paste email addresses before starting verification.")
            return
            
        if self.verifier_is_running:
            messagebox.showwarning("Busy", "Verification is already in progress.")
            return
            
        self.verifier_is_running = True
        self.verifier_stop_requested = False
        self.v_start_btn.configure(state=tk.DISABLED)
        self.v_stop_btn.configure(state=tk.NORMAL)
        self.v_progressbar.configure(value=0)
        self.status_var.set(f"Starting DNS MX & SMTP Handshake verification for {len(self.verifier_data)} emails...")
        
        threading.Thread(target=self._run_verifier_worker, daemon=True).start()

    def _stop_email_verification(self):
        if self.verifier_is_running:
            self.verifier_stop_requested = True
            self.status_var.set("⏹ Stopping verification...")

    def _run_verifier_worker(self):
        try:
            timeout = int(self.verifier_timeout_var.get())
            if timeout < 1:
                timeout = 8
        except Exception:
            timeout = 8
            
        catchall = self.verifier_catchall_var.get()
        use_waterfall = self.verifier_waterfall_var.get() if hasattr(self, "verifier_waterfall_var") else True
        total = len(self.verifier_data)
        
        deliverable_cnt = 0
        risky_cnt = 0
        undeliverable_cnt = 0
        errors_cnt = 0
        discovered_cnt = 0
        
        for idx, item in enumerate(self.verifier_data, 1):
            if self.verifier_stop_requested:
                break
                
            target_email = item.get("email", "")
            self.after(0, self.status_var.set, f"🛡️ Verifying ({idx}/{total}): {target_email}...")
            
            if use_waterfall:
                res = verify_email_waterfall_permutations(
                    target_email,
                    raw_row=item.get("raw_row"),
                    info=item.get("info", ""),
                    timeout=timeout,
                    check_catchall=catchall
                )
                if res.get("deliverable"):
                    if res["email"].lower() != target_email.lower():
                        discovered_cnt += 1
                    item["email"] = res["email"]  # Set to working format!
            else:
                res = verify_email_smtp_handshake(target_email, timeout=timeout, check_catchall=catchall)
            
            item["domain"] = res["domain"]
            item["mx_host"] = res["mx_host"]
            item["smtp_code"] = str(res["smtp_code"]) if res["smtp_code"] else "-"
            item["status"] = res["status"]
            item["badge"] = res["badge"]
            item["deliverable"] = res["deliverable"]
            item["details"] = res["details"]
            item["response_time_ms"] = res["response_time_ms"]
            
            if "Deliverable" in res["status"]:
                deliverable_cnt += 1
            elif "Catch-All" in res["status"] or "Greylisted" in res["status"] or "MX Active" in res["status"]:
                risky_cnt += 1
            elif "Undeliverable" in res["status"] or "No MX" in res["status"]:
                undeliverable_cnt += 1
            else:
                errors_cnt += 1
                
            progress_pct = int((idx / total) * 100)
            self.after(0, self.v_progressbar.configure, {"value": progress_pct})
            self.after(0, self.v_stats_lbl.configure, {
                "text": f"Total: {total} | 🟢 Deliverable: {deliverable_cnt} | 🟡 Risky: {risky_cnt} | 🔴 Undeliverable: {undeliverable_cnt}"
            })
            
            if idx % 2 == 0 or idx == total:
                self.after(0, self._refresh_verifier_display)
                
            time.sleep(0.02)
            
        self.verifier_is_running = False
        self.after(0, self.v_start_btn.configure, {"state": tk.NORMAL})
        self.after(0, self.v_stop_btn.configure, {"state": tk.DISABLED})
        self.after(0, self._refresh_verifier_display)
        self.after(0, self.status_var.set, f"✅ Verification complete: {deliverable_cnt} deliverable ({discovered_cnt} auto-discovered), {undeliverable_cnt} undeliverable.")
        
        disc_msg = f"\n✨ Auto-Waterfall successfully recovered/discovered {discovered_cnt} deliverable mailbox formats!" if discovered_cnt > 0 else ""
        reformat_tip = f"\n\n💡 Tip: Click '🔄 Reformat & Retry Undeliverables...' to test custom patterns on failed addresses." if undeliverable_cnt > 0 else ""
        self.after(0, messagebox.showinfo, "✅ Verification Finished",
            f"✅ Deliverability & SMTP Handshake Complete!\n\n"
            f"Total Processed: {total}\n"
            f"🟢 Deliverable (250 OK): {deliverable_cnt}{disc_msg}\n"
            f"🟡 Risky / Catch-All / Greylisted: {risky_cnt}\n"
            f"🔴 Undeliverable (550 / No MX): {undeliverable_cnt}"
            f"{reformat_tip}\n\n"
            f"Click '💾 Export Verified CSV' to save your verified file."
        )

    def _get_filtered_verifier_data(self):
        filt = self.verifier_filter_var.get().lower().strip() if hasattr(self, "verifier_filter_var") else ""
        if not filt:
            data = list(self.verifier_data)
        else:
            data = [
                r for r in self.verifier_data
                if (filt in r.get("email", "").lower() or
                    filt in r.get("info", "").lower() or
                    filt in r.get("domain", "").lower() or
                    filt in r.get("mx_host", "").lower() or
                    filt in r.get("status", "").lower())
            ]
            
        if hasattr(self, "verifier_sort_col") and self.verifier_sort_col:
            def sort_key(item):
                if self.verifier_sort_col == "#":
                    return item.get("id", 0)
                elif self.verifier_sort_col == "email":
                    return item.get("email", "").lower()
                elif self.verifier_sort_col == "info":
                    return item.get("info", "").lower()
                elif self.verifier_sort_col == "domain":
                    return item.get("domain", "").lower()
                elif self.verifier_sort_col == "mx_host":
                    return item.get("mx_host", "").lower()
                elif self.verifier_sort_col == "smtp_code":
                    return item.get("smtp_code", "").lower()
                elif self.verifier_sort_col == "status":
                    return item.get("status", "").lower()
                elif self.verifier_sort_col == "latency":
                    return item.get("response_time_ms", 0)
                return ""
            data.sort(key=sort_key, reverse=self.verifier_sort_rev)
            
        return data

    def _refresh_verifier_display(self):
        if not hasattr(self, "verifier_tree"):
            return
            
        for item in self.verifier_tree.get_children():
            self.verifier_tree.delete(item)
            
        data = self._get_filtered_verifier_data()
        for idx, r in enumerate(data, 1):
            st = r.get("status", "")
            if "Deliverable" in st:
                tag = "deliverable"
            elif "Catch-All" in st or "Greylisted" in st or "MX Active" in st or "Risky" in st:
                tag = "risky"
            elif "Undeliverable" in st or "No MX" in st:
                tag = "undeliverable"
            else:
                tag = "invalid"
                
            latency_str = f"{r.get('response_time_ms', 0)} ms" if r.get('response_time_ms') else "-"
            self.verifier_tree.insert(
                "",
                tk.END,
                iid=str(idx - 1),
                values=(
                    idx,
                    r.get("email", "-"),
                    r.get("info", "-"),
                    r.get("domain", "-"),
                    r.get("mx_host", "-"),
                    r.get("smtp_code", "-"),
                    r.get("status", "-"),
                    latency_str
                ),
                tags=(tag,)
            )

    def _sort_verifier_by_col(self, col):
        if self.verifier_sort_col == col:
            self.verifier_sort_rev = not self.verifier_sort_rev
        else:
            self.verifier_sort_col = col
            self.verifier_sort_rev = False
            
        self._update_verifier_column_headers()
        self._refresh_verifier_display()

    def _update_verifier_column_headers(self):
        if not hasattr(self, "verifier_tree") or not hasattr(self, "v_col_titles"):
            return
        for c, title in self.v_col_titles.items():
            if c == self.verifier_sort_col:
                arrow = " ▼ (Z-A)" if self.verifier_sort_rev else " ▲ (A-Z)"
                self.verifier_tree.heading(c, text=f"{title}{arrow}")
            else:
                self.verifier_tree.heading(c, text=title)

    def _show_verifier_context_menu(self, event):
        item = self.verifier_tree.identify_row(event.y)
        if item:
            curr = self.verifier_tree.selection()
            if item not in curr:
                self.verifier_tree.selection_set(item)
            try:
                self.v_tree_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.v_tree_menu.grab_release()

    def _on_verifier_row_double_click(self, event):
        selected = self.verifier_tree.selection()
        if not selected:
            return
        data = self._get_filtered_verifier_data()
        try:
            idx = int(selected[0])
            if 0 <= idx < len(data):
                r = data[idx]
                msg = (
                    f"📧 Email Address: {r.get('email', '')}\n"
                    f"🏢 Domain: {r.get('domain', '')}\n"
                    f"📡 Primary MX Host: {r.get('mx_host', '')}\n"
                    f"🔢 SMTP Response Code: {r.get('smtp_code', '')}\n"
                    f"🛡️ Verification Status: {r.get('status', '')}\n"
                    f"⏱️ Response Time: {r.get('response_time_ms', 0)} ms\n\n"
                    f"📝 Handshake Server Log:\n{r.get('details', '')}"
                )
                messagebox.showinfo("Handshake Details", msg)
        except Exception:
            pass

    def _copy_selected_verifier_email(self):
        selected = self.verifier_tree.selection()
        if not selected:
            return
        data = self._get_filtered_verifier_data()
        emails = []
        for item_id in selected:
            try:
                idx = int(item_id)
                if 0 <= idx < len(data):
                    e = data[idx].get("email", "").strip()
                    if e:
                        emails.append(e)
            except Exception:
                pass
        if emails:
            self.clipboard_clear()
            self.clipboard_append(", ".join(emails))
            self.status_var.set(f"Copied {len(emails)} email(s) to clipboard.")
            messagebox.showinfo("Copied Email", f"Copied {len(emails)} email address(es) to clipboard:\n\n" + "\n".join(emails[:10]))

    def _copy_selected_verifier_row(self):
        selected = self.verifier_tree.selection()
        if not selected:
            return
        data = self._get_filtered_verifier_data()
        lines = []
        for item_id in selected:
            try:
                idx = int(item_id)
                if 0 <= idx < len(data):
                    r = data[idx]
                    lines.append(f"{r.get('email', '')} | {r.get('domain', '')} | {r.get('mx_host', '')} | {r.get('status', '')} | {r.get('smtp_code', '')}")
            except Exception:
                pass
        if lines:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
            self.status_var.set(f"Copied {len(lines)} row(s) to clipboard.")
            messagebox.showinfo("Copied Row", f"Copied {len(lines)} row(s) to clipboard!")

    def _copy_deliverable_verifier_emails(self):
        deliv = [item.get("email", "").strip() for item in self.verifier_data if item.get("deliverable") or "Deliverable" in item.get("status", "")]
        if not deliv:
            messagebox.showinfo("No Deliverable Emails", "No deliverable emails found yet. Run verification first.")
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(deliv))
        self.status_var.set(f"Copied {len(deliv)} deliverable email(s) to clipboard.")
        messagebox.showinfo("Copied Deliverable Emails", f"Copied {len(deliv)} verified deliverable email addresses to clipboard!")

    def _clear_verifier_table(self):
        if self.verifier_is_running:
            messagebox.showwarning("Busy", "Cannot clear table while verification is running.")
            return
        self.verifier_data.clear()
        self.verifier_raw_rows.clear()
        self.verifier_csv_fieldnames = []
        self._refresh_verifier_display()
        self.v_progressbar.configure(value=0)
        self.v_stats_lbl.configure(text="Total: 0 | 🟢 Deliverable: 0 | 🟡 Risky: 0 | 🔴 Undeliverable: 0")
        self.v_csv_info_lbl.configure(text="Table cleared.", foreground="#64748B")
        self.v_paste_info_lbl.configure(text="Table cleared.", foreground="#64748B")
        self.status_var.set("Email verifier table cleared.")

    def _export_verified_csv(self):
        if not self.verifier_data:
            messagebox.showwarning("No Data", "No verification records to export. Load a CSV or paste emails first.")
            return
            
        filepath = filedialog.asksaveasfilename(
            title="Save Verified CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files (*.csv)", "*.csv"), ("All Files (*.*)", "*.*")],
            initialfile="verified_emails_delivery.csv"
        )
        if not filepath:
            return
            
        try:
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                if self.verifier_raw_rows and self.verifier_csv_fieldnames:
                    extra_fields = ["Verification_Status", "Deliverability_Badge", "Primary_MX_Host", "SMTP_Response_Code", "Handshake_Details", "Response_Time_MS"]
                    fieldnames = list(self.verifier_csv_fieldnames)
                    for ef in extra_fields:
                        if ef not in fieldnames:
                            fieldnames.append(ef)
                            
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for item in self.verifier_data:
                        raw = dict(item.get("raw_row", {}))
                        raw["Verification_Status"] = item.get("status", "")
                        raw["Deliverability_Badge"] = item.get("badge", "")
                        raw["Primary_MX_Host"] = item.get("mx_host", "")
                        raw["SMTP_Response_Code"] = item.get("smtp_code", "")
                        raw["Handshake_Details"] = item.get("details", "")
                        raw["Response_Time_MS"] = item.get("response_time_ms", 0)
                        writer.writerow(raw)
                else:
                    fieldnames = ["#", "Email", "Contact_Info", "Domain", "Primary_MX_Host", "SMTP_Code", "Verification_Status", "Deliverability_Badge", "Handshake_Details", "Response_Time_MS"]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for idx, item in enumerate(self.verifier_data, 1):
                        writer.writerow({
                            "#": idx,
                            "Email": item.get("email", ""),
                            "Contact_Info": item.get("info", ""),
                            "Domain": item.get("domain", ""),
                            "Primary_MX_Host": item.get("mx_host", ""),
                            "SMTP_Code": item.get("smtp_code", ""),
                            "Verification_Status": item.get("status", ""),
                            "Deliverability_Badge": item.get("badge", ""),
                            "Handshake_Details": item.get("details", ""),
                            "Response_Time_MS": item.get("response_time_ms", 0)
                        })
                        
            self.status_var.set(f"✅ Exported {len(self.verifier_data)} verified rows to {os.path.basename(filepath)}")
            messagebox.showinfo("Export Successful", f"Successfully exported {len(self.verifier_data)} verified contacts to:\n\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save file:\n{e}")

    def _open_reformat_retry_window(self, initial_scope="undeliverables"):
        """
        Opens a dedicated modal dialog for reformatting undeliverable/risky/selected emails
        (e.g., removing dots 'ali.cankal' -> 'alicankal', or changing to 'acankal', 'ali_cankal', etc.)
        and re-verifying live DNS MX and SMTP Handshake deliverability.
        """
        if not self.verifier_data:
            messagebox.showinfo("No Records", "Please import a CSV file or paste email addresses into the Verifier first.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("🔄 Email Pattern Reformatting & Retry Studio")
        dialog.geometry("1060x730")
        dialog.minsize(880, 600)
        dialog.transient(self)
        dialog.configure(bg="#F1F5F9")

        # Dialog State
        scope_var = tk.StringVar(value=initial_scope)
        pattern_formula_var = tk.StringVar(value="{first}{last}@{domain}")
        custom_pattern_var = tk.StringVar(value="{f}{last}@{domain}")
        dialog_filter_var = tk.StringVar(value="")
        dialog_is_running = [False]
        dialog_stop_requested = [False]
        dialog_records = []  # items in dialog

        # Header Frame
        top_frame = ttk.Frame(dialog, padding="10")
        top_frame.pack(fill=tk.X)

        lbl_title = ttk.Label(top_frame, text="🔄 Email Pattern Reformatting & Retry Studio", font=("Segoe UI", 13, "bold"), foreground="#0F172A")
        lbl_title.pack(anchor=tk.W)

        lbl_sub = ttk.Label(top_frame, text="Reformat undeliverable email addresses into alternate corporate formats (e.g. without dot 'alicankal', 'acankal', 'ali_cankal') and test live MX/SMTP deliverability.", font=("Segoe UI", 9), foreground="#64748B")
        lbl_sub.pack(anchor=tk.W, pady=(1, 4))

        # 1. Target Scope & Pattern Options Frame
        ctrl_frame = ttk.LabelFrame(dialog, text=" 🎯 1. Select Target Scope & New Email Formula ", padding="8")
        ctrl_frame.pack(fill=tk.X, padx=10, pady=(0, 6))

        # Row A: Scope Selector
        row_scope = ttk.Frame(ctrl_frame)
        row_scope.pack(fill=tk.X, pady=(0, 6))

        lbl_sc = ttk.Label(row_scope, text="Target Scope:", font=("Segoe UI", 9, "bold"), width=14)
        lbl_sc.pack(side=tk.LEFT)

        r_undeliv = ttk.Radiobutton(row_scope, text="🔴 Undeliverables (550 / No MX)", value="undeliverables", variable=scope_var, command=lambda: populate_records())
        r_undeliv.pack(side=tk.LEFT, padx=(0, 12))

        r_risky = ttk.Radiobutton(row_scope, text="🟡 Risky / Catch-All / Greylisted", value="risky", variable=scope_var, command=lambda: populate_records())
        r_risky.pack(side=tk.LEFT, padx=(0, 12))

        r_sel = ttk.Radiobutton(row_scope, text="📋 Selected in Table", value="selected", variable=scope_var, command=lambda: populate_records())
        r_sel.pack(side=tk.LEFT, padx=(0, 12))

        r_all = ttk.Radiobutton(row_scope, text="🌐 All Loaded Records", value="all", variable=scope_var, command=lambda: populate_records())
        r_all.pack(side=tk.LEFT, padx=(0, 12))

        scope_count_lbl = ttk.Label(row_scope, text="0 records targeted", font=("Segoe UI", 9, "bold"), foreground="#2563EB")
        scope_count_lbl.pack(side=tk.RIGHT)

        # Row B: Pattern Presets
        row_patterns = ttk.Frame(ctrl_frame)
        row_patterns.pack(fill=tk.X, pady=(0, 4))

        lbl_pat = ttk.Label(row_patterns, text="New Pattern:", font=("Segoe UI", 9, "bold"), width=14)
        lbl_pat.pack(side=tk.LEFT)

        patterns = [
            ("🔘 No Dot: {first}{last} (e.g. alicankal@domain)", "{first}{last}@{domain}"),
            ("🔘 First Initial + Last: {f}{last} (e.g. acankal@domain)", "{f}{last}@{domain}"),
            ("🔘 Standard Dot: {first}.{last} (e.g. ali.cankal@domain)", "{first}.{last}@{domain}"),
            ("🔘 Underscore: {first}_{last} (e.g. ali_cankal@domain)", "{first}_{last}@{domain}"),
            ("🔘 Last.First: {last}.{first} (e.g. cankal.ali@domain)", "{last}.{first}@{domain}"),
            ("🔘 LastFirst: {last}{first} (e.g. cankalali@domain)", "{last}{first}@{domain}"),
            ("🔘 Last + Initial: {last}{f} (e.g. cankala@domain)", "{last}{f}@{domain}"),
            ("🔘 First Name Only: {first} (e.g. ali@domain)", "{first}@{domain}"),
            ("🔘 Initial.Last: {f}.{last} (e.g. a.cankal@domain)", "{f}.{last}@{domain}"),
            ("🔘 Custom Formula...", "custom")
        ]

        pattern_combo = ttk.Combobox(row_patterns, values=[p[0] for p in patterns], state="readonly", width=48)
        pattern_combo.current(0)
        pattern_combo.pack(side=tk.LEFT, padx=(0, 10))

        custom_entry = ttk.Entry(row_patterns, textvariable=custom_pattern_var, font=("Segoe UI", 9), width=24)
        custom_entry.pack(side=tk.LEFT, padx=(0, 10))
        custom_entry.configure(state=tk.DISABLED)

        def on_pattern_changed(event=None):
            sel_idx = pattern_combo.current()
            if sel_idx < 0: sel_idx = 0
            label, pval = patterns[sel_idx]
            if pval == "custom":
                custom_entry.configure(state=tk.NORMAL)
                pattern_formula_var.set(custom_pattern_var.get().strip() or "{f}{last}@{domain}")
            else:
                custom_entry.configure(state=tk.DISABLED)
                pattern_formula_var.set(pval)
            apply_pattern_transformation()

        pattern_combo.bind("<<ComboboxSelected>>", on_pattern_changed)
        custom_pattern_var.trace_add("write", lambda *args: on_custom_pattern_typed())

        def on_custom_pattern_typed():
            if pattern_combo.current() == len(patterns) - 1:
                pattern_formula_var.set(custom_pattern_var.get().strip() or "{first}{last}@{domain}")
                apply_pattern_transformation()

        # Row C: Quick Preset Buttons
        row_quick = ttk.Frame(ctrl_frame)
        row_quick.pack(fill=tk.X, pady=(2, 0))

        lbl_qk = ttk.Label(row_quick, text="Quick Presets:", width=14, foreground="#64748B")
        lbl_qk.pack(side=tk.LEFT)

        def set_preset_quick(idx):
            pattern_combo.current(idx)
            on_pattern_changed()

        btn_q1 = ttk.Button(row_quick, text="⚡ 'alicankal' (No Dot)", style="Secondary.TButton", command=lambda: set_preset_quick(0))
        btn_q1.pack(side=tk.LEFT, padx=(0, 6))

        btn_q2 = ttk.Button(row_quick, text="⚡ 'acankal' (Initial+Last)", style="Secondary.TButton", command=lambda: set_preset_quick(1))
        btn_q2.pack(side=tk.LEFT, padx=(0, 6))

        btn_q3 = ttk.Button(row_quick, text="⚡ 'ali_cankal' (Underscore)", style="Secondary.TButton", command=lambda: set_preset_quick(3))
        btn_q3.pack(side=tk.LEFT, padx=(0, 6))

        btn_q4 = ttk.Button(row_quick, text="⚡ 'cankal.ali' (Last.First)", style="Secondary.TButton", command=lambda: set_preset_quick(4))
        btn_q4.pack(side=tk.LEFT, padx=(0, 6))

        # 2. Execution & Live Actions Bar
        act_frame = ttk.LabelFrame(dialog, text=" ⚡ 2. Verify Reformatted Emails & Apply Actions ", padding="8")
        act_frame.pack(fill=tk.X, padx=10, pady=(0, 6))

        act_r1 = ttk.Frame(act_frame)
        act_r1.pack(fill=tk.X, pady=(0, 4))

        btn_verify_reformat = ttk.Button(act_r1, text="🚀 Verify Current Pattern", style="Primary.TButton")
        btn_verify_reformat.pack(side=tk.LEFT, padx=(0, 8))

        btn_waterfall_all = ttk.Button(act_r1, text="✨ 1-Click Auto-Waterfall All Formats", style="Success.TButton")
        btn_waterfall_all.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(btn_waterfall_all, "Automatically cycles through ALL naming formats (firstlast, flast, underscore, etc.) for each person until a deliverable mailbox is discovered!")

        btn_stop_reformat = ttk.Button(act_r1, text="⏹ Stop", style="Danger.TButton", state=tk.DISABLED)
        btn_stop_reformat.pack(side=tk.LEFT, padx=(0, 15))

        btn_apply_main = ttk.Button(act_r1, text="📥 Apply & Update Main Table", style="Success.TButton")
        btn_apply_main.pack(side=tk.RIGHT, padx=(4, 0))
        ToolTip(btn_apply_main, "Replaces matching records in the main Verifier table with these newly formatted/verified emails.")

        btn_export_dialog_csv = ttk.Button(act_r1, text="💾 Export Reformatted CSV", style="Secondary.TButton")
        btn_export_dialog_csv.pack(side=tk.RIGHT, padx=(4, 0))

        btn_copy_dialog_valid = ttk.Button(act_r1, text="✉️ Copy Deliverable", style="Secondary.TButton")
        btn_copy_dialog_valid.pack(side=tk.RIGHT, padx=(4, 0))

        act_r2 = ttk.Frame(act_frame)
        act_r2.pack(fill=tk.X, pady=(2, 0))

        d_prog = ttk.Progressbar(act_r2, orient="horizontal", mode="determinate", length=200)
        d_prog.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)

        d_stats_lbl = ttk.Label(act_r2, text="Total: 0 | 🟢 Deliverable: 0 | 🔴 Undeliverable: 0", font=("Segoe UI", 9, "bold"), foreground="#2563EB")
        d_stats_lbl.pack(side=tk.RIGHT)

        # 3. Live Preview & Results Table
        table_container = ttk.Frame(dialog, padding="10")
        table_container.pack(fill=tk.BOTH, expand=True)

        # Filter bar
        tbl_top_bar = ttk.Frame(table_container)
        tbl_top_bar.pack(fill=tk.X, pady=(0, 4))

        lbl_f = ttk.Label(tbl_top_bar, text="Filter List:")
        lbl_f.pack(side=tk.LEFT, padx=(0, 4))

        d_filter_entry = ttk.Entry(tbl_top_bar, textvariable=dialog_filter_var, font=("Segoe UI", 9), width=22)
        d_filter_entry.pack(side=tk.LEFT, padx=(0, 8))
        d_filter_entry.bind("<KeyRelease>", lambda e: refresh_dialog_display())

        lbl_hint = ttk.Label(tbl_top_bar, text="💡 Double-click any row to view full server SMTP handshake response.", foreground="#64748B", font=("Segoe UI", 8, "italic"))
        lbl_hint.pack(side=tk.LEFT)

        d_tree_frame = ttk.Frame(table_container)
        d_tree_frame.pack(fill=tk.BOTH, expand=True)

        d_cols = ("#", "orig_email", "prev_status", "new_email", "new_status", "mx_host", "smtp_code", "latency")
        d_col_titles = {
            "#": "#",
            "orig_email": "Original Email",
            "prev_status": "Previous Status",
            "new_email": "➡️ Reformatted Email (New)",
            "new_status": "New Verification Status",
            "mx_host": "MX Host",
            "smtp_code": "Code",
            "latency": "Latency"
        }

        d_tree = ttk.Treeview(d_tree_frame, columns=d_cols, show="headings", selectmode="extended")
        for col in d_cols:
            d_tree.heading(col, text=d_col_titles[col])

        d_tree.column("#", width=36, minwidth=30, anchor="center")
        d_tree.column("orig_email", width=200, minwidth=130, anchor="w")
        d_tree.column("prev_status", width=150, minwidth=100, anchor="w")
        d_tree.column("new_email", width=220, minwidth=140, anchor="w")
        d_tree.column("new_status", width=180, minwidth=120, anchor="w")
        d_tree.column("mx_host", width=150, minwidth=100, anchor="w")
        d_tree.column("smtp_code", width=60, minwidth=45, anchor="center")
        d_tree.column("latency", width=70, minwidth=50, anchor="center")

        d_vsb = ttk.Scrollbar(d_tree_frame, orient="vertical", command=d_tree.yview)
        d_hsb = ttk.Scrollbar(d_tree_frame, orient="horizontal", command=d_tree.xview)
        d_tree.configure(yscrollcommand=d_vsb.set, xscrollcommand=d_hsb.set)

        d_tree.grid(row=0, column=0, sticky=tk.NSEW)
        d_vsb.grid(row=0, column=1, sticky=tk.NS)
        d_hsb.grid(row=1, column=0, sticky=tk.EW)

        d_tree_frame.rowconfigure(0, weight=1)
        d_tree_frame.columnconfigure(0, weight=1)

        d_tree.tag_configure("deliverable", background="#ECFDF5", foreground="#065F46")
        d_tree.tag_configure("risky", background="#FFFBEB", foreground="#92400E")
        d_tree.tag_configure("undeliverable", background="#FEF2F2", foreground="#991B1B")
        d_tree.tag_configure("pending", background="#FFFFFF", foreground="#0F172A")

        def populate_records():
            dialog_records.clear()
            sc = scope_var.get()
            selected_iids = self.verifier_tree.selection() if hasattr(self, "verifier_tree") else []
            filtered_main = self._get_filtered_verifier_data()

            for idx, item in enumerate(self.verifier_data):
                st = item.get("status", "")
                include = False
                if sc == "undeliverables":
                    if "Undeliverable" in st or "No MX" in st or "Invalid" in st or "Failed" in st:
                        include = True
                elif sc == "risky":
                    if "Risky" in st or "Catch-All" in st or "Greylisted" in st or "MX Active" in st:
                        include = True
                elif sc == "selected":
                    for sid in selected_iids:
                        try:
                            s_idx = int(sid)
                            if s_idx < len(filtered_main) and filtered_main[s_idx].get("id") == item.get("id"):
                                include = True
                                break
                        except Exception:
                            pass
                else:  # all
                    include = True

                if include:
                    dialog_records.append({
                        "id": len(dialog_records) + 1,
                        "orig_item": item,
                        "orig_email": item.get("email", ""),
                        "prev_status": item.get("status", ""),
                        "info": item.get("info", ""),
                        "raw_row": item.get("raw_row", {}),
                        "new_email": "",
                        "new_status": "Ready to verify",
                        "badge": "⚪ Pending",
                        "mx_host": item.get("mx_host", "-"),
                        "smtp_code": "-",
                        "deliverable": False,
                        "latency": 0,
                        "details": ""
                    })

            if not dialog_records and sc == "undeliverables":
                # If no undeliverables found, fallback to all records
                scope_var.set("all")
                populate_records()
                return

            scope_count_lbl.configure(text=f"{len(dialog_records)} records targeted")
            apply_pattern_transformation()

        def apply_pattern_transformation():
            pat = pattern_formula_var.get()
            for r in dialog_records:
                r["new_email"] = reformat_email_string(
                    r["orig_email"],
                    pattern=pat,
                    info=r.get("info", ""),
                    raw_row=r.get("raw_row")
                )
            refresh_dialog_display()

        def refresh_dialog_display():
            for item in d_tree.get_children():
                d_tree.delete(item)

            filt = dialog_filter_var.get().lower().strip()
            deliv_c = 0
            undeliv_c = 0

            for idx, r in enumerate(dialog_records, 1):
                if filt:
                    comb = f"{r.get('orig_email', '')} {r.get('new_email', '')} {r.get('new_status', '')} {r.get('mx_host', '')}".lower()
                    if filt not in comb:
                        continue

                st = r.get("new_status", "")
                if "Deliverable" in st:
                    tag = "deliverable"
                    deliv_c += 1
                elif "Catch-All" in st or "Risky" in st or "Greylisted" in st or "MX Active" in st:
                    tag = "risky"
                elif "Undeliverable" in st or "No MX" in st:
                    tag = "undeliverable"
                    undeliv_c += 1
                else:
                    tag = "pending"

                lat_str = f"{r.get('latency', 0)} ms" if r.get('latency') else "-"
                d_tree.insert(
                    "",
                    tk.END,
                    iid=str(idx - 1),
                    values=(
                        idx,
                        r.get("orig_email", "-"),
                        r.get("prev_status", "-"),
                        r.get("new_email", "-"),
                        r.get("new_status", "-"),
                        r.get("mx_host", "-"),
                        r.get("smtp_code", "-"),
                        lat_str
                    ),
                    tags=(tag,)
                )

            d_stats_lbl.configure(text=f"Total: {len(dialog_records)} | 🟢 Deliverable: {deliv_c} | 🔴 Undeliverable: {undeliv_c}")

        def start_dialog_verification():
            if not dialog_records:
                messagebox.showwarning("No Records", "No records targeted to verify.", parent=dialog)
                return
            if dialog_is_running[0]:
                return

            dialog_is_running[0] = True
            dialog_stop_requested[0] = False
            btn_verify_reformat.configure(state=tk.DISABLED)
            btn_stop_reformat.configure(state=tk.NORMAL)
            d_prog.configure(value=0)

            threading.Thread(target=run_dialog_worker, daemon=True).start()

        def stop_dialog_verification():
            if dialog_is_running[0]:
                dialog_stop_requested[0] = True

        def run_dialog_worker():
            try:
                tout = int(self.verifier_timeout_var.get()) if hasattr(self, "verifier_timeout_var") else 8
            except Exception:
                tout = 8
            catchall = self.verifier_catchall_var.get() if hasattr(self, "verifier_catchall_var") else False

            total = len(dialog_records)
            deliv_c = 0
            undeliv_c = 0
            risky_c = 0

            for idx, item in enumerate(dialog_records, 1):
                if dialog_stop_requested[0]:
                    break

                target_email = item.get("new_email", "")
                res = verify_email_smtp_handshake(target_email, timeout=tout, check_catchall=catchall)

                item["new_status"] = res["status"]
                item["badge"] = res["badge"]
                item["mx_host"] = res["mx_host"]
                item["smtp_code"] = str(res["smtp_code"]) if res["smtp_code"] else "-"
                item["deliverable"] = res["deliverable"]
                item["latency"] = res["response_time_ms"]
                item["details"] = res["details"]

                if "Deliverable" in res["status"]:
                    deliv_c += 1
                elif "Undeliverable" in res["status"] or "No MX" in res["status"]:
                    undeliv_c += 1
                else:
                    risky_c += 1

                progress_pct = int((idx / total) * 100)
                dialog.after(0, d_prog.configure, {"value": progress_pct})
                dialog.after(0, d_stats_lbl.configure, {
                    "text": f"Total: {total} | 🟢 Deliverable: {deliv_c} | 🟡 Risky: {risky_c} | 🔴 Undeliverable: {undeliv_c}"
                })

                if idx % 2 == 0 or idx == total:
                    dialog.after(0, refresh_dialog_display)
                time.sleep(0.02)

            dialog_is_running[0] = False
            dialog.after(0, btn_verify_reformat.configure, {"state": tk.NORMAL})
            dialog.after(0, btn_stop_reformat.configure, {"state": tk.DISABLED})
            dialog.after(0, refresh_dialog_display)
            dialog.after(0, lambda: messagebox.showinfo("✅ Reformat Verification Finished",
                f"✅ Reformatted Email Verification Finished!\n\n"
                f"Total Tested: {total}\n"
                f"🟢 Deliverable (250 OK): {deliv_c}\n"
                f"🟡 Risky / Catch-All: {risky_c}\n"
                f"🔴 Undeliverable: {undeliv_c}\n\n"
                f"Click '📥 Apply & Update Main Table' to replace with deliverable emails.",
                parent=dialog
            ))

        def apply_to_main_table():
            applied_cnt = 0
            for r in dialog_records:
                orig_item = r.get("orig_item")
                if orig_item and r.get("new_email"):
                    orig_item["email"] = r["new_email"]
                    if r.get("new_status") != "Ready to verify":
                        orig_item["status"] = r["new_status"]
                        orig_item["badge"] = r["badge"]
                        orig_item["mx_host"] = r["mx_host"]
                        orig_item["smtp_code"] = r["smtp_code"]
                        orig_item["deliverable"] = r["deliverable"]
                        orig_item["response_time_ms"] = r["latency"]
                        orig_item["details"] = r["details"]
                    applied_cnt += 1

            self._refresh_verifier_display()
            self.status_var.set(f"✅ Applied {applied_cnt} reformatted email(s) to the main Verifier table.")
            messagebox.showinfo("Applied", f"Successfully updated {applied_cnt} records in the main Verifier table!", parent=dialog)

        def export_dialog_csv():
            if not dialog_records:
                messagebox.showwarning("No Data", "No records to export.", parent=dialog)
                return

            filepath = filedialog.asksaveasfilename(
                title="Save Reformatted Emails CSV",
                defaultextension=".csv",
                filetypes=[("CSV Files (*.csv)", "*.csv"), ("All Files (*.*)", "*.*")],
                initialfile="reformatted_verified_emails.csv",
                parent=dialog
            )
            if not filepath:
                return

            try:
                with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                    fieldnames = ["#", "Original_Email", "Previous_Status", "Reformatted_Email", "New_Status", "MX_Host", "SMTP_Code", "Latency_MS", "Handshake_Details"]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for idx, r in enumerate(dialog_records, 1):
                        writer.writerow({
                            "#": idx,
                            "Original_Email": r.get("orig_email", ""),
                            "Previous_Status": r.get("prev_status", ""),
                            "Reformatted_Email": r.get("new_email", ""),
                            "New_Status": r.get("new_status", ""),
                            "MX_Host": r.get("mx_host", ""),
                            "SMTP_Code": r.get("smtp_code", ""),
                            "Latency_MS": r.get("latency", 0),
                            "Handshake_Details": r.get("details", "")
                        })
                messagebox.showinfo("Export Successful", f"Saved {len(dialog_records)} reformatted records to:\n\n{filepath}", parent=dialog)
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not save CSV:\n{e}", parent=dialog)

        def copy_dialog_deliverables():
            delivs = [r.get("new_email", "").strip() for r in dialog_records if r.get("deliverable") or "Deliverable" in r.get("new_status", "")]
            if not delivs:
                messagebox.showinfo("No Deliverables", "No deliverable emails found yet. Run verification first.", parent=dialog)
                return
            self.clipboard_clear()
            self.clipboard_append("\n".join(delivs))
            messagebox.showinfo("Copied", f"Copied {len(delivs)} verified deliverable email(s) to clipboard!", parent=dialog)

        def on_dialog_double_click(event):
            sel = d_tree.selection()
            if not sel: return
            try:
                idx = int(sel[0])
                if 0 <= idx < len(dialog_records):
                    r = dialog_records[idx]
                    msg = (
                        f"📧 Original Email: {r.get('orig_email', '')}\n"
                        f"➡️ Reformatted Email: {r.get('new_email', '')}\n"
                        f"📡 MX Host: {r.get('mx_host', '')}\n"
                        f"🔢 SMTP Response Code: {r.get('smtp_code', '')}\n"
                        f"🛡️ Verification Status: {r.get('new_status', '')}\n"
                        f"⏱️ Response Time: {r.get('latency', 0)} ms\n\n"
                        f"📝 Server Log:\n{r.get('details', '')}"
                    )
                    messagebox.showinfo("Handshake Log", msg, parent=dialog)
            except Exception:
                pass

        def start_dialog_waterfall():
            if not dialog_records:
                messagebox.showwarning("No Records", "No records targeted to verify.", parent=dialog)
                return
            if dialog_is_running[0]:
                return

            dialog_is_running[0] = True
            dialog_stop_requested[0] = False
            btn_verify_reformat.configure(state=tk.DISABLED)
            btn_waterfall_all.configure(state=tk.DISABLED)
            btn_stop_reformat.configure(state=tk.NORMAL)
            d_prog.configure(value=0)

            threading.Thread(target=run_dialog_waterfall_worker, daemon=True).start()

        def run_dialog_waterfall_worker():
            try:
                tout = int(self.verifier_timeout_var.get()) if hasattr(self, "verifier_timeout_var") else 8
            except Exception:
                tout = 8
            catchall = self.verifier_catchall_var.get() if hasattr(self, "verifier_catchall_var") else False

            total = len(dialog_records)
            deliv_c = 0
            undeliv_c = 0
            risky_c = 0

            for idx, item in enumerate(dialog_records, 1):
                if dialog_stop_requested[0]:
                    break

                target_email = item.get("orig_email", "")
                res = verify_email_waterfall_permutations(
                    target_email,
                    raw_row=item.get("raw_row"),
                    info=item.get("info", ""),
                    timeout=tout,
                    check_catchall=catchall
                )

                item["new_email"] = res["email"]  # Winning or best email format!
                item["new_status"] = res["status"]
                item["badge"] = res["badge"]
                item["mx_host"] = res["mx_host"]
                item["smtp_code"] = str(res["smtp_code"]) if res["smtp_code"] else "-"
                item["deliverable"] = res["deliverable"]
                item["latency"] = res["response_time_ms"]
                item["details"] = res["details"]

                if "Deliverable" in res["status"]:
                    deliv_c += 1
                elif "Undeliverable" in res["status"] or "No MX" in res["status"]:
                    undeliv_c += 1
                else:
                    risky_c += 1

                progress_pct = int((idx / total) * 100)
                dialog.after(0, d_prog.configure, {"value": progress_pct})
                dialog.after(0, d_stats_lbl.configure, {
                    "text": f"Total: {total} | 🟢 Deliverable: {deliv_c} | 🟡 Risky: {risky_c} | 🔴 Undeliverable: {undeliv_c}"
                })

                if idx % 2 == 0 or idx == total:
                    dialog.after(0, refresh_dialog_display)
                time.sleep(0.02)

            dialog_is_running[0] = False
            dialog.after(0, btn_verify_reformat.configure, {"state": tk.NORMAL})
            dialog.after(0, btn_waterfall_all.configure, {"state": tk.NORMAL})
            dialog.after(0, btn_stop_reformat.configure, {"state": tk.DISABLED})
            dialog.after(0, refresh_dialog_display)
            dialog.after(0, lambda: messagebox.showinfo("✨ Auto-Waterfall Finished",
                f"✨ Auto-Waterfall Complete!\n\n"
                f"Total Processed: {total}\n"
                f"🟢 Deliverable Found (250 OK): {deliv_c}\n"
                f"🔴 Undeliverable (All Formats Failed): {undeliv_c}\n\n"
                f"Click '📥 Apply & Update Main Table' to replace with the discovered deliverable emails.",
                parent=dialog
            ))

        d_tree.bind("<Double-1>", on_dialog_double_click)
        btn_verify_reformat.configure(command=start_dialog_verification)
        btn_waterfall_all.configure(command=start_dialog_waterfall)
        btn_stop_reformat.configure(command=stop_dialog_verification)
        btn_apply_main.configure(command=apply_to_main_table)
        btn_export_dialog_csv.configure(command=export_dialog_csv)
        btn_copy_dialog_valid.configure(command=copy_dialog_deliverables)

        # Initial Population
        populate_records()

    # -------------------------------------------------------------
    # TAB: DIRECT OPEN DATA & PUBLIC REGISTERS (CSV / ZIP / DIRECTORIES)
    # -------------------------------------------------------------
    def _build_tab_opendata(self):
        # 1. Header & Strategy Description
        od_header = ttk.Label(self.tab_opendata, text="📥 Direct Open Data & Public Registry Downloader", style="Header.TLabel")
        od_header.pack(anchor=tk.W, pady=(0, 2))
        
        od_sub = ttk.Label(self.tab_opendata, text="Direct bulk download of official open-data registers (CSV/ZIP) & directories. Bypasses search engines and CAPTCHAs entirely.", style="SubHeader.TLabel")
        od_sub.pack(anchor=tk.W, pady=(0, 6))

        # 2. Frame A: Saved Registry Sources & Portals
        src_frame = ttk.LabelFrame(self.tab_opendata, text=" 📜 Saved Registry Sources & Portals (Environment Agency, SEPA, NRW, NFCC) ", padding="8")
        src_frame.pack(fill=tk.X, pady=(0, 6))
        
        # Row 1: Combobox + Action Buttons
        r_src = ttk.Frame(src_frame)
        r_src.pack(fill=tk.X, pady=(0, 4))
        
        hl_src = self._create_help_label(r_src, "Select Source:", "Choose an official registry source or any custom link you previously saved.", width=14)
        hl_src.pack(side=tk.LEFT)
        
        source_names = [s.get("name", "Unknown") for s in self.opendata_sources]
        self.opendata_source_combo = ttk.Combobox(r_src, values=source_names, textvariable=self.opendata_selected_var, state="readonly", width=48)
        if source_names:
            self.opendata_source_combo.current(0)
        self.opendata_source_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.opendata_source_combo.bind("<<ComboboxSelected>>", self._on_opendata_source_selected)
        ToolTip(self.opendata_source_combo, "Select a pre-configured open-data register or any custom link you saved.")
        
        btn_load_src = ttk.Button(r_src, text="⚡ Load Source", style="Secondary.TButton", command=self._on_opendata_source_selected)
        btn_load_src.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(btn_load_src, "Populates the selected registry URL and details into the fetcher form below.")
        
        btn_open_web = ttk.Button(r_src, text="🌐 Open in Browser", style="Secondary.TButton", command=self._open_opendata_in_browser)
        btn_open_web.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(btn_open_web, "Opens the official register or portal web page directly in your default browser.")
        
        btn_save_src = ttk.Button(r_src, text="💾 Save to List", style="Secondary.TButton", command=self._save_current_opendata_source)
        btn_save_src.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(btn_save_src, "Saves whatever URL & Label you typed into your permanent saved registry sources.")
        
        btn_del_src = ttk.Button(r_src, text="🗑️ Delete Source", style="Secondary.TButton", command=self._delete_current_opendata_source)
        btn_del_src.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(btn_del_src, "Deletes the currently selected source from the saved list.")

        btn_reset_src = ttk.Button(r_src, text="🔄 Reset Defaults", style="Secondary.TButton", command=self._reset_opendata_sources_defaults)
        btn_reset_src.pack(side=tk.LEFT)
        ToolTip(btn_reset_src, "Restores the built-in official registry sources (EA, SEPA, NRW, NFCC).")

        # Row 2: Live Description Badge
        self.opendata_desc_lbl = ttk.Label(src_frame, text="", foreground="#64748B", font=("Segoe UI", 8, "italic"), wraplength=1000)
        self.opendata_desc_lbl.pack(anchor=tk.W, pady=(2, 0))
        self._update_opendata_desc_label()

        # 3. Frame B: Custom URL Input & Direct Fetcher
        fetch_frame = ttk.LabelFrame(self.tab_opendata, text=" 📥 Custom Registry URL / Direct Archive Fetcher ", padding="8")
        fetch_frame.pack(fill=tk.X, pady=(0, 6))
        
        # Row 1: URL & Label Inputs
        r_url = ttk.Frame(fetch_frame)
        r_url.pack(fill=tk.X, pady=(0, 4))
        
        hl_url = self._create_help_label(r_url, "Registry URL:", "Paste ANY URL: direct .csv or .zip link, API endpoint, or public directory webpage (e.g. NFCC or SEPA).", width=14)
        hl_url.pack(side=tk.LEFT)
        
        url_entry = ttk.Entry(r_url, textvariable=self.opendata_url_var, font=("Consolas", 9), width=50)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ToolTip(url_entry, "Paste a direct download URL (.zip, .csv) or web directory page URL (e.g. https://nfcc.org.uk/contacts/chief-fire-officers/).")
        
        lbl_name = ttk.Label(r_url, text="Label / Name:")
        lbl_name.pack(side=tk.LEFT, padx=(0, 4))
        
        name_entry = ttk.Entry(r_url, textvariable=self.opendata_name_var, font=("Segoe UI", 9), width=24)
        name_entry.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(name_entry, "Friendly name for this registry (used when saving to presets).")
        
        btn_pick_local = ttk.Button(r_url, text="📂 Local File...", style="Secondary.TButton", command=self._pick_opendata_local_file)
        btn_pick_local.pack(side=tk.LEFT)
        ToolTip(btn_pick_local, "Select any locally downloaded .csv or .zip register file from your computer.")

        # Row 2: Controls + Fetch Button + Progress
        r_ctrl = ttk.Frame(fetch_frame)
        r_ctrl.pack(fill=tk.X, pady=(2, 0))
        
        hl_max = self._create_help_label(r_ctrl, "Max Rows:", "Maximum number of records to load into memory/preview table.", width=14)
        hl_max.pack(side=tk.LEFT)
        
        max_spin = ttk.Spinbox(r_ctrl, from_=50, to=50000, increment=250, textvariable=self.opendata_max_rows_var, width=6)
        max_spin.pack(side=tk.LEFT, padx=(0, 12))
        ToolTip(max_spin, "Maximum rows to load (e.g. 500, 2000, 10000). Set higher for full national datasets.")
        
        self.btn_fetch_opendata = ttk.Button(r_ctrl, text="📥 Fetch & Download Data", style="Primary.TButton", command=self._start_fetch_opendata)
        self.btn_fetch_opendata.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(self.btn_fetch_opendata, "Directly downloads archive/CSV or extracts structured HTML directory tables.")
        
        self.btn_stop_opendata = ttk.Button(r_ctrl, text="⏹ Stop Fetch", style="Danger.TButton", command=self._stop_fetch_opendata, state=tk.DISABLED)
        self.btn_stop_opendata.pack(side=tk.LEFT, padx=(0, 12))
        
        self.opendata_prog = ttk.Progressbar(r_ctrl, mode="indeterminate", length=140)
        self.opendata_prog.pack(side=tk.LEFT, padx=(0, 10))
        
        self.opendata_status_var = tk.StringVar(value="Ready. Select a preset or paste a link, then click 'Fetch & Download Data'.")
        lbl_od_stat = ttk.Label(r_ctrl, textvariable=self.opendata_status_var, font=("Segoe UI", 8, "italic"), foreground="#475569")
        lbl_od_stat.pack(side=tk.LEFT)

        # 4. Frame C: Interactive Preview Table & Filter
        table_frame = ttk.LabelFrame(self.tab_opendata, text=" 📊 Dataset Preview & Interactive Table ", padding="6")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        
        # Filter & Count Bar
        f_bar = ttk.Frame(table_frame)
        f_bar.pack(fill=tk.X, pady=(0, 4))
        
        lbl_filter = ttk.Label(f_bar, text="🔍 Search Filter:")
        lbl_filter.pack(side=tk.LEFT, padx=(0, 4))
        
        self.opendata_filter_entry = ttk.Entry(f_bar, textvariable=self.opendata_filter_var, font=("Segoe UI", 9), width=24)
        self.opendata_filter_entry.pack(side=tk.LEFT, padx=(0, 8))
        self.opendata_filter_var.trace_add("write", lambda *args: self._refresh_opendata_table())
        ToolTip(self.opendata_filter_entry, "Filter live records by any keyword, business name, permit, or location.")
        
        btn_clr_filter = ttk.Button(f_bar, text="🔄 Clear Filter", style="Secondary.TButton", command=lambda: (self.opendata_filter_var.set(""), self._refresh_opendata_table()))
        btn_clr_filter.pack(side=tk.LEFT, padx=(0, 12))
        
        self.opendata_count_badge = ttk.Label(f_bar, text="0 records loaded", style="Badge.TLabel")
        self.opendata_count_badge.pack(side=tk.RIGHT)
        
        # Scrollable Treeview Container
        tree_container = ttk.Frame(table_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)
        
        self.opendata_tree = ttk.Treeview(tree_container, show="headings", selectmode="extended")
        
        sb_y = ttk.Scrollbar(tree_container, orient="vertical", command=self.opendata_tree.yview)
        sb_x = ttk.Scrollbar(tree_container, orient="horizontal", command=self.opendata_tree.xview)
        
        self.opendata_tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        
        sb_y.pack(side=tk.RIGHT, fill=tk.Y)
        sb_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.opendata_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.opendata_tree_hover_tip = TreeviewHoverToolTip(self.opendata_tree, self._get_opendata_tree_row_tooltip)

        # 5. Frame D: Action & Bridge Toolbar
        action_frame = ttk.Frame(self.tab_opendata)
        action_frame.pack(fill=tk.X)
        
        btn_send_leads = ttk.Button(action_frame, text="⚡ Send Records to Leads Table (Tab 2)", style="Primary.TButton", command=self._send_opendata_to_leads)
        btn_send_leads.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(btn_send_leads, "Maps loaded registry entities into Tab 2 so you can instantly run '⚡ Batch Enrich' to synthesize & verify emails.")
        
        btn_send_verif = ttk.Button(action_frame, text="⚡ Send to Email Verifier (Tab 3)", style="Secondary.TButton", command=self._send_opendata_to_verifier)
        btn_send_verif.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(btn_send_verif, "Bridges loaded contacts/emails directly into Tab 3 for MX/SMTP deliverability checking.")
        
        btn_export_csv = ttk.Button(action_frame, text="💾 Export Dataset as CSV", style="Secondary.TButton", command=self._export_opendata_csv)
        btn_export_csv.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(btn_export_csv, "Saves the loaded or filtered dataset to a clean CSV file on your disk.")
        
        btn_clear_tbl = ttk.Button(action_frame, text="🗑️ Clear Table", style="Secondary.TButton", command=self._clear_opendata_table)
        btn_clear_tbl.pack(side=tk.RIGHT)
        ToolTip(btn_clear_tbl, "Clears loaded dataset from memory and table.")

    def _update_opendata_desc_label(self):
        sel_name = self.opendata_selected_var.get()
        for s in self.opendata_sources:
            if s.get("name") == sel_name:
                desc = s.get("description", "")
                cat = s.get("category", "")
                self.opendata_desc_lbl.configure(text=f"📌 {cat}: {desc}")
                return
        self.opendata_desc_lbl.configure(text="📌 Custom Registry Dataset Source")

    def _on_opendata_source_selected(self, event=None):
        sel_name = self.opendata_selected_var.get()
        for s in self.opendata_sources:
            if s.get("name") == sel_name:
                self.opendata_url_var.set(s.get("url", ""))
                self.opendata_name_var.set(s.get("name", ""))
                self._update_opendata_desc_label()
                self.opendata_status_var.set(f"Selected '{s.get('name')}'. Ready to fetch.")
                return

    def _open_opendata_in_browser(self):
        sel_name = self.opendata_selected_var.get()
        target_url = self.opendata_url_var.get().strip()
        for s in self.opendata_sources:
            if s.get("name") == sel_name:
                target_url = s.get("web_url") or s.get("url") or target_url
                break
        if target_url:
            webbrowser.open(target_url)
            self.status_var.set(f"Opening {target_url} in browser...")
        else:
            messagebox.showwarning("No URL", "Please select a registry source or enter a URL first.")

    def _save_current_opendata_source(self):
        url = self.opendata_url_var.get().strip()
        name = self.opendata_name_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a valid Registry URL to save.")
            return
        if not name:
            name = f"Custom: {url[:30]}"
            self.opendata_name_var.set(name)
        
        # Check if updating existing
        existing = False
        for s in self.opendata_sources:
            if s.get("name") == name or s.get("url") == url:
                s["name"] = name
                s["url"] = url
                s["web_url"] = url
                existing = True
                break
        if not existing:
            self.opendata_sources.append({
                "name": name,
                "url": url,
                "web_url": url,
                "category": "User Saved",
                "description": f"Custom user-added open dataset from {url}"
            })
            
        save_registry_sources(self.opendata_sources)
        names = [s.get("name", "Unknown") for s in self.opendata_sources]
        self.opendata_source_combo.configure(values=names)
        self.opendata_selected_var.set(name)
        self._update_opendata_desc_label()
        messagebox.showinfo("Saved", f"Saved '{name}' to your permanent registry sources!")

    def _delete_current_opendata_source(self):
        sel_name = self.opendata_selected_var.get()
        if not sel_name:
            return
        if len(self.opendata_sources) <= 1:
            messagebox.showwarning("Cannot Delete", "Cannot delete the only remaining source.")
            return
        confirm = messagebox.askyesno("Delete Source", f"Are you sure you want to remove '{sel_name}' from your saved sources?")
        if confirm:
            self.opendata_sources = [s for s in self.opendata_sources if s.get("name") != sel_name]
            save_registry_sources(self.opendata_sources)
            names = [s.get("name", "Unknown") for s in self.opendata_sources]
            self.opendata_source_combo.configure(values=names)
            if names:
                self.opendata_source_combo.current(0)
                self._on_opendata_source_selected()
            messagebox.showinfo("Deleted", f"Removed '{sel_name}' from saved registry sources.")

    def _reset_opendata_sources_defaults(self):
        confirm = messagebox.askyesno("Reset Defaults", "Reset saved registry sources back to official defaults (EA, SEPA, NRW, NFCC)?")
        if confirm:
            self.opendata_sources = list(DEFAULT_REGISTRY_SOURCES)
            save_registry_sources(self.opendata_sources)
            names = [s.get("name", "Unknown") for s in self.opendata_sources]
            self.opendata_source_combo.configure(values=names)
            if names:
                self.opendata_source_combo.current(0)
                self._on_opendata_source_selected()
            messagebox.showinfo("Reset", "Registry sources restored to defaults.")

    def _pick_opendata_local_file(self):
        path = filedialog.askopenfilename(
            title="Select Open Data File",
            filetypes=[("Data Archives & CSVs", "*.csv *.zip *.tsv *.txt *.xlsx"), ("All Files", "*.*")]
        )
        if path:
            self.opendata_url_var.set(path)
            self.opendata_name_var.set(os.path.basename(path))
            self.opendata_status_var.set(f"Loaded local path: {os.path.basename(path)}. Click 'Fetch & Download Data' to parse.")

    def _start_fetch_opendata(self):
        url = self.opendata_url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a URL or select a local dataset file first.")
            return
        if self.opendata_is_fetching:
            return
            
        self.opendata_is_fetching = True
        self.opendata_stop_requested = False
        self.btn_fetch_opendata.configure(state=tk.DISABLED)
        self.btn_stop_opendata.configure(state=tk.NORMAL)
        self.opendata_prog.start(10)
        self.opendata_status_var.set(f"Connecting and downloading from {url[:50]}...")
        
        max_rows = self.opendata_max_rows_var.get()
        threading.Thread(target=self._fetch_opendata_worker, args=(url, max_rows), daemon=True).start()

    def _stop_fetch_opendata(self):
        self.opendata_stop_requested = True
        self.opendata_is_fetching = False
        self.opendata_status_var.set("Fetch cancelled by user.")
        self.btn_fetch_opendata.configure(state=tk.NORMAL)
        self.btn_stop_opendata.configure(state=tk.DISABLED)
        self.opendata_prog.stop()

    def _fetch_opendata_worker(self, url, max_rows):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
        parsed_headers = []
        parsed_rows = []
        err_msg = ""
        
        try:
            # 1. Local File Check
            if os.path.isfile(url):
                if url.lower().endswith('.zip'):
                    with zipfile.ZipFile(url, 'r') as z:
                        csv_files = [n for n in z.namelist() if n.lower().endswith('.csv')]
                        if csv_files:
                            with z.open(csv_files[0]) as f:
                                reader = csv.reader(io.TextIOWrapper(f, encoding='utf-8', errors='ignore'))
                                parsed_headers = next(reader)
                                for idx, row in enumerate(reader):
                                    if self.opendata_stop_requested or idx >= max_rows: break
                                    parsed_rows.append(row)
                else:
                    with open(url, 'r', encoding='utf-8', errors='ignore') as f:
                        reader = csv.reader(f)
                        parsed_headers = next(reader)
                        for idx, row in enumerate(reader):
                            if self.opendata_stop_requested or idx >= max_rows: break
                            parsed_rows.append(row)
            else:
                # 2. Remote HTTP Download
                resp = requests.get(url, headers=headers, timeout=25, stream=True)
                if resp.status_code != 200:
                    err_msg = f"HTTP {resp.status_code}: {resp.reason}"
                else:
                    content_type = resp.headers.get('Content-Type', '').lower()
                    raw_bytes = resp.content
                    
                    # Check if ZIP Archive
                    if 'zip' in content_type or url.lower().endswith('.zip') or raw_bytes[:4] == b'PK\x03\x04':
                        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                            csv_files = [n for n in z.namelist() if n.lower().endswith('.csv')]
                            if csv_files:
                                with z.open(csv_files[0]) as f:
                                    reader = csv.reader(io.TextIOWrapper(f, encoding='utf-8', errors='ignore'))
                                    parsed_headers = next(reader)
                                    for idx, row in enumerate(reader):
                                        if self.opendata_stop_requested or idx >= max_rows: break
                                        parsed_rows.append(row)
                            else:
                                err_msg = "ZIP file downloaded successfully, but contained no .csv data files."
                                
                    # Check if Direct CSV / Plain Text
                    elif 'text/csv' in content_type or url.lower().endswith('.csv') or (',' in resp.text[:200] and '\n' in resp.text[:200] and not '<html' in resp.text[:200].lower()):
                        reader = csv.reader(io.StringIO(resp.text))
                        parsed_headers = next(reader)
                        for idx, row in enumerate(reader):
                            if self.opendata_stop_requested or idx >= max_rows: break
                            parsed_rows.append(row)
                            
                    # Check if HTML Directory or Portal
                    elif 'html' in content_type or '<html' in resp.text.lower():
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        tables = soup.find_all('table')
                        
                        # If HTML table present (e.g. NFCC Chief Fire Officers)
                        if tables:
                            table = tables[0]
                            th_cells = table.find_all('th')
                            if th_cells:
                                parsed_headers = [th.get_text(strip=True) for th in th_cells]
                            
                            for tr in table.find_all('tr'):
                                if self.opendata_stop_requested or len(parsed_rows) >= max_rows: break
                                td_cells = tr.find_all('td')
                                if td_cells:
                                    parsed_rows.append([td.get_text(strip=True) for td in td_cells])
                                    
                            if not parsed_headers and parsed_rows:
                                if len(parsed_rows[0]) == 2:
                                    parsed_headers = ["Name / Official", "Organisation / Fire Service"]
                                else:
                                    parsed_headers = [f"Column_{i+1}" for i in range(len(parsed_rows[0]))]
                        else:
                            # Look for downloadable links on the webpage
                            found_download_url = None
                            for a in soup.find_all('a', href=True):
                                href = a['href']
                                text = a.get_text(strip=True).lower()
                                if any(ext in href.lower() for ext in ['.zip', '.csv', '/downloads/']) or 'download' in text:
                                    found_download_url = urllib.parse.urljoin(url, href)
                                    break
                            if found_download_url and found_download_url != url:
                                # Fetch nested link
                                sub_r = requests.get(found_download_url, headers=headers, timeout=25)
                                if sub_r.status_code == 200:
                                    if sub_r.content[:4] == b'PK\x03\x04' or found_download_url.lower().endswith('.zip'):
                                        with zipfile.ZipFile(io.BytesIO(sub_r.content)) as z:
                                            csv_files = [n for n in z.namelist() if n.lower().endswith('.csv')]
                                            if csv_files:
                                                with z.open(csv_files[0]) as f:
                                                    reader = csv.reader(io.TextIOWrapper(f, encoding='utf-8', errors='ignore'))
                                                    parsed_headers = next(reader)
                                                    for idx, row in enumerate(reader):
                                                        if self.opendata_stop_requested or idx >= max_rows: break
                                                        parsed_rows.append(row)
                                    else:
                                        reader = csv.reader(io.StringIO(sub_r.text))
                                        parsed_headers = next(reader)
                                        for idx, row in enumerate(reader):
                                            if self.opendata_stop_requested or idx >= max_rows: break
                                            parsed_rows.append(row)
                            else:
                                err_msg = "Webpage loaded, but no structured tables or downloadable CSV/ZIP links were detected."
        except Exception as e:
            err_msg = str(e)
            
        def _finish_ui():
            self.opendata_is_fetching = False
            self.btn_fetch_opendata.configure(state=tk.NORMAL)
            self.btn_stop_opendata.configure(state=tk.DISABLED)
            self.opendata_prog.stop()
            
            if err_msg:
                self.opendata_status_var.set(f"❌ Error: {err_msg}")
                messagebox.showerror("Fetch Error", f"Failed to fetch data from:\n{url}\n\nReason:\n{err_msg}")
            else:
                self.opendata_headers = [h.strip() for h in parsed_headers] if parsed_headers else []
                self.opendata_raw_records = parsed_rows
                self._refresh_opendata_table()
                self.opendata_status_var.set(f"✅ Loaded {len(parsed_rows)} records ({len(self.opendata_headers)} columns) successfully!")
                self.status_var.set(f"Loaded {len(parsed_rows)} registry records into memory.")
                
        self.after(0, _finish_ui)

    def _refresh_opendata_table(self):
        # Configure columns
        if not self.opendata_headers and self.opendata_raw_records:
            self.opendata_headers = [f"Col_{i+1}" for i in range(len(self.opendata_raw_records[0]))]
            
        self.opendata_tree.delete(*self.opendata_tree.get_children())
        cols = [f"col_{i}" for i in range(len(self.opendata_headers))]
        self.opendata_tree["columns"] = cols
        
        for i, header_text in enumerate(self.opendata_headers):
            col_id = cols[i]
            col_label = f"{header_text}"
            if self.opendata_sort_col == i:
                col_label += " ▼" if self.opendata_sort_rev else " ▲"
            self.opendata_tree.heading(col_id, text=col_label, command=lambda idx=i: self._on_opendata_column_click(idx))
            self.opendata_tree.column(col_id, width=150, minwidth=80, anchor=tk.W)
            
        filter_str = self.opendata_filter_var.get().strip().lower()
        displayed_count = 0
        
        # Sort if set
        records = list(self.opendata_raw_records)
        if self.opendata_sort_col is not None and self.opendata_sort_col < len(self.opendata_headers):
            records.sort(
                key=lambda r: str(r[self.opendata_sort_col]).lower() if self.opendata_sort_col < len(r) else "",
                reverse=self.opendata_sort_rev
            )
            
        for r_idx, row in enumerate(records):
            if filter_str:
                row_str = " ".join([str(c) for c in row]).lower()
                if filter_str not in row_str:
                    continue
            row_vals = [row[c_idx] if c_idx < len(row) else "" for c_idx in range(len(self.opendata_headers))]
            self.opendata_tree.insert("", tk.END, iid=str(r_idx), values=row_vals)
            displayed_count += 1
            
        self.opendata_count_badge.configure(text=f"📊 {displayed_count} of {len(self.opendata_raw_records)} records loaded")

    def _on_opendata_column_click(self, col_idx):
        if self.opendata_sort_col == col_idx:
            self.opendata_sort_rev = not self.opendata_sort_rev
        else:
            self.opendata_sort_col = col_idx
            self.opendata_sort_rev = False
        self._refresh_opendata_table()

    def _send_opendata_to_leads(self):
        if not self.opendata_raw_records:
            messagebox.showwarning("No Data", "No registry records loaded. Fetch a dataset first.")
            return
            
        sel_iids = self.opendata_tree.selection()
        if sel_iids:
            records_to_send = [self.opendata_raw_records[int(i)] for i in sel_iids if int(i) < len(self.opendata_raw_records)]
        else:
            records_to_send = self.opendata_raw_records
            
        headers_lower = [h.lower() for h in self.opendata_headers]
        
        # Find best column mappings
        org_col = None
        name_col = None
        role_col = None
        permit_col = None
        addr_col = None
        email_col = None
        
        for idx, h in enumerate(headers_lower):
            if any(k in h for k in ['business name', 'licence holder', 'organisation', 'organization', 'company', 'fire service', 'employer']):
                if org_col is None: org_col = idx
            elif any(k in h for k in ['name / official', 'full name', 'contact name', 'director', 'officer', 'applicant']):
                if name_col is None: name_col = idx
            elif any(k in h for k in ['role', 'job title', 'title', 'position']):
                if role_col is None: role_col = idx
            elif any(k in h for k in ['permit', 'registration number', 'licence no', 'reference']):
                if permit_col is None: permit_col = idx
            elif any(k in h for k in ['address', 'postcode', 'town', 'location']):
                if addr_col is None: addr_col = idx
            elif any(k in h for k in ['email', 'mail', 'e-mail']):
                if email_col is None: email_col = idx

        source_name = self.opendata_name_var.get().strip() or "Direct Public Register"
        source_url = self.opendata_url_var.get().strip()
        added_count = 0
        
        for r in records_to_send:
            org_val = r[org_col] if (org_col is not None and org_col < len(r)) else ""
            name_val = r[name_col] if (name_col is not None and name_col < len(r)) else ""
            role_val = r[role_col] if (role_col is not None and role_col < len(r)) else ""
            permit_val = r[permit_col] if (permit_col is not None and permit_col < len(r)) else ""
            addr_val = r[addr_col] if (addr_col is not None and addr_col < len(r)) else ""
            email_val = r[email_col] if (email_col is not None and email_col < len(r)) else ""
            
            # If name is present but org is not (e.g. single entity)
            if not org_val and name_val:
                org_val = name_val
            if not name_val and org_val:
                name_val = org_val
                
            parts = name_val.split()
            first = parts[0] if parts else ""
            last = parts[-1] if len(parts) > 1 else ""
            
            lead = {
                "Name": name_val,
                "First Name": first,
                "Surname": last,
                "Job Title": role_val or ("Chief Fire Officer" if "fire" in source_name.lower() else ("Permit Holder" if permit_val else "Registered Commercial Entity")),
                "Organisation": org_val,
                "URL": source_url or "https://environment.data.gov.uk",
                "Snippet": f"Source: {source_name} | Permit: {permit_val} | Address: {addr_val}" if permit_val or addr_val else f"Direct Export: {source_name}",
                "Phone": "",
                "Enriched Email": email_val if email_val else "Click '⚡ Batch Enrich'",
                "Deliverability Status": "🟢 Valid (Imported)" if email_val else "⚪ Not Checked",
                "Domain": "",
                "MX Host": ""
            }
            
            self.results_data.append(lead)
            added_count += 1
            
        self._refresh_text_display()
        self.notebook.select(self.tab_results)
        self.status_var.set(f"Sent {added_count} registry records to Leads Table (Tab 2). Click '⚡ Batch Enrich All' to discover emails.")
        messagebox.showinfo("Records Sent", f"✅ Successfully sent {added_count} records to Tab 2 (Leads Table)!\n\nYou can now click '⚡ Batch Enrich All' to automatically synthesize company domains, generate work emails, and verify mail servers.")

    def _send_opendata_to_verifier(self):
        if not self.opendata_raw_records:
            messagebox.showwarning("No Data", "No registry records loaded.")
            return
            
        # Check if email column exists
        headers_lower = [h.lower() for h in self.opendata_headers]
        email_col = None
        name_col = None
        org_col = None
        
        for idx, h in enumerate(headers_lower):
            if any(k in h for k in ['email', 'mail', 'e-mail']):
                email_col = idx
            elif any(k in h for k in ['name', 'director', 'officer']):
                name_col = idx
            elif any(k in h for k in ['organisation', 'organization', 'company', 'business']):
                org_col = idx

        added_count = 0
        for r in self.opendata_raw_records:
            email_val = r[email_col] if (email_col is not None and email_col < len(r)) else ""
            name_val = r[name_col] if (name_col is not None and name_col < len(r)) else ""
            org_val = r[org_col] if (org_col is not None and org_col < len(r)) else ""
            
            if email_val:
                parts = name_val.split()
                first = parts[0] if parts else ""
                last = parts[-1] if len(parts) > 1 else ""
                
                v_item = {
                    "Email": email_val,
                    "First Name": first,
                    "Surname": last,
                    "Full Name": name_val,
                    "Organisation": org_val,
                    "Job Title": "Registered Entity",
                    "Status": "⚪ Not Checked",
                    "Badge": "⚪ Not Checked",
                    "MX Host": "",
                    "Response Time": "-",
                    "SMTP Log": "Imported from Direct Registry"
                }
                self.verifier_data.append(v_item)
                added_count += 1
                
        if added_count > 0:
            self._refresh_verifier_display()
            self.notebook.select(self.tab_verifier)
            messagebox.showinfo("Sent to Verifier", f"✅ Sent {added_count} email addresses to Tab 3 (Verifier)!\n\nClick '🚀 Start MX/SMTP Verification' to test mail servers.")
        else:
            messagebox.showinfo("No Direct Emails", "No email column was detected in this registry.\n\nTip: Click '⚡ Send Records to Leads Table (Tab 2)' first, where the app will automatically resolve company domains and synthesize verified corporate emails!")

    def _export_opendata_csv(self):
        if not self.opendata_raw_records:
            messagebox.showwarning("No Data", "No records loaded to export.")
            return
            
        path = filedialog.asksaveasfilename(
            title="Export Registry Dataset as CSV",
            defaultextension=".csv",
            filetypes=[("CSV Spreadsheet", "*.csv"), ("All Files", "*.*")]
        )
        if not path:
            return
            
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if self.opendata_headers:
                    writer.writerow(self.opendata_headers)
                for r in self.opendata_raw_records:
                    writer.writerow(r)
            messagebox.showinfo("Export Successful", f"✅ Successfully exported {len(self.opendata_raw_records)} records to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save CSV file:\n{e}")

    def _clear_opendata_table(self):
        self.opendata_raw_records = []
        self.opendata_headers = []
        self.opendata_tree.delete(*self.opendata_tree.get_children())
        self.opendata_count_badge.configure(text="0 records loaded")
        self.opendata_status_var.set("Table cleared. Ready for next dataset.")

    # -------------------------------------------------------------
    # HELP & USER GUIDE DIALOGS
    # -------------------------------------------------------------
    def _open_user_guide_dialog(self):
        """Opens the full interactive In-App User Guide reader dialog with search, TOC, and syntax styling."""
        guide_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "USER_GUIDE.md")
        if not os.path.exists(guide_path):
            messagebox.showwarning("User Guide Not Found", f"Could not find USER_GUIDE.md at:\n{guide_path}\n\nPlease ensure USER_GUIDE.md exists in the application directory.")
            return

        try:
            with open(guide_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Error Reading Guide", f"Could not open USER_GUIDE.md:\n{e}")
            return

        dialog = tk.Toplevel(self)
        dialog.title("📖 Complete User Guide & Knowledge Base - Multi-Engine Lead & Advanced Dork Suite")
        dialog.geometry("1100x750")
        dialog.minsize(850, 520)

        # Center dialog relative to parent
        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 550
            y = self.winfo_y() + (self.winfo_height() // 2) - 375
            dialog.geometry(f"1100x750+{max(30, x)}+{max(30, y)}")
        except Exception:
            pass

        # Top Header & Search Bar Frame
        top_bar = ttk.Frame(dialog, padding=(12, 10, 12, 8))
        top_bar.pack(fill=tk.X)

        header_info = ttk.Frame(top_bar)
        header_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        guide_title = ttk.Label(header_info, text="📖 In-App User Guide & Beginner's Knowledge Base", font=("Segoe UI", 13, "bold"), foreground="#4F46E5")
        guide_title.pack(anchor=tk.W)
        guide_sub = ttk.Label(header_info, text="Browse the table of contents or search topics, dork patterns, deliverability badges, and workflows.", font=("Segoe UI", 8), foreground="#6B7280")
        guide_sub.pack(anchor=tk.W)

        # Search Controls
        search_frame = ttk.Frame(top_bar)
        search_frame.pack(side=tk.RIGHT)

        ttk.Label(search_frame, text="🔍 Search:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=22)
        search_entry.pack(side=tk.LEFT, padx=(0, 4))

        match_count_lbl = ttk.Label(search_frame, text="0 matches", font=("Segoe UI", 8), foreground="#6B7280", width=12)
        match_count_lbl.pack(side=tk.LEFT, padx=(0, 4))

        # Main Paned Window: Left TOC sidebar, Right scrollable Text
        paned = ttk.PanedWindow(dialog, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        # Left TOC Sidebar
        toc_frame = ttk.Frame(paned, width=280)
        paned.add(toc_frame, weight=1)

        toc_header_frame = ttk.Frame(toc_frame)
        toc_header_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(toc_header_frame, text="📑 Table of Contents", font=("Segoe UI", 10, "bold"), foreground="#1F2937").pack(side=tk.LEFT)

        toc_list_frame = ttk.Frame(toc_frame)
        toc_list_frame.pack(fill=tk.BOTH, expand=True)

        toc_scroll_y = ttk.Scrollbar(toc_list_frame, orient=tk.VERTICAL)
        toc_scroll_x = ttk.Scrollbar(toc_list_frame, orient=tk.HORIZONTAL)
        toc_listbox = tk.Listbox(toc_list_frame, yscrollcommand=toc_scroll_y.set, xscrollcommand=toc_scroll_x.set,
                                 font=("Segoe UI", 9), selectbackground="#4F46E5", selectforeground="#FFFFFF",
                                 activestyle="none", relief=tk.SOLID, borderwidth=1, highlightthickness=0)
        toc_scroll_y.config(command=toc_listbox.yview)
        toc_scroll_x.config(command=toc_listbox.xview)

        toc_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        toc_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        toc_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Right Text Viewer Frame
        text_frame = ttk.Frame(paned)
        paned.add(text_frame, weight=4)

        text_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        guide_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=text_scroll.set,
                             font=("Segoe UI", 10), bg="#FFFFFF", fg="#1F2937",
                             padx=18, pady=14, relief=tk.SOLID, borderwidth=1, highlightthickness=0)
        text_scroll.config(command=guide_text.yview)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        guide_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure rich styles in tk.Text
        guide_text.tag_configure("h1", font=("Segoe UI", 15, "bold"), foreground="#1E1B4B", spacing1=14, spacing3=6)
        guide_text.tag_configure("h2", font=("Segoe UI", 12, "bold"), foreground="#4338CA", spacing1=12, spacing3=4)
        guide_text.tag_configure("h3", font=("Segoe UI", 10, "bold"), foreground="#4F46E5", spacing1=8, spacing3=2)
        guide_text.tag_configure("h4", font=("Segoe UI", 9, "bold"), foreground="#374151", spacing1=6, spacing3=2)
        guide_text.tag_configure("bullet", lmargin1=16, lmargin2=28)
        guide_text.tag_configure("code_block", font=("Consolas", 9), background="#F8FAFC", foreground="#0F172A", lmargin1=20, lmargin2=20, rmargin=20, spacing1=4, spacing3=4)
        guide_text.tag_configure("quote", font=("Segoe UI", 9, "italic"), foreground="#4B5563", lmargin1=24, lmargin2=24, spacing1=3, spacing3=3)
        guide_text.tag_configure("separator", foreground="#CBD5E1")
        guide_text.tag_configure("search_match", background="#FEF08A", foreground="#000000")
        guide_text.tag_configure("active_match", background="#F59E0B", foreground="#FFFFFF")
        guide_text.tag_configure("section_highlight", background="#E0E7FF")

        # Parse markdown lines into formatted Text & TOC items
        toc_items = [] # list of (line_idx_in_text, display_text)
        lines = content.splitlines()
        in_code_block = False

        guide_text.config(state=tk.NORMAL)
        for line in lines:
            if line.startswith("```"):
                in_code_block = not in_code_block
                guide_text.insert(tk.END, line + "\n", "code_block")
                continue

            if in_code_block:
                guide_text.insert(tk.END, line + "\n", "code_block")
                continue

            if line.startswith("# "):
                curr_pos = guide_text.index(tk.INSERT)
                clean_title = line[2:].strip()
                guide_text.insert(tk.END, clean_title + "\n", "h1")
                toc_items.append((curr_pos, f"📘 {clean_title}"))
            elif line.startswith("## "):
                curr_pos = guide_text.index(tk.INSERT)
                clean_title = line[3:].strip()
                guide_text.insert(tk.END, clean_title + "\n", "h2")
                toc_items.append((curr_pos, f"  📁 {clean_title}"))
            elif line.startswith("### "):
                curr_pos = guide_text.index(tk.INSERT)
                clean_title = line[4:].strip()
                guide_text.insert(tk.END, clean_title + "\n", "h3")
                toc_items.append((curr_pos, f"    🔹 {clean_title}"))
            elif line.startswith("#### "):
                curr_pos = guide_text.index(tk.INSERT)
                clean_title = line[5:].strip()
                guide_text.insert(tk.END, clean_title + "\n", "h4")
            elif line.startswith("---"):
                guide_text.insert(tk.END, "─" * 65 + "\n", "separator")
            elif line.startswith("> "):
                guide_text.insert(tk.END, line[2:] + "\n", "quote")
            elif line.startswith("- ") or line.startswith("* "):
                guide_text.insert(tk.END, "  • " + line[2:] + "\n", "bullet")
            else:
                guide_text.insert(tk.END, line + "\n")

        guide_text.config(state=tk.DISABLED)

        # Populate TOC listbox
        for _, title in toc_items:
            toc_listbox.insert(tk.END, title)

        def _on_toc_select(event=None):
            sel = toc_listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx < len(toc_items):
                target_pos, _ = toc_items[idx]
                guide_text.see(target_pos)
                guide_text.tag_remove("section_highlight", "1.0", tk.END)
                # Highlight the target header line briefly
                line_no = target_pos.split(".")[0]
                guide_text.tag_add("section_highlight", f"{line_no}.0", f"{line_no}.end")

        toc_listbox.bind("<<ListboxSelect>>", _on_toc_select)

        # Search Highlighting & Navigation Logic
        search_matches = [] # list of start positions
        current_match_idx = [-1]

        def _perform_search(event=None):
            query = search_var.get().strip()
            guide_text.tag_remove("search_match", "1.0", tk.END)
            guide_text.tag_remove("active_match", "1.0", tk.END)
            search_matches.clear()
            current_match_idx[0] = -1

            if not query:
                match_count_lbl.config(text="0 matches")
                return

            pos = "1.0"
            while True:
                pos = guide_text.search(query, pos, stopindex=tk.END, nocase=True)
                if not pos:
                    break
                end_pos = f"{pos}+{len(query)}c"
                guide_text.tag_add("search_match", pos, end_pos)
                search_matches.append(pos)
                pos = end_pos

            total = len(search_matches)
            if total > 0:
                current_match_idx[0] = 0
                _highlight_active_match()
                match_count_lbl.config(text=f"1 of {total} matches", foreground="#15803D")
            else:
                match_count_lbl.config(text="0 matches", foreground="#DC2626")

        def _highlight_active_match():
            if not search_matches or current_match_idx[0] < 0:
                return
            guide_text.tag_remove("active_match", "1.0", tk.END)
            curr_pos = search_matches[current_match_idx[0]]
            query_len = len(search_var.get().strip())
            end_pos = f"{curr_pos}+{query_len}c"
            guide_text.tag_add("active_match", curr_pos, end_pos)
            guide_text.see(curr_pos)
            total = len(search_matches)
            match_count_lbl.config(text=f"{current_match_idx[0] + 1} of {total} matches", foreground="#15803D")

        def _next_match(event=None):
            if not search_matches:
                return
            current_match_idx[0] = (current_match_idx[0] + 1) % len(search_matches)
            _highlight_active_match()

        def _prev_match(event=None):
            if not search_matches:
                return
            current_match_idx[0] = (current_match_idx[0] - 1 + len(search_matches)) % len(search_matches)
            _highlight_active_match()

        def _clear_search(event=None):
            search_var.set("")
            guide_text.tag_remove("search_match", "1.0", tk.END)
            guide_text.tag_remove("active_match", "1.0", tk.END)
            search_matches.clear()
            current_match_idx[0] = -1
            match_count_lbl.config(text="0 matches", foreground="#6B7280")

        btn_prev = ttk.Button(search_frame, text="▲", width=3, command=_prev_match)
        btn_prev.pack(side=tk.LEFT, padx=1)
        btn_next = ttk.Button(search_frame, text="▼", width=3, command=_next_match)
        btn_next.pack(side=tk.LEFT, padx=1)
        btn_clear = ttk.Button(search_frame, text="✕", width=3, command=_clear_search)
        btn_clear.pack(side=tk.LEFT, padx=(1, 0))

        search_entry.bind("<Return>", lambda e: _next_match() if search_matches else _perform_search())
        search_entry.bind("<Shift-Return>", _prev_match)
        search_var.trace_add("write", lambda *args: _perform_search())

        # Bottom Action Bar
        bottom_bar = ttk.Frame(dialog, padding=(12, 6, 12, 10))
        bottom_bar.pack(fill=tk.X)

        status_lbl = ttk.Label(bottom_bar, text=f"📁 Source: {os.path.basename(guide_path)} ({len(lines)} lines)", font=("Segoe UI", 8), foreground="#6B7280")
        status_lbl.pack(side=tk.LEFT)

        def _copy_all_guide():
            try:
                self.clipboard_clear()
                self.clipboard_append(content)
                messagebox.showinfo("Copied", "📋 The complete User Guide text has been copied to your clipboard!", parent=dialog)
            except Exception as e:
                messagebox.showerror("Clipboard Error", f"Could not copy text:\n{e}", parent=dialog)

        btn_copy = ttk.Button(bottom_bar, text="📋 Copy Full Guide", style="Secondary.TButton", command=_copy_all_guide)
        btn_copy.pack(side=tk.RIGHT, padx=(4, 0))

        btn_ext = ttk.Button(bottom_bar, text="🌐 Open in Default App / Browser", style="Secondary.TButton", command=self._open_user_guide_external)
        btn_ext.pack(side=tk.RIGHT, padx=4)

        btn_close = ttk.Button(bottom_bar, text="✕ Close", style="Primary.TButton", command=dialog.destroy)
        btn_close.pack(side=tk.RIGHT, padx=4)

    def _open_user_guide_external(self):
        """Opens USER_GUIDE.md directly using the system's default markdown reader or browser."""
        guide_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "USER_GUIDE.md")
        if not os.path.exists(guide_path):
            messagebox.showwarning("File Not Found", f"Could not locate USER_GUIDE.md at:\n{guide_path}")
            return
        try:
            if hasattr(os, "startfile"):
                os.startfile(guide_path)
            else:
                webbrowser.open(f"file:///{urllib.parse.quote(guide_path.replace(os.sep, '/'))}")
        except Exception as e:
            messagebox.showerror("Open Error", f"Could not launch file:\n{e}")

    def _open_readme_external(self):
        """Opens README.md directly using the system's default viewer."""
        readme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
        if not os.path.exists(readme_path):
            messagebox.showwarning("File Not Found", f"Could not locate README.md at:\n{readme_path}")
            return
        try:
            if hasattr(os, "startfile"):
                os.startfile(readme_path)
            else:
                webbrowser.open(f"file:///{urllib.parse.quote(readme_path.replace(os.sep, '/'))}")
        except Exception as e:
            messagebox.showerror("Open Error", f"Could not launch file:\n{e}")

    def _show_quick_start_dialog(self):
        """Displays a clean modal with the 4-step dummy-proof quick start walkthrough."""
        dialog = tk.Toplevel(self)
        dialog.title("⚡ Quick Start: 4-Step Walkthrough")
        dialog.geometry("750x520")
        dialog.resizable(False, False)

        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 375
            y = self.winfo_y() + (self.winfo_height() // 2) - 260
            dialog.geometry(f"750x520+{max(30, x)}+{max(30, y)}")
        except Exception:
            pass

        frame = ttk.Frame(dialog, padding="16")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="⚡ Quick Start Walkthrough (In 4 Easy Steps)", font=("Segoe UI", 13, "bold"), foreground="#4F46E5").pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(frame, text="Follow these four steps to start extracting and enriching verified leads immediately:", font=("Segoe UI", 9), foreground="#6B7280").pack(anchor=tk.W, pady=(0, 10))

        steps = [
            ("Step 1: Pick a Preset or Build Your Query", "In Tab 1 (Query Builder), select a quick preset from the 'Templates' menu or dropdown (e.g. 'Materials Recovery Facilities' or 'Fire & Rescue IT Leaders'). Alternatively, enter your search keywords.", "#4F46E5"),
            ("Step 2: Run Search & Extract Contacts", "Choose your search engine (Google, Bing, Brave, DDG) and click '🔍 Run Search & Scrape'. The app pulls names, job titles, companies, and URLs directly into Tab 2.", "#2563EB"),
            ("Step 3: Batch Enrich Missing Emails", "Switch to Tab 2 (Results & Enrichment) and click '⚡ Batch Enrich All Contacts'. The app automatically matches corporate domains, constructs standard email patterns, and verifies mailbox deliverability.", "#7C3AED"),
            ("Step 4: Verify & Export Clean Spreadsheets", "Inspect the deliverability badges (🟢 High, 🟡 Catch-All, 🔴 Undeliverable). Click '💾 Save / Export Enriched CSV' to download your final clean spreadsheet for your CRM or outreach campaign!", "#059669")
        ]

        for title, desc, color in steps:
            s_frame = ttk.LabelFrame(frame, text=f" {title} ", padding=(10, 6))
            s_frame.pack(fill=tk.X, pady=4)
            lbl = ttk.Label(s_frame, text=desc, font=("Segoe UI", 9), wraplength=680, justify=tk.LEFT)
            lbl.pack(anchor=tk.W)

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=(12, 0))

        btn_full = ttk.Button(btn_row, text="📖 Open Full User Guide", style="Secondary.TButton", command=lambda: [dialog.destroy(), self._open_user_guide_dialog()])
        btn_full.pack(side=tk.LEFT)

        btn_ok = ttk.Button(btn_row, text="Got It, Let's Start!", style="Primary.TButton", command=dialog.destroy)
        btn_ok.pack(side=tk.RIGHT)

    def _show_deliverability_guide(self):
        """Displays a modal explaining email verification badges and SMTP handshake safety."""
        dialog = tk.Toplevel(self)
        dialog.title("🛡️ Email Deliverability Badges & Verification Guide")
        dialog.geometry("780x560")
        dialog.resizable(False, False)

        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 390
            y = self.winfo_y() + (self.winfo_height() // 2) - 280
            dialog.geometry(f"780x560+{max(30, x)}+{max(30, y)}")
        except Exception:
            pass

        frame = ttk.Frame(dialog, padding="16")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="🛡️ Understanding Email Deliverability Badges", font=("Segoe UI", 13, "bold"), foreground="#15803D").pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(frame, text="When email addresses are verified in Tab 2 or Tab 3, they receive one of four badges:", font=("Segoe UI", 9), foreground="#6B7280").pack(anchor=tk.W, pady=(0, 10))

        badges = [
            ("🟢 High Deliverability (SMTP Validated)", "#DCFCE7", "#15803D", "The recipient mail server (MX) explicitly accepted the recipient address (SMTP 250 OK) without sending any actual email. Safe to send."),
            ("🟡 Catch-All Domain (MX Verified)", "#FEF3C7", "#B45309", "The domain has active mail servers, but accepts all addresses without verifying individual mailboxes. Safe to send with mild bounce caution."),
            ("🔵 Syntax / Format Valid", "#DBEAFE", "#1E40AF", "The email has a valid structural format (name@domain.com) and valid TLD, but mail server verification was skipped or timed out."),
            ("🔴 Undeliverable / Mailbox Rejected", "#FEE2E2", "#B91C1C", "The domain does not exist, has no MX records, or the server explicitly returned SMTP 550 Mailbox Unavailable. Do not send.")
        ]

        for title, bg, fg, desc in badges:
            b_box = tk.Frame(frame, bg=bg, highlightbackground=fg, highlightthickness=1, padx=10, pady=8)
            b_box.pack(fill=tk.X, pady=4)
            t_lbl = tk.Label(b_box, text=title, font=("Segoe UI", 10, "bold"), bg=bg, fg=fg)
            t_lbl.pack(anchor=tk.W)
            d_lbl = tk.Label(b_box, text=desc, font=("Segoe UI", 9), bg=bg, fg="#1F2937", wraplength=720, justify=tk.LEFT)
            d_lbl.pack(anchor=tk.W, pady=(2, 0))

        # Handshake note
        note_frame = ttk.LabelFrame(frame, text=" 💡 Zero Spam Guarantee ", padding=(10, 6))
        note_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(note_frame, text="Our live verification uses a non-intrusive SMTP RCPT TO handshake. It disconnects before any message data is sent (RSET / QUIT), meaning zero spam is delivered and zero recipient inboxes are pinged.", font=("Segoe UI", 8), wraplength=720).pack(anchor=tk.W)

        btn_close = ttk.Button(frame, text="Close Guide", style="Primary.TButton", command=dialog.destroy)
        btn_close.pack(anchor=tk.E, pady=(12, 0))

    def _show_opendata_guide(self):
        """Displays a modal explaining how to use Tab 4 for direct open government registers."""
        dialog = tk.Toplevel(self)
        dialog.title("📥 Direct Open Data & Public Registers Guide")
        dialog.geometry("780x520")
        dialog.resizable(False, False)

        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 390
            y = self.winfo_y() + (self.winfo_height() // 2) - 260
            dialog.geometry(f"780x520+{max(30, x)}+{max(30, y)}")
        except Exception:
            pass

        frame = ttk.Frame(dialog, padding="16")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="📥 Direct Open Data & Public Registers (Tab 4)", font=("Segoe UI", 13, "bold"), foreground="#2563EB").pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(frame, text="How to bypass search engine rate limits and pull complete official datasets directly:", font=("Segoe UI", 9), foreground="#6B7280").pack(anchor=tk.W, pady=(0, 10))

        points = [
            ("1. Why Use Open Data Registers?", "Instead of querying Google pages (which can trigger CAPTCHAs), official regulators (Environment Agency, SEPA, NRW) publish complete CSV/ZIP datasets containing company names, permit numbers, and postcodes."),
            ("2. Pre-Configured Sources", "Tab 4 comes loaded with official public registries for England (EA Permitted Waste Operations, Waste Carriers & Brokers), Scotland (SEPA Register), Wales (NRW Register), and UK central data.gov.uk."),
            ("3. Download & Auto-Extract", "Click '⬇️ Download / Open Selected Source'. If a direct CSV or ZIP URL is supplied, the suite downloads, unzips in-memory, and loads all records into the live searchable table instantly."),
            ("4. Add Custom Registry URLs", "Paste any open government dataset or public CSV URL into the 'Custom Registry URL' box and click '💾 Save & Add to Register Sources' to store it forever in your dropdown list.")
        ]

        for title, desc in points:
            p_frame = ttk.LabelFrame(frame, text=f" {title} ", padding=(10, 6))
            p_frame.pack(fill=tk.X, pady=4)
            ttk.Label(p_frame, text=desc, font=("Segoe UI", 9), wraplength=720, justify=tk.LEFT).pack(anchor=tk.W)

        btn_close = ttk.Button(frame, text="Close Guide", style="Primary.TButton", command=dialog.destroy)
        btn_close.pack(anchor=tk.E, pady=(12, 0))

    def _show_about_dialog(self):
        """Displays the application About modal dialog."""
        dialog = tk.Toplevel(self)
        dialog.title("ℹ️ About Multi-Engine Lead & Advanced Dork Suite")
        dialog.geometry("560x380")
        dialog.resizable(False, False)

        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 280
            y = self.winfo_y() + (self.winfo_height() // 2) - 190
            dialog.geometry(f"560x380+{max(30, x)}+{max(30, y)}")
        except Exception:
            pass

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="⚡ Multi-Engine Lead & Advanced Dork Suite", font=("Segoe UI", 13, "bold"), foreground="#4F46E5").pack(anchor=tk.W, pady=(0, 2))
        ttk.Label(frame, text="Version 3.2.0 • Professional Edition", font=("Segoe UI", 9), foreground="#6B7280").pack(anchor=tk.W, pady=(0, 10))

        about_text = (
            "An all-in-one multi-engine lead generation, contact extraction, corporate email "
            "enrichment, live SMTP mailbox verification, and direct open government dataset suite.\n\n"
            "• Search Engines: Google, Bing, DuckDuckGo, Brave, Yahoo, Tor/Onion\n"
            "• Enrichment: 100+ UK public sector domain registries, Hunter.io, Abstract API\n"
            "• Deliverability: RFC 5322 syntax validation, DNS MX resolution, zero-spam SMTP handshake\n"
            "• Open Data: Direct integration with EA, SEPA, NRW, and data.gov.uk bulk datasets\n\n"
            "Designed for sales teams, researchers, journalists, and recruitment specialists."
        )
        ttk.Label(frame, text=about_text, font=("Segoe UI", 9), wraplength=510, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 14))

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="📖 Open Full User Guide", style="Secondary.TButton", command=lambda: [dialog.destroy(), self._open_user_guide_dialog()]).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Close", style="Primary.TButton", command=dialog.destroy).pack(side=tk.RIGHT)

    # -------------------------------------------------------------
    # QUERY BUILDER ENGINE
    # -------------------------------------------------------------
    def _append_operator_to_query(self, operator_snippet):
        current = self.assembled_query_var.get().strip()
        new_q = f"{current}{operator_snippet}" if current else operator_snippet.strip()
        self.assembled_query_var.set(new_q)

    def _on_engine_selected(self, event=None):
        """Updates active engine variable and status bar when a search engine is selected from dropdown."""
        val = self.engine_combo.get() if hasattr(self, "engine_combo") else ""
        if "Google" in val:
            engine = "Google"
        elif "Bing" in val:
            engine = "Bing"
        elif "DuckDuckGo" in val:
            engine = "DuckDuckGo"
        elif "Brave" in val:
            engine = "Brave"
        elif "Yahoo" in val:
            engine = "Yahoo"
        elif "Ahmia" in val:
            engine = "Ahmia"
        elif "Yandex" in val:
            engine = "Yandex"
        else:
            engine = "Google"
        self.engine_var.set(engine)
        self.status_var.set(f"🌐 Search Engine Selected: {engine}. Ready to search.")

    def _on_criteria_tab_changed(self, event=None):
        """Switches active criteria mode and updates assembled query when switching subtabs."""
        try:
            sel = self.criteria_notebook.select()
            sel_idx = self.criteria_notebook.index(sel)
            if sel_idx == 0:
                self.active_criteria_mode = "targeted"
            else:
                self.active_criteria_mode = "generalized"
            self._rebuild_query()
        except Exception:
            pass

    def _on_gen_category_selected(self, event=None):
        val = self.gen_category_combo.get()
        if "Materials Recovery & Waste" in val:
            self.gen_industry_var.set('("Materials Recovery Facility" OR "waste transfer station" OR "commercial recycling facility")')
        elif "Plastics Recycling" in val:
            self.gen_industry_var.set('("plastics recycling" OR "polymer reprocessing" OR "plastic granulate" OR "plastic waste processing" OR "polymer recycling")')
        elif "Wood, Timber & Paper" in val:
            self.gen_industry_var.set('("wood recycling" OR "timber processing" OR "paper mill" OR "cardboard recycling" OR "biomass wood chip")')
        elif "Farms, Agriculture" in val:
            self.gen_industry_var.set('("grain drying" OR "agricultural storage" OR "grain silo" OR "farming estate" OR "straw storage" OR "grain store")')
        elif "Warehouse Management" in val or "Logistics & Distribution" in val:
            self.gen_industry_var.set('("warehouse management" OR "3PL fulfillment" OR "logistics distribution centre" OR "bonded warehouse" OR "bulk storage warehouse")')
        elif "Outside Storage" in val:
            self.gen_industry_var.set('("outside storage" OR "open yard storage" OR "bulk materials storage" OR "aggregate storage yard" OR "pallet storage depot")')
        elif "Tyre Recycling" in val:
            self.gen_industry_var.set('("tyre recycling" OR "tire processing" OR "rubber crumb" OR "pyrolysis plant" OR "retreading depot")')
        elif "Battery Storage" in val:
            self.gen_industry_var.set('("battery energy storage" OR "BESS facility" OR "lithium battery recycling" OR "battery storage facility" OR "grid battery site")')
        elif "Textiles, Fabric" in val:
            self.gen_industry_var.set('("textile recycling" OR "rag processing" OR "clothing baling" OR "fabric reprocessing" OR "fibre recycling")')
        elif "Food Processing, Mills" in val:
            self.gen_industry_var.set('("flour mill" OR "industrial bakery" OR "food processing plant" OR "feed mill" OR "grain milling")')
        elif "Chemical & Hazmat" in val or "Chemical & Hazardous" in val:
            self.gen_industry_var.set('("chemical storage" OR "COMAH site" OR "bulk liquid terminal" OR "hazardous substances" OR "solvents storage")')
        elif "Metal Scrap" in val or "Metal Recycling" in val:
            self.gen_industry_var.set('("scrap metal yard" OR "metal recycling facility" OR "authorised treatment facility" OR "ATF depollution" OR "car dismantler")')
        elif "Transport & Fleet" in val:
            self.gen_industry_var.set('("fleet depot" OR "transport depot" OR "haulage depot" OR "operating centre")')
        elif "Industrial Manufacturing" in val:
            self.gen_industry_var.set('("manufacturing plant" OR "processing facility" OR "production site" OR "industrial estate")')
        elif "Energy, Biomass" in val:
            self.gen_industry_var.set('("energy from waste" OR "biomass plant" OR "anaerobic digestion" OR "EfW facility")')
        elif "Data Centers" in val:
            self.gen_industry_var.set('("data centre" OR "server farm" OR "colocation facility" OR "telecoms exchange")')
        elif "Clear" in val:
            self.gen_industry_var.set("")
        self._rebuild_query()

    def _on_gen_scale_selected(self, event=None):
        val = self.gen_scale_combo.get()
        if "Multi-Site" in val:
            self.gen_scale_var.set('("multiple sites" OR "depots across" OR "nationwide" OR "head office")')
        elif "Regional Hubs" in val:
            self.gen_scale_var.set('("regional depots" OR "branches across" OR "operating centres" OR "facilities across")')
        elif "Corporate HQ" in val:
            self.gen_scale_var.set('("head office" OR "corporate headquarters" OR "group operations" OR "registered office")')
        elif "UK-Wide" in val:
            self.gen_scale_var.set('("national coverage" OR "uk-wide" OR "across the uk" OR "network of facilities")')
        elif "None" in val:
            self.gen_scale_var.set("")
        self._rebuild_query()

    def _on_gen_geo_selected(self, event=None):
        val = self.gen_geo_combo.get()
        if "United Kingdom" in val:
            self.gen_geo_var.set('("United Kingdom" OR "UK" OR "England" OR "Scotland" OR "Wales")')
        elif "England & Greater" in val:
            self.gen_geo_var.set('("England" OR "London" OR "South East" OR "Midlands" OR "North West")')
        elif "Scotland & Northern" in val:
            self.gen_geo_var.set('("Scotland" OR "Northern Ireland" OR "Edinburgh" OR "Glasgow" OR "Belfast")')
        elif "United States" in val:
            self.gen_geo_var.set('("United States" OR "USA" OR "nationwide" OR "headquarters")')
        elif "Europe" in val:
            self.gen_geo_var.set('("Europe" OR "EU" OR "Germany" OR "France" OR "Netherlands")')
        elif "Worldwide" in val:
            self.gen_geo_var.set("")
        self._rebuild_query()

    def _on_gen_exclude_selected(self, event=None):
        val = self.gen_exclude_combo.get()
        if "Municipal/Council Tips & .gov.uk" in val:
            self.gen_exclude_var.set("-council -civic -household -tip -hwrc -.gov.uk -jobs -recruiting -indeed -careers -vacancies -fish4")
        elif "Council Tips + Job" in val:
            self.gen_exclude_var.set("-council -civic -household -tip -hwrc -.gov.uk -jobs -recruiting -indeed -careers -vacancies -totaljobs -reed -fish4")
        elif "Job & Recruitment" in val:
            self.gen_exclude_var.set("-jobs -recruiting -indeed -careers -vacancies -totaljobs -reed -fish4 -cv-library")
        elif "Public Sector" in val:
            self.gen_exclude_var.set("-gov -council -nhs -police -.gov.uk -.nhs.uk")
        elif "Directory" in val:
            self.gen_exclude_var.set("-yell -thomsonlocal -checkatrade -192.com -trustpilot")
        elif "No Exclusions" in val:
            self.gen_exclude_var.set("")
        self._rebuild_query()

    def _load_waste_facility_example(self):
        """Loads the generalized waste & materials recovery facility search query."""
        self.criteria_notebook.select(self.subtab_generalized)
        self.active_criteria_mode = "generalized"
        self._updating_query = True
        self.gen_industry_var.set('("Materials Recovery Facility" OR "waste transfer station" OR "commercial recycling facility")')
        self.gen_scale_var.set('("multiple sites" OR "depots across" OR "nationwide" OR "head office")')
        self.gen_geo_var.set('("United Kingdom" OR "UK" OR "England" OR "Scotland" OR "Wales")')
        self.gen_exclude_var.set('-council -civic -household -tip -hwrc -.gov.uk -jobs -recruiting -indeed -careers -vacancies -fish4')
        self.gen_intext_var.set("")
        self.gen_inurl_var.set("")
        self.gen_site_var.set("")
        self.gen_filetype_var.set("None")
        self.gen_email_dork_var.set(False)
        self.gen_phone_dork_var.set(False)
        if hasattr(self, "gen_category_combo"):
            self.gen_category_combo.current(1)
        if hasattr(self, "gen_scale_combo"):
            self.gen_scale_combo.current(1)
        if hasattr(self, "gen_geo_combo"):
            self.gen_geo_combo.current(1)
        if hasattr(self, "gen_exclude_combo"):
            self.gen_exclude_combo.current(1)
        self._updating_query = False
        self._rebuild_query()
        self.status_var.set("Loaded Generalized Search: Waste & Materials Recovery Facilities (UK)")

    def _reset_generalized_form(self):
        """Resets all fields in the Generalized Search Criteria tab."""
        self._updating_query = True
        self.gen_industry_var.set("")
        self.gen_scale_var.set("")
        self.gen_geo_var.set("")
        self.gen_exclude_var.set("")
        self.gen_intext_var.set("")
        self.gen_inurl_var.set("")
        self.gen_site_var.set("")
        self.gen_filetype_var.set("None")
        self.gen_email_dork_var.set(False)
        self.gen_phone_dork_var.set(False)
        if hasattr(self, "gen_category_combo"):
            self.gen_category_combo.set("Choose Preset Category...")
        if hasattr(self, "gen_scale_combo"):
            self.gen_scale_combo.set("Choose Scale...")
        if hasattr(self, "gen_geo_combo"):
            self.gen_geo_combo.set("Choose Region...")
        if hasattr(self, "gen_exclude_combo"):
            self.gen_exclude_combo.set("Choose Exclusion Pattern...")
        self.assembled_query_var.set("")
        self._updating_query = False
        self.status_var.set("Generalized search criteria cleared.")

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
        if len(items) > 1 or (len(items) == 1 and not items[0].startswith('"')):
            formatted = f'({formatted})'
        string_var.set(formatted)
        self._rebuild_query()

    def _rebuild_query(self):
        """Assembles all form fields from the active criteria tab into a unified search query."""
        if self._updating_query:
            return
            
        parts = []
        
        if self.active_criteria_mode == "targeted":
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
                
        else:
            # Generalized Criteria Mode (Tab 2)
            # Group 1: Facility / Industry / Sector Terms
            ind = self.gen_industry_var.get().strip()
            if ind:
                if not (ind.startswith("(") and ind.endswith(")")) and " OR " in ind:
                    ind = f"({ind})"
                parts.append(ind)
                
            # Group 2: Operational Scale / Multi-Site Scope
            scale = self.gen_scale_var.get().strip()
            if scale:
                if not (scale.startswith("(") and scale.endswith(")")) and " OR " in scale:
                    scale = f"({scale})"
                parts.append(scale)
                
            # Group 3: Geographic / Regional Scope
            geo = self.gen_geo_var.get().strip()
            if geo and "(Worldwide" not in geo:
                if not (geo.startswith("(") and geo.endswith(")")) and " OR " in geo:
                    geo = f"({geo})"
                parts.append(geo)
                
            # Optional intext
            intext = self.gen_intext_var.get().strip()
            if intext:
                if not intext.startswith("intext:"):
                    intext = f'intext:"{intext.strip(chr(34))}"'
                parts.append(intext)
                
            # Optional inurl
            inurl = self.gen_inurl_var.get().strip()
            if inurl:
                if not inurl.startswith("inurl:"):
                    inurl = f'inurl:{inurl}'
                parts.append(inurl)
                
            # Optional site
            site = self.gen_site_var.get().strip()
            if site and "(All" not in site:
                parts.append(site)
                
            # Email hunting
            if self.gen_email_dork_var.get():
                parts.append('("@gmail.com" OR "@yahoo.com" OR "@outlook.com" OR "@hotmail.com" OR "email me at")')
                
            # Phone hunting
            if self.gen_phone_dork_var.get():
                parts.append('("phone" OR "tel" OR "mobile" OR "contact")')
                
            # Filetype
            ft = self.gen_filetype_var.get().strip()
            if ft and ft != "None":
                parts.append(ft)
                
            # Exclusions
            ex = self.gen_exclude_var.get().strip()
            if ex:
                parts.append(ex)
                
        # Automatic Job Board exclusions if toggle is active and not already excluded
        if getattr(self, "exclude_job_boards_var", None) and self.exclude_job_boards_var.get():
            combined_q = " ".join(parts).lower()
            if "-job" not in combined_q and "linkedin.com/in/" not in combined_q:
                parts.append("-jobs -recruitment -vacancies -careers")
                
        final_query = " ".join(parts)
        self._updating_query = True
        self.assembled_query_var.set(final_query)
        self._updating_query = False
        self.assembled_query_var.set(final_query)
        self._updating_query = False

    def _on_preset_selected(self, event=None):
        combo_val = self.preset_combo.get()
        if "TARGETED" in combo_val or "GENERALIZED" in combo_val or "ENVIRONMENTAL" in combo_val or "FIRE & SMOKE" in combo_val:
            return
        if "Clean / Blank" in combo_val:
            self._reset_builder()
        # High Fire & Smoke Hazard Generalized Multi-Site Industries
        elif "Materials Recovery" in combo_val:
            self._load_preset("gen_waste")
        elif "Plastics Recycling" in combo_val:
            self._load_preset("gen_plastics")
        elif "Wood, Timber & Paper" in combo_val:
            self._load_preset("gen_wood_paper")
        elif "Farms, Agriculture" in combo_val:
            self._load_preset("gen_farms")
        elif "Warehouse Management" in combo_val or "Logistics & Distribution" in combo_val:
            self._load_preset("gen_warehouses")
        elif "Outside Storage" in combo_val:
            self._load_preset("gen_outside_storage")
        elif "Tyre Recycling" in combo_val:
            self._load_preset("gen_tyres")
        elif "Battery Storage" in combo_val:
            self._load_preset("gen_batteries")
        elif "Textiles, Fabric" in combo_val:
            self._load_preset("gen_textiles")
        elif "Food Processing, Mills" in combo_val:
            self._load_preset("gen_food_mills")
        elif "Chemical & Hazmat" in combo_val or "Chemical & Hazardous" in combo_val:
            self._load_preset("gen_chemical")
        elif "Metal Scrap" in combo_val or "Scrap Metal" in combo_val:
            self._load_preset("gen_scrap")
        elif "Commercial Transport" in combo_val or "Transport & Fleet" in combo_val:
            self._load_preset("gen_fleet")
        elif "Manufacturing & Industrial" in combo_val or "Industrial Manufacturing" in combo_val:
            self._load_preset("gen_manufacturing")
        elif "Energy, Biomass" in combo_val:
            self._load_preset("gen_energy")
        elif "Data Centers" in combo_val:
            self._load_preset("gen_datacenters")
        # UK Environmental Registers (EA / SEPA / NRW)
        elif "EA: Waste Permitting" in combo_val:
            self._load_preset("ea_waste_ops")
        elif "EA: Waste Carriers" in combo_val:
            self._load_preset("ea_waste_carriers")
        elif "SEPA: Waste Carriers" in combo_val:
            self._load_preset("sepa_waste")
        elif "NRW: Waste Permitting" in combo_val:
            self._load_preset("nrw_waste")
        elif "Combined UK Regulators" in combo_val:
            self._load_preset("combined_uk_env_registers")
        elif "National Highways Leaders" in combo_val:
            self._load_preset("national_highways_leaders")
        elif "National Highways: Schemes" in combo_val:
            self._load_preset("national_highways_gov")
        elif "National Highways & Road" in combo_val:
            self._load_preset("gen_highways")
        # Targeted Presets (Tab 1)
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
        if preset_key == "custom":
            self._reset_builder()
            return
            
        if preset_key == "gen_waste":
            self._load_waste_facility_example()
            return

        self._updating_query = True
        mode, p_data = data_loader.get_preset_data(preset_key)

        if mode == "targeted":
            self.criteria_notebook.select(self.subtab_targeted)
            self.active_criteria_mode = "targeted"
            self.site_preset_var.set(p_data.get("site", ""))
            self.org_var.set(p_data.get("org", ""))
            self.titles_var.set(p_data.get("titles", ""))
            self.location_var.set(p_data.get("location", ""))
            self.email_dork_var.set(bool(p_data.get("email_dork", False)))
            self.phone_dork_var.set(bool(p_data.get("phone_dork", False)))
            self.custom_email_domain_var.set(p_data.get("custom_email_domain", ""))
            self.exclude_var.set(p_data.get("exclude", ""))
            self.filetype_var.set(p_data.get("filetype", "None"))
        elif mode == "generalized":
            self.criteria_notebook.select(self.subtab_generalized)
            self.active_criteria_mode = "generalized"
            self.gen_industry_var.set(p_data.get("industry", ""))
            self.gen_scale_var.set(p_data.get("scale", ""))
            self.gen_geo_var.set(p_data.get("geo", ""))
            self.gen_exclude_var.set(p_data.get("exclude", ""))
            self.gen_intext_var.set(p_data.get("intext", ""))
            self.gen_inurl_var.set(p_data.get("inurl", ""))
            self.gen_site_var.set(p_data.get("site", ""))
            self.gen_filetype_var.set(p_data.get("filetype", "None"))
            self.gen_email_dork_var.set(bool(p_data.get("email_dork", False)))
            self.gen_phone_dork_var.set(bool(p_data.get("phone_dork", False)))
        else:
            self._reset_builder()

        self._updating_query = False
        self._rebuild_query()
        self.status_var.set(f"Loaded search template: {preset_key.replace('_', ' ').title()}")

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
                return f"https://duckduckgo.com/?q={encoded_query}&kl=uk-en&ia=web"
            else:
                return f"https://duckduckgo.com/?q={encoded_query}&kl=uk-en&ia=web&s={page * 30}"
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
            cards = (soup.find_all("article") or 
                     soup.find_all("li", attrs={"data-layout": "organic"}) or 
                     soup.find_all("div", class_=re.compile(r"result")) or 
                     soup.find_all("td", class_="result-snippet"))
            for card in cards:
                t_el = (card.find("h2") or 
                        card.find("h3") or 
                        card.find("a", attrs={"data-testid": "result-title-a"}) or 
                        card.find("a", class_=re.compile(r"title|url|snippet")))
                if not t_el: continue
                raw_title = t_el.get_text(strip=True)
                a = (card.find("a", attrs={"data-testid": "result-title-a"}) or 
                     card.find("a", class_=re.compile(r"title|url|snippet")) or 
                     card.find("a", href=True))
                if not a: continue
                href = a.get("href", "")
                if "duckduckgo.com/l/?uddg=" in href:
                    parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    href = urllib.parse.unquote(parsed_qs.get("uddg", [href])[0])
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
            
            # Check if this lead originates from a job recruitment aggregator board (e.g. Fish4, Indeed, Reed, Totaljobs)
            if getattr(self, "exclude_job_boards_var", None) and self.exclude_job_boards_var.get():
                if is_job_posting_url(href):
                    continue
            
            combined_text = f"{raw_title} {snippet}"
            emails = EMAIL_PATTERN.findall(combined_text)
            phones = extract_phones_from_soup_or_text(text=combined_text)
            
            # Check if this lead is a LinkedIn profile vs an Open-Web / Corporate / Facility result
            is_linkedin = "linkedin.com/in/" in href or " - LinkedIn" in raw_title or " | LinkedIn" in raw_title
            
            # 1. Extract destination URL domain
            url_domain = ""
            if href:
                try:
                    parsed_netloc = urllib.parse.urlparse(href).netloc.lower()
                    clean_netloc = re.sub(r'^www\.', '', parsed_netloc)
                    non_corporate = ['google.', 'bing.', 'duckduckgo.', 'brave.', 'yahoo.', 'yandex.', 'ahmia.', 'linkedin.', 'youtube.', 'facebook.', 'twitter.', 'x.com', 'instagram.', 'wikipedia.']
                    if clean_netloc and not any(se in clean_netloc for se in non_corporate):
                        url_domain = clean_netloc
                except Exception:
                    pass
            
            clean_title = raw_title.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()
            
            if is_linkedin:
                # Standard LinkedIn person lead: Name - Role - Company
                parts = [p.strip() for p in clean_title.split(" - ")]
                name = parts[0] if len(parts) > 0 else clean_title
                headline = parts[1] if len(parts) > 1 else ""
                company = parts[2] if len(parts) > 2 else ""
                
                # If company missing, attempt parsing from headline (e.g. "Head of IT at Greater Manchester Fire")
                if not company and " at " in headline:
                    company = headline.split(" at ")[-1].strip()
                elif not company and " @ " in headline:
                    company = headline.split(" @ ")[-1].strip()
                    
                first_name, last_name, display_name = parse_lead_name(name)
                
                industry = self.enrich_industry_var.get() if hasattr(self, "enrich_industry_var") else "fire"
                custom_dom = self.custom_email_domain_var.get() if hasattr(self, "custom_email_domain_var") else ""
                resolved_dom = custom_dom.strip().lower().replace("@", "") if (custom_dom and custom_dom.strip()) else resolve_organization_domain(company, headline, snippet, industry)
            else:
                # Open-Web Corporate / Facility / Commercial Lead (e.g. Materials Recovery Facility, Depot, Plant, MM Group)
                # If auto-crawl is enabled, crawl the target website's contact pages directly
                if href and getattr(self, "auto_scrape_site_var", None) and self.auto_scrape_site_var.get():
                    try:
                        site_res = scrape_website_contacts(href, timeout=6)
                        if site_res.get("emails"):
                            emails.extend(site_res["emails"])
                        if site_res.get("phones"):
                            phones.extend(site_res["phones"])
                    except Exception:
                        pass

                delims = [r'\s+[|]\s+', r'\s+[-–—]\s+', r'\s+::\s+', r'\s+:\s+']
                title_parts = [clean_title]
                for d in delims:
                    if re.search(d, clean_title):
                        title_parts = [p.strip() for p in re.split(d, clean_title) if p.strip()]
                        break
                        
                dom_base = url_domain.split('.')[0].lower() if url_domain else ""
                company = ""
                headline = ""
                
                if len(title_parts) >= 2:
                    last_part = title_parts[-1]
                    first_part = title_parts[0]
                    
                    if dom_base and (dom_base in last_part.lower().replace(" ", "") or any(kw in last_part.lower() for kw in ["group", "ltd", "limited", "plc", "corp", "inc", "services", "recycling"])):
                        company = last_part
                        headline = " - ".join(title_parts[:-1])
                    elif dom_base and (dom_base in first_part.lower().replace(" ", "") or any(kw in first_part.lower() for kw in ["group", "ltd", "limited", "plc", "corp", "inc", "services", "recycling"])):
                        company = first_part
                        headline = " - ".join(title_parts[1:])
                    else:
                        company = first_part if len(first_part) < len(last_part) else last_part
                        headline = last_part if company == first_part else first_part
                else:
                    headline = title_parts[0]
                    company = dom_base.capitalize() if dom_base else title_parts[0]
                    
                if not company and url_domain:
                    company = dom_base.capitalize()
                    
                first_name = ""
                last_name = ""
                display_name = f"Site Contact ({company})" if company else "Site Contact / Commercial Enquiries"
                
                # Priority: If direct URL domain exists, that is the source domain!
                custom_dom = self.custom_email_domain_var.get() if hasattr(self, "custom_email_domain_var") else ""
                if custom_dom and custom_dom.strip():
                    resolved_dom = custom_dom.strip().lower().replace("@", "")
                elif url_domain:
                    resolved_dom = url_domain
                else:
                    industry = self.enrich_industry_var.get() if hasattr(self, "enrich_industry_var") else "fire"
                    resolved_dom = resolve_organization_domain(company, headline, snippet, industry)

            raw_email = ", ".join(list(dict.fromkeys(emails))) if emails else ""
            
            # Pre-synthesize email candidate if domain is resolved and no raw email was found
            if not raw_email and resolved_dom:
                pat = self.enrich_pattern_var.get() if hasattr(self, "enrich_pattern_var") else "{first}.{last}@{domain}"
                if first_name and last_name:
                    enriched_email = synthesize_email(first_name, last_name, resolved_dom, pat)
                else:
                    enriched_email = f"info@{resolved_dom.lower()}"
                deliv_status = "Pending Verification"
                deliv_badge = "⚪ Pending"
            else:
                enriched_email = raw_email.split(',')[0].strip() if raw_email else ""
                deliv_status = "Valid (Scraped from Site)" if raw_email else "Not Enriched"
                deliv_badge = "🟢 Scraped" if raw_email else "⚪ Not Found"
            
            normalized_leads.append({
                "First Name": first_name,
                "Last Name": last_name,
                "Name": display_name,
                "Headline / Role": headline,
                "Organisation": company,
                "Domain": resolved_dom,
                "Enriched Email": enriched_email,
                "Deliverability": deliv_status,
                "Deliverability Badge": deliv_badge,
                "MX Server": "Live Website Verified" if "Scraped" in deliv_status else "",
                "Email": raw_email,
                "Phone": ", ".join(list(dict.fromkeys(phones))) if phones else "",
                "URL": href,
                "Snippet": snippet
            })
            
        return normalized_leads

    def _show_search_progress(self, title_msg="Searching background engine...", detail_msg=""):
        if hasattr(self, "search_progress_lbl"):
            self.search_progress_lbl.configure(text=f"🔄 {title_msg}")
        if hasattr(self, "search_progress_detail_lbl"):
            self.search_progress_detail_lbl.configure(text=detail_msg)
        if hasattr(self, "search_progress_frame") and hasattr(self, "view_container"):
            try:
                self.search_progress_frame.pack(fill=tk.X, pady=(0, 4), before=self.view_container)
                self.search_progress_bar.start(12)
            except Exception:
                pass

    def _update_search_progress(self, title_msg, detail_msg=""):
        if hasattr(self, "search_progress_lbl"):
            self.search_progress_lbl.configure(text=f"🔄 {title_msg}")
        if hasattr(self, "search_progress_detail_lbl"):
            self.search_progress_detail_lbl.configure(text=detail_msg)

    def _hide_search_progress(self):
        if hasattr(self, "search_progress_bar"):
            try:
                self.search_progress_bar.stop()
            except Exception:
                pass
        if hasattr(self, "search_progress_frame"):
            try:
                self.search_progress_frame.pack_forget()
            except Exception:
                pass

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
        if hasattr(self, "top_search_btn"):
            self.top_search_btn.configure(state=tk.DISABLED)
        if hasattr(self, "top_stop_btn"):
            self.top_stop_btn.configure(state=tk.NORMAL)
        
        # Switch to results tab automatically
        self.notebook.select(self.tab_results)
        
        tor_msg = " [🧅 Tor Proxy SOCKS5 Enabled]" if use_tor else ""
        mode_desc = " [Mini Corner Window]" if browser_mode == "mini" else (" [Silent Background]" if browser_mode == "headless" else " [Normal Window]")
        self.results_text.delete("1.0", tk.END)
        self.results_text.insert(tk.END, f"Target Engine: {engine}{tor_msg}{mode_desc}\nQuery: {query}\n\nInitializing browser...\n")
        self.status_var.set(f"Starting {engine} extraction...")
        
        # Show animated visual progress banner
        self._show_search_progress(f"Searching {engine} (Page 1 of {pages})...", "Initializing engine & live contact crawler...")
        
        threading.Thread(target=self._scrape_worker, args=(engine, query, pages, delay, browser_mode, use_tor), daemon=True).start()

    def _interruptible_sleep(self, duration_sec):
        """Sleeps in 50ms steps so clicking Stop interrupts immediately."""
        steps = int(duration_sec / 0.05)
        for _ in range(max(1, steps)):
            if self.stop_requested:
                return
            time.sleep(0.05)

    def _safe_quit_driver(self, d):
        try:
            d.quit()
        except Exception:
            pass

    def _stop_search(self):
        if self.is_running or self.driver:
            self.stop_requested = True
            self.is_running = False
            self.status_var.set("⏹ Search stopped.")
            self._append_log("\n⏹ Search stopped by user.\n")
            self.search_btn.configure(state=tk.NORMAL)
            self.stop_btn.configure(state=tk.DISABLED)
            if hasattr(self, "top_search_btn"):
                self.top_search_btn.configure(state=tk.NORMAL)
            if hasattr(self, "top_stop_btn"):
                self.top_stop_btn.configure(state=tk.DISABLED)
            self._hide_search_progress()
            
            d = self.driver
            self.driver = None
            if d:
                threading.Thread(target=lambda: self._safe_quit_driver(d), daemon=True).start()

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
            self.after(0, self._update_search_progress, f"Searching {engine} (Page {page + 1} of {pages})...", f"Fetching SERP HTML and crawling site contacts...")
            
            try:
                self.driver.get(url)
            except Exception as e:
                if self.stop_requested:
                    break
                self.after(0, self._append_log, f"Navigation error on page {page + 1} ({e}).\n")
                break
                
            # Allow page to load & handle Cookie Consents
            self._interruptible_sleep(2.0)
            if self.stop_requested or not self.driver:
                break

            try:
                for btn_id in ["L2AGLb", "W0wltc", "bnp_btn_accept"]:
                    try:
                        b = self.driver.find_element(By.ID, btn_id)
                        if b.is_displayed():
                            b.click()
                            self._interruptible_sleep(1.0)
                            break
                    except Exception:
                        pass
                        
                for btn_text in ["Accept all", "I agree", "Tout accepter", "Alle akzeptieren", "Accept"]:
                    btns = self.driver.find_elements(By.XPATH, f"//button[contains(., '{btn_text}')]")
                    if btns and btns[0].is_displayed():
                        btns[0].click()
                        self._interruptible_sleep(1.0)
                        break
            except Exception:
                pass
                
            if self.stop_requested or not self.driver:
                break

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
                    self._interruptible_sleep(1.0)
                    try:
                        c_url = self.driver.current_url
                        c_src = self.driver.page_source
                        if "/sorry/" not in c_url and "captcha-form" not in c_src and "unusual traffic from your computer" not in c_src:
                            solved = True
                            self.after(0, self._append_log, "✅ CAPTCHA passed! Resuming extraction...\n\n")
                            if browser_mode in ["headless", "mini"]:
                                try:
                                    self.driver.minimize_window()
                                except Exception:
                                    pass
                            break
                    except Exception:
                        pass
                        
                if not solved and not self.stop_requested:
                    self.after(0, self._append_log, "⏳ CAPTCHA was not solved in time.\n💡 Tip: Try switching Search Engine to '🦁 Brave' or '🟦 Bing' or '🦆 DuckDuckGo' (which don't require CAPTCHAs).\n")
                    break
                    
                try:
                    page_src = self.driver.page_source if self.driver else ""
                except Exception:
                    pass
                
            if self.stop_requested:
                break

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
                self._interruptible_sleep(delay)
                
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
            self.after(0, self._update_search_progress, f"Requesting {engine} (Page {page + 1} of {pages})...", "Fetching HTML & extracting leads...")
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
        if hasattr(self, "top_search_btn"):
            self.top_search_btn.configure(state=tk.NORMAL)
        if hasattr(self, "top_stop_btn"):
            self.top_stop_btn.configure(state=tk.DISABLED)
        self._hide_search_progress()
        
        count = len(self.results_data)
        email_count = sum(1 for r in self.results_data if r.get("Email"))
        self._refresh_text_display()
        self.status_var.set(f"Completed! Found {count} lead(s) ({email_count} with email addresses).")
        self.stat_leads_var.set(f"{count} leads | {email_count} emails")
        
        if count == 0:
            messagebox.showinfo("Search Complete", f"No results were found on {self.engine_var.get()}.\n\nTip: Leave 'Show Chrome Window' checked to solve any CAPTCHA if prompted.")
        else:
            messagebox.showinfo("Search Complete", f"Extraction completed on {self.engine_var.get()}!\n\nFound: {count} leads\nExtracted Emails: {email_count}\n\nResults are ready in the table and text box for export.")

    def _get_filtered_data(self):
        """Returns results filtered by search text, organisation, status, and sorted by active column."""
        filt = self.filter_var.get().lower().strip()
        comp_filter = self.filter_company_var.get().strip() if hasattr(self, "filter_company_var") else ""
        stat_filter = self.filter_status_var.get().strip() if hasattr(self, "filter_status_var") else ""
        
        # Strip count from company filter e.g. "London Fire Brigade (12)" -> "London Fire Brigade"
        if comp_filter and comp_filter != "(All Organisations)":
            comp_match = re.sub(r'\s*\(\d+\)$', '', comp_filter).lower().strip()
        else:
            comp_match = ""
            
        filtered = []
        for r in self.results_data:
            # 1. Free text search filter
            if filt:
                match = (
                    filt in r.get("Name", "").lower() or
                    filt in r.get("First Name", "").lower() or
                    filt in r.get("Last Name", "").lower() or
                    filt in r.get("Headline / Role", "").lower() or
                    filt in r.get("Organisation", "").lower() or
                    filt in r.get("Domain", "").lower() or
                    filt in r.get("Enriched Email", "").lower() or
                    filt in r.get("Email", "").lower() or
                    filt in r.get("Deliverability", "").lower() or
                    filt in r.get("URL", "").lower() or
                    filt in r.get("Snippet", "").lower()
                )
                if not match:
                    continue
                    
            # 2. Company / Organisation filter
            if comp_match:
                r_org = r.get("Organisation", "").lower().strip()
                if comp_match not in r_org:
                    continue
                    
            # 3. Deliverability Status filter
            if stat_filter and stat_filter != "(All Statuses)":
                r_deliv = r.get("Deliverability", "")
                if "Valid" in stat_filter and "Valid" not in r_deliv:
                    continue
                elif "Risky" in stat_filter and "Risky" not in r_deliv:
                    continue
                elif "Not Found" in stat_filter and ("Valid" in r_deliv or "Risky" in r_deliv or "Invalid" in r_deliv or "No MX" in r_deliv):
                    continue
                elif "Invalid" in stat_filter and ("Invalid" not in r_deliv and "No MX" not in r_deliv):
                    continue
                    
            filtered.append(r)
            
        # 4. Interactive Column Header Sorting
        if hasattr(self, "sort_column") and self.sort_column:
            def sort_key(item):
                if self.sort_column == "#":
                    return self.results_data.index(item) if item in self.results_data else 0
                elif self.sort_column == "first_name":
                    return (item.get("First Name") or "").lower()
                elif self.sort_column == "last_name":
                    return (item.get("Last Name") or "").lower()
                elif self.sort_column == "role":
                    return (item.get("Headline / Role") or "").lower()
                elif self.sort_column == "org":
                    return (item.get("Organisation") or "").lower()
                elif self.sort_column == "email":
                    return (item.get("Enriched Email") or item.get("Email") or "").lower()
                elif self.sort_column == "phone":
                    return (item.get("Phone") or "").lower()
                elif self.sort_column == "status":
                    return (item.get("Deliverability") or "").lower()
                elif self.sort_column == "domain":
                    return (item.get("Domain") or "").lower()
                elif self.sort_column == "url":
                    return (item.get("URL") or "").lower()
                return ""
                
            filtered.sort(key=sort_key, reverse=self.sort_reverse)
            
        return filtered

    def _sort_by_column(self, col):
        """Sorts the results table by the clicked column header (ascending or descending)."""
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
            
        self._update_column_headers()
        self._refresh_text_display()
        
        order_str = "Descending (Z-A)" if self.sort_reverse else "Ascending (A-Z)"
        col_name = self.col_titles.get(col, col) if hasattr(self, "col_titles") else col
        self.status_var.set(f"Sorted table by '{col_name}' ({order_str})")

    def _update_column_headers(self):
        """Updates table headers with ▲ or ▼ sort direction arrows."""
        if not hasattr(self, "tree") or not hasattr(self, "col_titles"):
            return
        for c, title in self.col_titles.items():
            if c == self.sort_column:
                arrow = " ▼ (Z-A)" if self.sort_reverse else " ▲ (A-Z)"
                self.tree.heading(c, text=f"{title}{arrow}")
            else:
                self.tree.heading(c, text=title)

    def _update_company_filter_options(self):
        """Updates organisation combobox with unique companies and counts from results."""
        if not hasattr(self, "company_filter_combo"):
            return
            
        counts = {}
        for r in self.results_data:
            org = r.get("Organisation", "").strip()
            if org:
                counts[org] = counts.get(org, 0) + 1
                
        sorted_orgs = sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))
        options = ["(All Organisations)"] + [f"{org} ({cnt})" for org, cnt in sorted_orgs]
        self.company_filter_combo['values'] = options
        
        curr = self.filter_company_var.get()
        if not curr or curr not in options:
            match_found = False
            for opt in options:
                if curr and curr != "(All Organisations)" and opt.startswith(curr):
                    self.filter_company_var.set(opt)
                    match_found = True
                    break
            if not match_found:
                self.filter_company_var.set("(All Organisations)")

    def _reset_results_filters(self):
        """Resets search filter, company filter, status filter, and column sorting back to default."""
        self.filter_var.set("")
        self.filter_company_var.set("(All Organisations)")
        self.filter_status_var.set("(All Statuses)")
        self.sort_column = None
        self.sort_reverse = False
        self._update_column_headers()
        self._refresh_text_display()
        self.status_var.set("All result filters and sorting reset.")

    def _show_tree_context_menu(self, event):
        """Displays right-click context menu on table items."""
        item = self.tree.identify_row(event.y)
        if item:
            curr_selection = self.tree.selection()
            if item not in curr_selection:
                self.tree.selection_set(item)
            try:
                self.tree_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.tree_menu.grab_release()

    def _filter_by_selected_org(self):
        """Filters results by the organisation of the clicked table row."""
        selected = self.tree.selection()
        if not selected:
            return
        data = self._get_filtered_data()
        try:
            idx = int(selected[0])
            if 0 <= idx < len(data):
                org = data[idx].get("Organisation", "").strip()
                if org:
                    self.filter_company_var.set(org)
                    self._refresh_text_display()
                    self.status_var.set(f"Filtered results by organisation: '{org}'")
        except Exception:
            pass

    def _copy_selected_email(self):
        """Copies emails of selected table rows to clipboard."""
        selected = self.tree.selection()
        if not selected:
            return
        data = self._get_filtered_data()
        emails = []
        for item_id in selected:
            try:
                idx = int(item_id)
                if 0 <= idx < len(data):
                    e = data[idx].get("Enriched Email") or data[idx].get("Email")
                    if e:
                        emails.append(str(e).strip())
            except Exception:
                pass
        if emails:
            self.clipboard_clear()
            self.clipboard_append(", ".join(emails))
            self.status_var.set(f"Copied {len(emails)} email address(es) to clipboard.")
            messagebox.showinfo("Copied Email", f"Copied {len(emails)} email address(es) to clipboard:\n\n" + "\n".join(emails[:10]))
        else:
            messagebox.showinfo("No Email Found", "The selected contact(s) do not have an email address yet.\n\nTip: Click '⚡ Enrich Selected' or '🌐 Scrape Site Contacts' to discover their contact details.")

    def _copy_selected_phone(self):
        """Copies phone numbers of selected table rows to clipboard."""
        selected = self.tree.selection()
        if not selected:
            return
        data = self._get_filtered_data()
        phones = []
        for item_id in selected:
            try:
                idx = int(item_id)
                if 0 <= idx < len(data):
                    p = data[idx].get("Phone")
                    if p:
                        phones.append(str(p).strip())
            except Exception:
                pass
        if phones:
            self.clipboard_clear()
            self.clipboard_append(", ".join(phones))
            self.status_var.set(f"Copied {len(phones)} phone number(s) to clipboard.")
            messagebox.showinfo("Copied Phone", f"Copied {len(phones)} phone number(s) to clipboard:\n\n" + "\n".join(phones[:10]))
        else:
            messagebox.showinfo("No Phone Found", "The selected contact(s) do not have a phone number yet.\n\nTip: Click '🌐 Scrape Site Contacts' to extract phone numbers from the website.")

    def _copy_selected_row(self):
        """Copies full details of selected rows to clipboard."""
        selected = self.tree.selection()
        if not selected:
            return
        data = self._get_filtered_data()
        lines = []
        for item_id in selected:
            try:
                idx = int(item_id)
                if 0 <= idx < len(data):
                    r = data[idx]
                    email_val = r.get("Enriched Email") or r.get("Email", "-")
                    phone_val = r.get("Phone", "-")
                    lines.append(f"{r.get('First Name', '')} {r.get('Last Name', '')} | {r.get('Headline / Role', '')} | {r.get('Organisation', '')} | {email_val} | {phone_val} | {r.get('Deliverability', '')} | {r.get('URL', '')}")
            except Exception:
                pass
        if lines:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
            self.status_var.set(f"Copied {len(lines)} contact row(s) to clipboard.")
            messagebox.showinfo("Copied Details", f"Copied {len(lines)} row(s) to clipboard!")

    def _open_selected_url(self):
        """Opens profile or website URL of selected contact in default web browser."""
        selected = self.tree.selection()
        if not selected:
            return
        data = self._get_filtered_data()
        for item_id in selected:
            try:
                idx = int(item_id)
                if 0 <= idx < len(data):
                    url = data[idx].get("URL", "")
                    if url and (url.startswith("http://") or url.startswith("https://")):
                        webbrowser.open(url)
                        self.status_var.set(f"Opened URL in browser: {url[:50]}...")
                        break
            except Exception:
                pass

    def _start_batch_site_scrape(self):
        """Launches batch website contact extraction in a background worker thread."""
        if self.is_enriching:
            messagebox.showwarning("Busy", "Enrichment or site contact scraping is already in progress.")
            return
        if not self.results_data:
            messagebox.showwarning("No Leads", "No contacts in list. Run a search query first to extract leads.")
            return
            
        self.is_enriching = True
        self.batch_enrich_btn.configure(state=tk.DISABLED)
        if hasattr(self, "scrape_sites_btn"):
            self.scrape_sites_btn.configure(state=tk.DISABLED)
        self.single_enrich_btn.configure(state=tk.DISABLED)
        self.status_var.set("🌐 Starting Deep Website Contact Scraping (Emails & Phone Numbers)...")
        
        threading.Thread(target=self._batch_site_scrape_worker, daemon=True).start()

    def _batch_site_scrape_worker(self):
        total = len(self.results_data)
        found_emails_count = 0
        found_phones_count = 0
        
        for idx, lead in enumerate(self.results_data, 1):
            if not self.is_enriching:
                break
                
            url = lead.get("URL", "")
            org_name = lead.get("Organisation", "") or lead.get("Domain", "site")
            self.after(0, self.status_var.set, f"🌐 Scraping contacts from website {idx} of {total}: {org_name}...")
            
            if url and (url.startswith("http://") or url.startswith("https://")) and "linkedin.com" not in url:
                try:
                    site_res = scrape_website_contacts(url, timeout=8)
                    emails = site_res.get("emails", [])
                    phones = site_res.get("phones", [])
                    
                    if emails:
                        primary_em = emails[0]
                        lead["Email"] = ", ".join(emails)
                        lead["Enriched Email"] = primary_em
                        lead["Deliverability"] = "Valid (Scraped from Site)"
                        lead["Deliverability Badge"] = "🟢 Scraped"
                        found_emails_count += 1
                        
                    if phones:
                        lead["Phone"] = ", ".join(phones)
                        found_phones_count += 1
                except Exception:
                    pass
                    
            if idx % 2 == 0 or idx == total:
                self.after(0, self._refresh_text_display)
                
            time.sleep(0.05)
            
        self.is_enriching = False
        self.after(0, self.batch_enrich_btn.configure, {"state": tk.NORMAL})
        if hasattr(self, "scrape_sites_btn"):
            self.after(0, self.scrape_sites_btn.configure, {"state": tk.NORMAL})
        self.after(0, self.single_enrich_btn.configure, {"state": tk.NORMAL})
        self.after(0, self._refresh_text_display)
        self.after(0, self.status_var.set, f"✅ Website contact scraping complete! Found {found_emails_count} site emails, {found_phones_count} phone numbers.")
        
        self.after(0, messagebox.showinfo, "✅ Site Contact Scraping Complete",
            f"🌐 Live Website Contact Extraction Complete!\n\n"
            f"Total Sites Crawled: {total}\n"
            f"✉️ Contact Emails Found: {found_emails_count}\n"
            f"📞 Phone Numbers Found: {found_phones_count}\n\n"
            f"Your contacts are updated in the table with direct site contact details.\n"
            f"Click '💾 Export Enriched CSV' to export."
        )

    def _scrape_selected_site_contacts(self):
        """Scrapes live website contacts for selected rows in the table."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select Row", "Please select one or more contacts in the table to scrape their website contacts.")
            return
            
        data = self._get_filtered_data()
        selected_leads = []
        for item_id in selected:
            try:
                idx = int(item_id)
                if 0 <= idx < len(data):
                    selected_leads.append(data[idx])
            except (ValueError, IndexError):
                pass
                
        if not selected_leads:
            return
            
        if self.is_enriching:
            messagebox.showwarning("Busy", "Scraping or enrichment is already in progress.")
            return
            
        self.is_enriching = True
        self.batch_enrich_btn.configure(state=tk.DISABLED)
        if hasattr(self, "scrape_sites_btn"):
            self.scrape_sites_btn.configure(state=tk.DISABLED)
        self.single_enrich_btn.configure(state=tk.DISABLED)
        
        def _worker():
            total = len(selected_leads)
            found_e = 0
            found_p = 0
            for idx, lead in enumerate(selected_leads, 1):
                if not self.is_enriching:
                    break
                url = lead.get("URL", "")
                self.after(0, self.status_var.set, f"🌐 Scraping contacts from {lead.get('Organisation', 'site')} ({idx}/{total})...")
                if url and (url.startswith("http://") or url.startswith("https://")) and "linkedin.com" not in url:
                    try:
                        site_res = scrape_website_contacts(url, timeout=8)
                        emails = site_res.get("emails", [])
                        phones = site_res.get("phones", [])
                        if emails:
                            lead["Email"] = ", ".join(emails)
                            lead["Enriched Email"] = emails[0]
                            lead["Deliverability"] = "Valid (Scraped from Site)"
                            lead["Deliverability Badge"] = "🟢 Scraped"
                            found_e += 1
                        if phones:
                            lead["Phone"] = ", ".join(phones)
                            found_p += 1
                    except Exception:
                        pass
                time.sleep(0.04)
                self.after(0, self._refresh_text_display)
                
            self.is_enriching = False
            self.after(0, self.batch_enrich_btn.configure, {"state": tk.NORMAL})
            if hasattr(self, "scrape_sites_btn"):
                self.after(0, self.scrape_sites_btn.configure, {"state": tk.NORMAL})
            self.after(0, self.single_enrich_btn.configure, {"state": tk.NORMAL})
            self.after(0, self._refresh_text_display)
            self.after(0, self.status_var.set, f"✅ Scraped {total} site(s): {found_e} emails, {found_p} phone numbers.")
            self.after(0, messagebox.showinfo, "✅ Site Scraping Complete",
                f"Finished scraping {total} selected website(s)!\n\n"
                f"✉️ Emails Discovered: {found_e}\n"
                f"📞 Phone Numbers Discovered: {found_p}"
            )
            
        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_text_display(self):
        fmt = self.format_var.get()
        data = self._get_filtered_data()
        count = len(data)
        total = len(self.results_data)
        
        # Update organisation filter combobox options
        self._update_company_filter_options()
        
        # Count verified emails or enriched emails
        email_count = sum(1 for r in self.results_data if (r.get("Enriched Email") or r.get("Email")))
        valid_mx_count = sum(1 for r in self.results_data if "Valid" in r.get("Deliverability", ""))
        
        if valid_mx_count > 0:
            self.count_badge.configure(text=f"{count} / {total} leads ({valid_mx_count} MX verified)")
            self.stat_leads_var.set(f"{total} leads | {valid_mx_count} MX verified | {email_count} emails")
        else:
            self.count_badge.configure(text=f"{count} / {total} leads ({email_count} emails)")
            self.stat_leads_var.set(f"{total} leads | {email_count} emails")
            
        # 1. Update Table View (Treeview)
        if hasattr(self, "tree"):
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
                
            for idx, r in enumerate(data, 1):
                deliv = r.get("Deliverability", "Not Enriched")
                badge = r.get("Deliverability Badge", "⚪ Not Found")
                
                # Tag determination
                if "Valid" in deliv:
                    tag = "valid"
                elif "Risky" in deliv:
                    tag = "risky"
                elif "Invalid" in deliv or "No MX" in deliv:
                    tag = "invalid"
                else:
                    tag = "not_found"
                    
                display_email = r.get("Enriched Email") or r.get("Email") or "-"
                display_phone = r.get("Phone") or "-"
                display_domain = r.get("Domain") or "-"
                
                self.tree.insert(
                    "",
                    tk.END,
                    iid=str(idx - 1),
                    values=(
                        idx,
                        r.get("First Name", "-"),
                        r.get("Last Name", "-"),
                        r.get("Headline / Role", "-"),
                        r.get("Organisation", "-"),
                        display_email,
                        display_phone,
                        badge,
                        display_domain,
                        r.get("URL", "-")
                    ),
                    tags=(tag,)
                )

        # 2. Update Text Box View
        self.results_text.delete("1.0", tk.END)
        
        if not data:
            if self.is_running:
                self.results_text.insert(tk.END, f"Searching {self.engine_var.get()}... please wait.\n")
            else:
                self.results_text.insert(tk.END, f"No results match your criteria.\nConfigure search criteria in Tab 1 and click 'Search & Extract Leads'.\n")
        else:
            if fmt == "formatted":
                lines = []
                for idx, item in enumerate(data, 1):
                    lines.append(f"[{idx}] {item.get('Name', '')}")
                    if item.get('First Name') or item.get('Last Name'):
                        lines.append(f"    Name:    {item.get('First Name', '')} {item.get('Last Name', '')}")
                    if item.get('Headline / Role'):
                        lines.append(f"    Role:    {item.get('Headline / Role', '')}")
                    if item.get('Organisation'):
                        lines.append(f"    Org:     {item.get('Organisation', '')}")
                    if item.get('Domain'):
                        lines.append(f"    Domain:  {item.get('Domain', '')}")
                    if item.get('Enriched Email'):
                        lines.append(f"    ✉ Email: {item.get('Enriched Email', '')} [{item.get('Deliverability', '')}]")
                    elif item.get('Email'):
                        lines.append(f"    ✉ Email: {item.get('Email', '')}")
                    if item.get('MX Server'):
                        lines.append(f"    🛡 MX:    {item.get('MX Server', '')}")
                    if item.get('Phone'):
                        lines.append(f"    📞 Phone: {item.get('Phone', '')}")
                    lines.append(f"    🔗 URL:   {item.get('URL', '')}")
                    if item.get('Snippet'):
                        lines.append(f"    📝 Snip:  {item.get('Snippet', '')}")
                    lines.append("-" * 75)
                self.results_text.insert(tk.END, "\n".join(lines))
                
            elif fmt == "tsv":
                headers = ["First Name", "Last Name", "Job Title", "Organisation", "Enriched Email", "Deliverability", "Domain", "MX Server", "Phone", "URL", "Snippet"]
                lines = ["\t".join(headers)]
                for item in data:
                    row = [
                        item.get("First Name", "").replace("\t", " "),
                        item.get("Last Name", "").replace("\t", " "),
                        item.get("Headline / Role", "").replace("\t", " "),
                        item.get("Organisation", "").replace("\t", " "),
                        (item.get("Enriched Email") or item.get("Email", "")).replace("\t", " "),
                        item.get("Deliverability", "").replace("\t", " "),
                        item.get("Domain", "").replace("\t", " "),
                        item.get("MX Server", "").replace("\t", " "),
                        item.get("Phone", "").replace("\t", " "),
                        item.get("URL", "").replace("\t", " "),
                        item.get("Snippet", "").replace("\t", " ").replace("\n", " ")
                    ]
                    lines.append("\t".join(row))
                self.results_text.insert(tk.END, "\n".join(lines))
                
            elif fmt == "csv":
                output = io.StringIO()
                fieldnames = ["First Name", "Last Name", "Job Title", "Organisation", "Enriched Email", "Deliverability", "Domain", "MX Server", "Phone", "URL", "Snippet"]
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                for item in data:
                    writer.writerow({
                        "First Name": item.get("First Name", ""),
                        "Last Name": item.get("Last Name", ""),
                        "Job Title": item.get("Headline / Role", ""),
                        "Organisation": item.get("Organisation", ""),
                        "Enriched Email": item.get("Enriched Email") or item.get("Email", ""),
                        "Deliverability": item.get("Deliverability", ""),
                        "Domain": item.get("Domain", ""),
                        "MX Server": item.get("MX Server", ""),
                        "Phone": item.get("Phone", ""),
                        "URL": item.get("URL", ""),
                        "Snippet": item.get("Snippet", "")
                    })
                self.results_text.insert(tk.END, output.getvalue())
                
            elif fmt == "emails":
                all_emails = []
                for item in data:
                    e = item.get("Enriched Email") or item.get("Email")
                    if e:
                        for em in str(e).split(","):
                            clean_em = em.strip()
                            if clean_em and clean_em not in all_emails:
                                all_emails.append(clean_em)
                if all_emails:
                    self.results_text.insert(tk.END, "\n".join(all_emails))
                else:
                    self.results_text.insert(tk.END, "No email addresses found.\nClick '⚡ Batch Enrich All' to discover and verify emails.")
                    
            elif fmt == "urls":
                urls = [item.get("URL", "") for item in data if item.get("URL")]
                self.results_text.insert(tk.END, "\n".join(urls))

        # 3. View Switch (Table vs Text Box)
        if hasattr(self, "tree_frame") and hasattr(self, "text_container"):
            if fmt == "table":
                self.text_container.pack_forget()
                self.tree_frame.pack(fill=tk.BOTH, expand=True)
            else:
                self.tree_frame.pack_forget()
                self.text_container.pack(fill=tk.BOTH, expand=True)

    def _on_tree_double_click(self, event):
        """Enriches or inspects the double-clicked lead in table view."""
        selected_item = self.tree.selection()
        if not selected_item:
            return
        data = self._get_filtered_data()
        try:
            idx = int(selected_item[0])
            if 0 <= idx < len(data):
                lead = data[idx]
                self._enrich_single_lead_item(lead)
        except Exception:
            pass

    def _on_tree_select(self, event):
        pass

    def _get_leads_tree_row_tooltip(self, item):
        """Generates an adaptive hover preview card for rows in the Leads table."""
        try:
            idx = int(item)
            data = self._get_filtered_data()
            if 0 <= idx < len(data):
                r = data[idx]
                lines = [
                    f"👤 {r.get('Name', '-')}",
                    f"💼 Role: {r.get('Headline / Role', '-')}",
                    f"🏢 Company: {r.get('Organisation', '-')}",
                    f"✉️ Email: {r.get('Enriched Email') or r.get('Email', '-')}",
                    f"📞 Phone: {r.get('Phone', 'No phone listed')}",
                    f"🛡️ Status: {r.get('Deliverability', 'Not Checked')}  |  🌐 Domain: {r.get('Domain', '-')}"
                ]
                if r.get('URL'):
                    lines.append(f"🔗 URL: {r.get('URL')}")
                if r.get('Snippet'):
                    lines.append(f"📝 Snippet: {r.get('Snippet')}")
                return "\n".join(lines)
        except Exception:
            pass
        return ""

    def _get_verifier_tree_row_tooltip(self, item):
        """Generates an adaptive hover preview card for rows in the Verifier table."""
        try:
            idx = int(item)
            data = self._get_filtered_verifier_data()
            if 0 <= idx < len(data):
                r = data[idx]
                lines = [
                    f"✉️ Target Email: {r.get('email', '')}",
                    f"👤 Info / Name: {r.get('info', '')}",
                    f"🌐 Domain: {r.get('domain', '')}  |  🛡️ Status: {r.get('status', '')}",
                    f"🖥️ MX Server: {r.get('mx_host', 'None')} (SMTP Code: {r.get('smtp_code', '-')}, Latency: {r.get('response_time_ms', 0)}ms)"
                ]
                if r.get('details'):
                    lines.append(f"📝 Handshake Log: {r.get('details')}")
                return "\n".join(lines)
        except Exception:
            pass
        return ""

    def _get_opendata_tree_row_tooltip(self, item):
        """Generates an adaptive hover preview card for rows in the Public Registry table."""
        try:
            vals = self.opendata_tree.item(item, "values")
            if vals and self.opendata_headers:
                lines = []
                for h, v in zip(self.opendata_headers, vals):
                    if str(v).strip():
                        lines.append(f"• {h}: {v}")
                return "\n".join(lines[:14])
        except Exception:
            pass
        return ""


    def _enrich_selected_lead(self):
        """Enriches all currently selected contacts in the Treeview table (single or multi-select)."""
        if not hasattr(self, "tree"):
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select Contact(s)", "Please click on one or more contacts in the table.\n\n💡 Tip: You can hold Ctrl or Shift to select multiple rows, then click '⚡ Enrich Selected'.")
            return
            
        data = self._get_filtered_data()
        selected_leads = []
        for item_id in selected:
            try:
                idx = int(item_id)
                if 0 <= idx < len(data):
                    selected_leads.append(data[idx])
            except (ValueError, IndexError):
                pass
                
        if not selected_leads:
            return
            
        if len(selected_leads) == 1:
            self._enrich_single_lead_item(selected_leads[0])
        else:
            self._start_subset_enrich(selected_leads)

    def _start_subset_enrich(self, leads_subset):
        """Launches enrichment for a selected group of leads."""
        if self.is_enriching:
            messagebox.showwarning("Busy", "Enrichment is already in progress.")
            return
            
        self.is_enriching = True
        self.batch_enrich_btn.configure(state=tk.DISABLED)
        self.single_enrich_btn.configure(state=tk.DISABLED)
        self.status_var.set(f"⚡ Starting Email Enrichment for {len(leads_subset)} selected contacts...")
        
        threading.Thread(target=self._subset_enrich_worker, args=(leads_subset,), daemon=True).start()

    def _subset_enrich_worker(self, leads_subset):
        provider = self.enrich_provider_var.get()
        api_key = self.enrich_api_key_var.get().strip()
        pattern = self.enrich_pattern_var.get()
        industry = self.enrich_industry_var.get()
        custom_dom = self.enrich_custom_domain_var.get().strip()
        
        total = len(leads_subset)
        valid_count = 0
        risky_count = 0
        not_found_count = 0
        
        for idx, lead in enumerate(leads_subset, 1):
            if not self.is_enriching:
                break
                
            self.after(0, self.status_var.set, f"⚡ Enriching selected lead {idx} of {total} ({int((idx/total)*100)}%)...")
            
            res = api_enrich_lead(lead, provider=provider, api_key=api_key, pattern=pattern, industry=industry, custom_domain=custom_dom)
            
            lead["First Name"] = res["First Name"]
            lead["Last Name"] = res["Last Name"]
            lead["Domain"] = res["Domain"]
            lead["Enriched Email"] = res["Enriched Email"]
            lead["Deliverability"] = res["Deliverability"]
            lead["Deliverability Badge"] = res["Deliverability Badge"]
            lead["MX Server"] = res["MX Server"]
            
            if "Valid" in res["Deliverability"]:
                valid_count += 1
            elif "Risky" in res["Deliverability"]:
                risky_count += 1
            else:
                not_found_count += 1
                
            if idx % 2 == 0 or idx == total:
                self.after(0, self._refresh_text_display)
                
            time.sleep(0.04)
            
        self.is_enriching = False
        self.after(0, self.batch_enrich_btn.configure, {"state": tk.NORMAL})
        self.after(0, self.single_enrich_btn.configure, {"state": tk.NORMAL})
        self.after(0, self._refresh_text_display)
        self.after(0, self.status_var.set, f"✅ Enriched {total} selected leads! ({valid_count} MX verified)")
        
        self.after(0, messagebox.showinfo, "✅ Selected Leads Enriched",
            f"✅ Finished Enriching {total} Selected Contacts!\n\n"
            f"🟢 Valid (MX Verified): {valid_count}\n"
            f"🟡 Risky / Unverified: {risky_count}\n"
            f"⚪ Not Found: {not_found_count}\n\n"
            f"Results have been updated in the table."
        )

    def _enrich_single_lead_item(self, lead: dict):
        """Enriches a single lead dictionary and refreshes UI."""
        provider = self.enrich_provider_var.get()
        api_key = self.enrich_api_key_var.get().strip()
        pattern = self.enrich_pattern_var.get()
        industry = self.enrich_industry_var.get()
        custom_dom = self.enrich_custom_domain_var.get().strip()
        
        self.status_var.set(f"Enriching contact: {lead.get('Name', '')}...")
        res = api_enrich_lead(lead, provider=provider, api_key=api_key, pattern=pattern, industry=industry, custom_domain=custom_dom)
        
        lead["First Name"] = res["First Name"]
        lead["Last Name"] = res["Last Name"]
        lead["Domain"] = res["Domain"]
        lead["Enriched Email"] = res["Enriched Email"]
        lead["Deliverability"] = res["Deliverability"]
        lead["Deliverability Badge"] = res["Deliverability Badge"]
        lead["MX Server"] = res["MX Server"]
        
        self._refresh_text_display()
        self.status_var.set(f"✅ Enriched {lead.get('Name', '')}: {lead.get('Enriched Email', 'Not Found')} ({res['Deliverability']})")
        messagebox.showinfo(
            "Contact Enriched",
            f"👤 Name: {res['First Name']} {res['Last Name']}\n"
            f"🏢 Organisation: {lead.get('Organisation', '')}\n"
            f"🌐 Domain: {res['Domain'] or 'Not Found'}\n"
            f"✉️ Email: {res['Enriched Email'] or 'None'}\n"
            f"🛡️ Deliverability: {res['Deliverability']}\n"
            f"📡 MX Host: {res['MX Server']}"
        )

    def _start_batch_enrich(self):
        """Launches batch lead enrichment in a background worker thread."""
        if self.is_enriching:
            messagebox.showwarning("Busy", "Enrichment is already in progress.")
            return
        if not self.results_data:
            messagebox.showwarning("No Leads", "No contacts in list. Run a search query first to extract leads.")
            return
            
        self.is_enriching = True
        self.batch_enrich_btn.configure(state=tk.DISABLED)
        self.single_enrich_btn.configure(state=tk.DISABLED)
        self.status_var.set("⚡ Starting Batch Email Enrichment & Deliverability Verification...")
        
        threading.Thread(target=self._batch_enrich_worker, daemon=True).start()

    def _batch_enrich_worker(self):
        provider = self.enrich_provider_var.get()
        api_key = self.enrich_api_key_var.get().strip()
        pattern = self.enrich_pattern_var.get()
        industry = self.enrich_industry_var.get()
        custom_dom = self.enrich_custom_domain_var.get().strip()
        
        total = len(self.results_data)
        valid_count = 0
        risky_count = 0
        not_found_count = 0
        
        for idx, lead in enumerate(self.results_data, 1):
            if not self.is_enriching:
                break
                
            self.after(0, self.status_var.set, f"⚡ Enriching lead {idx} of {total} ({int((idx/total)*100)}%)...")
            
            res = api_enrich_lead(lead, provider=provider, api_key=api_key, pattern=pattern, industry=industry, custom_domain=custom_dom)
            
            lead["First Name"] = res["First Name"]
            lead["Last Name"] = res["Last Name"]
            lead["Domain"] = res["Domain"]
            lead["Enriched Email"] = res["Enriched Email"]
            lead["Deliverability"] = res["Deliverability"]
            lead["Deliverability Badge"] = res["Deliverability Badge"]
            lead["MX Server"] = res["MX Server"]
            
            if "Valid" in res["Deliverability"]:
                valid_count += 1
            elif "Risky" in res["Deliverability"]:
                risky_count += 1
            else:
                not_found_count += 1
                
            # Periodically update table every 3 leads
            if idx % 3 == 0 or idx == total:
                self.after(0, self._refresh_text_display)
                
            time.sleep(0.05)
            
        self.is_enriching = False
        self.after(0, self.batch_enrich_btn.configure, {"state": tk.NORMAL})
        self.after(0, self.single_enrich_btn.configure, {"state": tk.NORMAL})
        self.after(0, self._refresh_text_display)
        self.after(0, self.status_var.set, f"✅ Batch enrichment complete! {valid_count} MX verified emails found.")
        
        self.after(0, messagebox.showinfo, "✅ Enrichment Complete",
            f"✅ Lead Email Enrichment Complete!\n\n"
            f"Total Leads Processed: {total}\n"
            f"🟢 Valid (MX Verified): {valid_count}\n"
            f"🟡 Risky / Unverified: {risky_count}\n"
            f"⚪ Not Found / Missing Domain: {not_found_count}\n\n"
            f"Your contacts are updated in the table with official domains and deliverability badges.\n"
            f"Click '💾 Export Enriched CSV' to export."
        )

    def _save_to_enriched_csv(self):
        """Exports enriched leads with First Name, Surname, Job Role, Organisation, Enriched Email, Domain, MX Status."""
        if not self.results_data:
            messagebox.showwarning("Export", "No leads to export. Run a search or apply template first.")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files (*.csv)", "*.csv"), ("All Files (*.*)", "*.*")],
            initialfile="enriched_leads.csv"
        )
        if not filepath:
            return
            
        try:
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                fieldnames = [
                    "First Name",
                    "Last Name",
                    "Full Name",
                    "Job Title / Role",
                    "Organisation",
                    "Resolved Domain",
                    "Enriched Email",
                    "Deliverability Status",
                    "MX Server Host",
                    "Phone",
                    "LinkedIn Profile URL",
                    "Search Snippet Context"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for item in self.results_data:
                    email_val = item.get("Enriched Email") or item.get("Email", "")
                    writer.writerow({
                        "First Name": item.get("First Name", ""),
                        "Last Name": item.get("Last Name", ""),
                        "Full Name": item.get("Name", ""),
                        "Job Title / Role": item.get("Headline / Role", ""),
                        "Organisation": item.get("Organisation", ""),
                        "Resolved Domain": item.get("Domain", ""),
                        "Enriched Email": email_val,
                        "Deliverability Status": item.get("Deliverability", "Not Enriched"),
                        "MX Server Host": item.get("MX Server", ""),
                        "Phone": item.get("Phone", ""),
                        "LinkedIn Profile URL": item.get("URL", ""),
                        "Search Snippet Context": item.get("Snippet", "")
                    })
                    
            self.status_var.set(f"✅ Exported {len(self.results_data)} enriched leads to {os.path.basename(filepath)}")
            messagebox.showinfo("Export Successful", f"Successfully exported {len(self.results_data)} enriched leads to:\n\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save file:\n{e}")

    def _open_enrichment_settings(self):
        """Opens interactive configuration dialog for Domain Resolution, Patterns, and External APIs."""
        dlg = tk.Toplevel(self)
        dlg.title("⚙️ Email Enrichment & Domain Settings")
        dlg.geometry("620x530")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(bg="#F1F5F9")
        
        main_f = ttk.Frame(dlg, padding="15")
        main_f.pack(fill=tk.BOTH, expand=True)
        
        # Title
        t_lbl = ttk.Label(main_f, text="⚙️ Email Enrichment & Domain Settings", font=("Segoe UI", 12, "bold"), foreground="#0F172A")
        t_lbl.pack(anchor=tk.W, pady=(0, 3))
        s_lbl = ttk.Label(main_f, text="Configure industry domain mapping, naming formulas, and discovery APIs.", foreground="#64748B", font=("Segoe UI", 9))
        s_lbl.pack(anchor=tk.W, pady=(0, 10))
        
        # 1. Industry Domain Mapping Registry
        f1 = ttk.LabelFrame(main_f, text=" 🏢 Target Industry Domain Registry ", padding="10")
        f1.pack(fill=tk.X, pady=(0, 8))
        
        lbl_ind = ttk.Label(f1, text="Industry Domain Map:", font=("Segoe UI", 9, "bold"))
        lbl_ind.grid(row=0, column=0, sticky=tk.W, pady=3)
        
        ind_combo = ttk.Combobox(f1, state="readonly", width=42)
        ind_combo['values'] = (
            "🌐 Auto-Detect Website Domain (Commercial Sites & Facilities)",
            "♻️ UK Waste & Environment Agencies (EA / SEPA / NRW)",
            "🚒 UK Fire & Rescue Services (50+ official .gov.uk domains)",
            "🏥 NHS Trusts & Health Boards (.nhs.uk domains)",
            "🏛️ UK Local Councils & Authorities (.gov.uk)",
            "👮 UK Police Constabularies (.police.uk)",
            "🏢 Custom Domain (Specified below)"
        )
        
        curr_ind = self.enrich_industry_var.get()
        if curr_ind == "auto":
            ind_combo.current(0)
        elif curr_ind in ["waste", "environment", "recycling"]:
            ind_combo.current(1)
        elif curr_ind == "fire":
            ind_combo.current(2)
        elif curr_ind == "nhs":
            ind_combo.current(3)
        elif curr_ind == "council":
            ind_combo.current(4)
        elif curr_ind == "police":
            ind_combo.current(5)
        elif curr_ind == "custom":
            ind_combo.current(6)
        else:
            ind_combo.current(0)
            
        ind_combo.grid(row=0, column=1, padx=6, pady=3)
        
        lbl_cdom = ttk.Label(f1, text="Custom Domain Fallback:")
        lbl_cdom.grid(row=1, column=0, sticky=tk.W, pady=3)
        
        cdom_var = tk.StringVar(value=self.enrich_custom_domain_var.get())
        cdom_entry = ttk.Entry(f1, textvariable=cdom_var, width=32)
        cdom_entry.grid(row=1, column=1, sticky=tk.W, padx=6, pady=3)
        ToolTip(cdom_entry, "Fallback domain to use if organization is not recognized in registry (e.g. london-fire.gov.uk).")
        
        # 2. Email Formula Pattern
        f2 = ttk.LabelFrame(main_f, text=" 📧 Corporate Email Pattern Formula ", padding="10")
        f2.pack(fill=tk.X, pady=(0, 8))
        
        lbl_pat = ttk.Label(f2, text="Naming Formula:", font=("Segoe UI", 9, "bold"))
        lbl_pat.grid(row=0, column=0, sticky=tk.W, pady=3)
        
        pat_combo = ttk.Combobox(f2, state="readonly", width=42)
        pat_combo['values'] = (
            "{first}.{last}@{domain} (e.g. john.smith@domain.com - Standard)",
            "{f}{last}@{domain} (e.g. jsmith@domain.com)",
            "{first}{last}@{domain} (e.g. johnsmith@domain.com)",
            "{first}_{last}@{domain} (e.g. john_smith@domain.com)",
            "{last}.{first}@{domain} (e.g. smith.john@domain.com)"
        )
        
        curr_pat = self.enrich_pattern_var.get()
        if "{f}{last}" in curr_pat:
            pat_combo.current(1)
        elif "{first}{last}" in curr_pat:
            pat_combo.current(2)
        elif "{first}_{last}" in curr_pat:
            pat_combo.current(3)
        elif "{last}.{first}" in curr_pat:
            pat_combo.current(4)
        else:
            pat_combo.current(0)
            
        pat_combo.grid(row=0, column=1, padx=6, pady=3)
        
        # 3. Provider & API Key
        f3 = ttk.LabelFrame(main_f, text=" 🔌 Discovery & Verification Engine ", padding="10")
        f3.pack(fill=tk.X, pady=(0, 8))
        
        lbl_prov = ttk.Label(f3, text="Enrichment Provider:", font=("Segoe UI", 9, "bold"))
        lbl_prov.grid(row=0, column=0, sticky=tk.W, pady=3)
        
        prov_combo = ttk.Combobox(f3, state="readonly", width=42)
        prov_combo['values'] = (
            "⚡ Built-in MX & DNS Verifier (Free, Instant, Local, DNS MX Check)",
            "🎯 Hunter.io Email Finder API",
            "🚀 Apollo.io Match API",
            "❄️ Snov.io Email Discovery API"
        )
        
        curr_prov = self.enrich_provider_var.get()
        if curr_prov == "hunter":
            prov_combo.current(1)
        elif curr_prov == "apollo":
            prov_combo.current(2)
        elif curr_prov == "snov":
            prov_combo.current(3)
        else:
            prov_combo.current(0)
            
        prov_combo.grid(row=0, column=1, padx=6, pady=3)
        
        lbl_key = ttk.Label(f3, text="API Key (If using external):")
        lbl_key.grid(row=1, column=0, sticky=tk.W, pady=3)
        
        key_var = tk.StringVar(value=self.enrich_api_key_var.get())
        key_entry = ttk.Entry(f3, textvariable=key_var, show="*", width=32)
        key_entry.grid(row=1, column=1, sticky=tk.W, padx=6, pady=3)
        ToolTip(key_entry, "Enter your Hunter.io, Apollo.io, or Snov.io API key (not required for Built-in MX engine).")
        
        # 4. REST API Endpoint Status
        f4 = ttk.LabelFrame(main_f, text=" 🌐 Embedded REST API Server ", padding="8")
        f4.pack(fill=tk.X, pady=(0, 10))
        
        api_info = ttk.Label(f4, text=f"• Local REST Server: 🟢 Active on http://127.0.0.1:{LOCAL_ENRICHMENT_PORT}/api/enrich\n• Health Check: http://127.0.0.1:{LOCAL_ENRICHMENT_PORT}/api/health", font=("Consolas", 8), foreground="#334155")
        api_info.pack(anchor=tk.W)
        
        # Action Buttons
        btn_bar = ttk.Frame(main_f)
        btn_bar.pack(fill=tk.X)
        
        def _save_settings():
            # Save industry
            raw_ind = ind_combo.get()
            if "Auto-Detect" in raw_ind:
                self.enrich_industry_var.set("auto")
            elif "Waste" in raw_ind or "Environment" in raw_ind:
                self.enrich_industry_var.set("waste")
            elif "NHS" in raw_ind:
                self.enrich_industry_var.set("nhs")
            elif "Council" in raw_ind:
                self.enrich_industry_var.set("council")
            elif "Police" in raw_ind:
                self.enrich_industry_var.set("police")
            elif "Custom" in raw_ind:
                self.enrich_industry_var.set("custom")
            else:
                self.enrich_industry_var.set("fire")
                
            # Save custom domain
            self.enrich_custom_domain_var.set(cdom_var.get().strip())
            
            # Save pattern formula
            raw_pat = pat_combo.get()
            if "{f}{last}" in raw_pat:
                self.enrich_pattern_var.set("{f}{last}@{domain}")
            elif "{first}{last}" in raw_pat:
                self.enrich_pattern_var.set("{first}{last}@{domain}")
            elif "{first}_{last}" in raw_pat:
                self.enrich_pattern_var.set("{first}_{last}@{domain}")
            elif "{last}.{first}" in raw_pat:
                self.enrich_pattern_var.set("{last}.{first}@{domain}")
            else:
                self.enrich_pattern_var.set("{first}.{last}@{domain}")
                
            # Save provider & key
            raw_prov = prov_combo.get()
            if "Hunter" in raw_prov:
                self.enrich_provider_var.set("hunter")
            elif "Apollo" in raw_prov:
                self.enrich_provider_var.set("apollo")
            elif "Snov" in raw_prov:
                self.enrich_provider_var.set("snov")
            else:
                self.enrich_provider_var.set("builtin")
                
            self.enrich_api_key_var.set(key_var.get().strip())
            
            dlg.destroy()
            self.status_var.set("✅ Email Enrichment settings saved.")
            messagebox.showinfo("Settings Saved", "✅ Email Enrichment settings successfully saved!")
            
        save_btn = ttk.Button(btn_bar, text="💾 Save Settings", style="Primary.TButton", command=_save_settings)
        save_btn.pack(side=tk.RIGHT, padx=4)
        
        cancel_btn = ttk.Button(btn_bar, text="Cancel", style="Secondary.TButton", command=dlg.destroy)
        cancel_btn.pack(side=tk.RIGHT)

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
            e = item.get("Enriched Email") or item.get("Email")
            if e:
                for em in str(e).split(","):
                    clean_em = em.strip()
                    if clean_em and clean_em not in all_emails:
                        all_emails.append(clean_em)
        if not all_emails:
            messagebox.showinfo("Emails", "No email addresses have been extracted or enriched yet.\n\nTip: Click '⚡ Batch Enrich Leads' to discover and verify email addresses.")
            return
        text = "\n".join(all_emails)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set(f"✅ Copied {len(all_emails)} email(s) to clipboard!")
        messagebox.showinfo("Copied!", f"Copied {len(all_emails)} extracted & enriched email addresses to clipboard!")

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
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                fieldnames = ["Name", "Headline / Role", "Organisation", "Email", "Phone", "URL", "Snippet Context"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for item in self.results_data:
                    writer.writerow({
                        "Name": item.get("Name", ""),
                        "Headline / Role": item.get("Headline / Role", ""),
                        "Organisation": item.get("Organisation", ""),
                        "Email": item.get("Enriched Email") or item.get("Email", ""),
                        "Phone": item.get("Phone", ""),
                        "URL": item.get("URL", ""),
                        "Snippet Context": item.get("Snippet", "")
                    })
            self.status_var.set(f"Saved to {os.path.basename(filepath)}")
            messagebox.showinfo("Saved", f"Successfully exported {len(self.results_data)} leads to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")

    def _clear_results(self):
        if self.is_running or self.is_enriching:
            messagebox.showwarning("Busy", "Cannot clear while extraction or enrichment is active.")
            return
        self.results_data.clear()
        self._refresh_text_display()
        self.count_badge.configure(text="0 leads")
        self.stat_leads_var.set("0 leads | 0 emails")
        self.status_var.set("Results cleared.")

    def _on_closing(self):
        self._stop_search()
        self.destroy()


if __name__ == "__main__":
    app = GoogleLeadScraperSuite()
    app.mainloop()
