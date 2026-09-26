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
PHONE_PATTERN = re.compile(r'(?:(?:\+44\s?\(0\)\s?\d{2,4}|\+44\s?\d{2,4}|0\d{2,4})\s?\d{3,4}\s?\d{3,4}|\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9})')

# History log file path & Auth Profile path
HISTORY_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "search_history.log")
AUTH_PROFILE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "GoogleScraperAuthProfile")
LOCAL_ENRICHMENT_PORT = 8765

# ---------------------------------------------------------------------------
# OFFICIAL UK PUBLIC SECTOR & INDUSTRY DOMAIN REGISTRIES
# ---------------------------------------------------------------------------
UK_FIRE_SERVICES_DOMAINS = {
    # Metropolitan & Combined Services
    "london fire brigade": "london-fire.gov.uk",
    "london fire": "london-fire.gov.uk",
    "lfb": "london-fire.gov.uk",
    "greater manchester fire and rescue": "manchesterfire.gov.uk",
    "greater manchester fire": "manchesterfire.gov.uk",
    "manchester fire": "manchesterfire.gov.uk",
    "gmfrs": "manchesterfire.gov.uk",
    "west midlands fire service": "wmfs.net",
    "west midlands fire": "wmfs.net",
    "wmfs": "wmfs.net",
    "west yorkshire fire and rescue": "westyorksfire.gov.uk",
    "west yorkshire fire": "westyorksfire.gov.uk",
    "wyfrs": "westyorksfire.gov.uk",
    "south yorkshire fire and rescue": "syfire.gov.uk",
    "south yorkshire fire": "syfire.gov.uk",
    "syfr": "syfire.gov.uk",
    "merseyside fire and rescue": "merseyfire.gov.uk",
    "merseyside fire": "merseyfire.gov.uk",
    "mfra": "merseyfire.gov.uk",
    "tyne and wear fire and rescue": "twfire.gov.uk",
    "tyne and wear fire": "twfire.gov.uk",
    "twfrs": "twfire.gov.uk",
    
    # England County Services
    "avon fire and rescue": "avonfire.gov.uk",
    "avon fire": "avonfire.gov.uk",
    "bedfordshire fire and rescue": "bedsfire.gov.uk",
    "bedfordshire fire": "bedsfire.gov.uk",
    "royal berkshire fire and rescue": "rbfrs.co.uk",
    "royal berkshire fire": "rbfrs.co.uk",
    "rbfrs": "rbfrs.co.uk",
    "buckinghamshire and milton keynes fire": "bucksfire.gov.uk",
    "buckinghamshire fire and rescue": "bucksfire.gov.uk",
    "buckinghamshire fire": "bucksfire.gov.uk",
    "bucks fire": "bucksfire.gov.uk",
    "cambridgeshire fire and rescue": "cambsfire.gov.uk",
    "cambridgeshire fire": "cambsfire.gov.uk",
    "cambs fire": "cambsfire.gov.uk",
    "cheshire fire and rescue": "cheshirefire.gov.uk",
    "cheshire fire": "cheshirefire.gov.uk",
    "cleveland fire brigade": "clevelandfire.gov.uk",
    "cleveland fire": "clevelandfire.gov.uk",
    "cornwall fire and rescue": "cornwall.gov.uk",
    "cornwall fire": "cornwall.gov.uk",
    "county durham and darlington fire": "ddfire.gov.uk",
    "durham and darlington fire": "ddfire.gov.uk",
    "durham fire": "ddfire.gov.uk",
    "cddfrs": "ddfire.gov.uk",
    "cumbria fire and rescue": "cumbriafire.gov.uk",
    "cumbria fire": "cumbriafire.gov.uk",
    "derbyshire fire and rescue": "derbys-fire.gov.uk",
    "derbyshire fire": "derbys-fire.gov.uk",
    "dfrs": "derbys-fire.gov.uk",
    "devon and somerset fire and rescue": "dsfire.gov.uk",
    "devon and somerset fire": "dsfire.gov.uk",
    "dsfrs": "dsfire.gov.uk",
    "dorset and wiltshire fire and rescue": "dwfire.org.uk",
    "dorset & wiltshire fire": "dwfire.org.uk",
    "dorset and wiltshire fire": "dwfire.org.uk",
    "dwfrs": "dwfire.org.uk",
    "east sussex fire and rescue": "esfrs.org",
    "east sussex fire": "esfrs.org",
    "esfrs": "esfrs.org",
    "essex county fire and rescue": "essex-fire.gov.uk",
    "essex fire and rescue": "essex-fire.gov.uk",
    "essex fire": "essex-fire.gov.uk",
    "ecfrs": "essex-fire.gov.uk",
    "gloucestershire fire and rescue": "glosfire.gov.uk",
    "gloucestershire fire": "glosfire.gov.uk",
    "hampshire and isle of wight fire and rescue": "hantsfire.gov.uk",
    "hampshire and isle of wight fire": "hantsfire.gov.uk",
    "hampshire & isle of wight fire": "hantsfire.gov.uk",
    "hampshire fire and rescue": "hantsfire.gov.uk",
    "hampshire fire": "hantsfire.gov.uk",
    "hiwfrs": "hantsfire.gov.uk",
    "hereford and worcester fire and rescue": "hwfire.org.uk",
    "hereford & worcester fire": "hwfire.org.uk",
    "hereford and worcester fire": "hwfire.org.uk",
    "hwfrs": "hwfire.org.uk",
    "hertfordshire fire and rescue": "hertfordshire.gov.uk",
    "hertfordshire fire": "hertfordshire.gov.uk",
    "herts fire": "hertfordshire.gov.uk",
    "humberside fire and rescue": "humbersidefire.gov.uk",
    "humberside fire": "humbersidefire.gov.uk",
    "kent fire and rescue": "kent.fire-uk.org",
    "kent fire": "kent.fire-uk.org",
    "kfrs": "kent.fire-uk.org",
    "lancashire fire and rescue": "lancsfirerescue.org.uk",
    "lancashire fire": "lancsfirerescue.org.uk",
    "lfrs": "lancsfirerescue.org.uk",
    "leicestershire fire and rescue": "leics-fire.gov.uk",
    "leicestershire fire": "leics-fire.gov.uk",
    "lincolnshire fire and rescue": "lincolnshire.gov.uk",
    "lincolnshire fire": "lincolnshire.gov.uk",
    "norfolk fire and rescue": "norfolk.gov.uk",
    "norfolk fire": "norfolk.gov.uk",
    "northamptonshire fire and rescue": "northantsfire.gov.uk",
    "northamptonshire fire": "northantsfire.gov.uk",
    "northants fire": "northantsfire.gov.uk",
    "northumberland fire and rescue": "northumberland.gov.uk",
    "northumberland fire": "northumberland.gov.uk",
    "north yorkshire fire and rescue": "northyorksfire.gov.uk",
    "north yorkshire fire": "northyorksfire.gov.uk",
    "nyfrs": "northyorksfire.gov.uk",
    "nottinghamshire fire and rescue": "notts-fire.gov.uk",
    "nottinghamshire fire": "notts-fire.gov.uk",
    "notts fire": "notts-fire.gov.uk",
    "oxfordshire fire and rescue": "oxfordshire.gov.uk",
    "oxfordshire fire": "oxfordshire.gov.uk",
    "shropshire fire and rescue": "shropshirefire.gov.uk",
    "shropshire fire": "shropshirefire.gov.uk",
    "staffordshire fire and rescue": "staffordshirefire.gov.uk",
    "staffordshire fire": "staffordshirefire.gov.uk",
    "suffolk fire and rescue": "suffolk.gov.uk",
    "suffolk fire": "suffolk.gov.uk",
    "surrey fire and rescue": "surreycc.gov.uk",
    "surrey fire": "surreycc.gov.uk",
    "warwickshire fire and rescue": "warwickshire.gov.uk",
    "warwickshire fire": "warwickshire.gov.uk",
    "west sussex fire and rescue": "westsussex.gov.uk",
    "west sussex fire": "westsussex.gov.uk",
    
    # Devolved Nations & National Bodies
    "scottish fire and rescue": "firescotland.gov.uk",
    "scottish fire": "firescotland.gov.uk",
    "scotland fire": "firescotland.gov.uk",
    "sfrs": "firescotland.gov.uk",
    "south wales fire and rescue": "southwales-fire.gov.uk",
    "south wales fire": "southwales-fire.gov.uk",
    "swfrs": "southwales-fire.gov.uk",
    "mid and west wales fire and rescue": "mawwfire.gov.uk",
    "mid and west wales fire": "mawwfire.gov.uk",
    "mawwfrs": "mawwfire.gov.uk",
    "north wales fire and rescue": "northwalesfire.gov.wales",
    "north wales fire": "northwalesfire.gov.wales",
    "nwfrs": "northwalesfire.gov.wales",
    "northern ireland fire and rescue": "nifrs.org",
    "northern ireland fire": "nifrs.org",
    "nifrs": "nifrs.org",
    "national fire chiefs council": "nationalfirechiefs.org.uk",
    "nfcc": "nationalfirechiefs.org.uk",
    "fire service college": "fireservicecollege.ac.uk",
    "fsc": "fireservicecollege.ac.uk"
}

UK_NHS_DOMAINS = {
    "barts health": "bartshealth.nhs.uk",
    "guy's and st thomas": "gstt.nhs.uk",
    "guys and st thomas": "gstt.nhs.uk",
    "imperial college healthcare": "imperial.nhs.uk",
    "king's college hospital": "kch.nhs.uk",
    "kings college hospital": "kch.nhs.uk",
    "manchester university nhs": "mft.nhs.uk",
    "university hospitals birmingham": "uhb.nhs.uk",
    "leeds teaching hospitals": "leedsth.nhs.uk",
    "newcastle upon tyne hospitals": "nuth.nhs.uk",
    "sheffield teaching hospitals": "sth.nhs.uk",
    "nottingham university hospitals": "nuh.nhs.uk",
    "oxford university hospitals": "ouh.nhs.uk",
    "cambridge university hospitals": "cuh.nhs.uk",
    "nhs digital": "nhs.net",
    "nhs england": "england.nhs.uk"
}

UK_COUNCILS_DOMAINS = {
    "birmingham city council": "birmingham.gov.uk",
    "leeds city council": "leeds.gov.uk",
    "glasgow city council": "glasgow.gov.uk",
    "sheffield city council": "sheffield.gov.uk",
    "manchester city council": "manchester.gov.uk",
    "liverpool city council": "liverpool.gov.uk",
    "bristol city council": "bristol.gov.uk",
    "edinburgh city council": "edinburgh.gov.uk",
    "cardiff council": "cardiff.gov.uk",
    "hampshire county council": "hants.gov.uk",
    "essex county council": "essex.gov.uk",
    "kent county council": "kent.gov.uk",
    "surrey county council": "surreycc.gov.uk",
    "lancashire county council": "lancashire.gov.uk"
}

UK_POLICE_DOMAINS = {
    "metropolitan police": "met.police.uk",
    "met police": "met.police.uk",
    "greater manchester police": "gmp.police.uk",
    "west midlands police": "westmidlands.police.uk",
    "west yorkshire police": "westyorkshire.police.uk",
    "thames valley police": "thamesvalley.police.uk",
    "police scotland": "scotland.police.uk",
    "police service of northern ireland": "psni.police.uk",
    "psni": "psni.police.uk"
}

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
    Parses a raw full name string from LinkedIn into (First Name, Surname, Display Name).
    Strips titles, honorifics, post-nominal credentials, pronoun tags, and noise.
    """
    if not full_name:
        return "", "", ""
    
    # Remove unicode emojis and LinkedIn badges
    raw = re.sub(r'[\U00010000-\U0010ffff]', '', full_name)
    raw = raw.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()
    
    # Remove parenthesized pronouns or details (e.g. "John Smith (He/Him)")
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
        return clean_words[0].capitalize(), "", clean_words[0].capitalize()
        
    first_name = clean_words[0].capitalize()
    last_name = clean_words[-1].capitalize()
    
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
        
    # Select active lookup dictionary
    if industry == "nhs":
        lookup_dict = UK_NHS_DOMAINS
    elif industry == "council":
        lookup_dict = UK_COUNCILS_DOMAINS
    elif industry == "police":
        lookup_dict = UK_POLICE_DOMAINS
    else:
        lookup_dict = UK_FIRE_SERVICES_DOMAINS
        
    clean_org = clean_org_text(org_text)
    
    # 1. Exact match
    if clean_org in lookup_dict:
        return lookup_dict[clean_org]
        
    # 2. Check if dictionary key is contained in organization string
    for key, dom in sorted(lookup_dict.items(), key=lambda x: len(x[0]), reverse=True):
        if key in clean_org:
            return dom
            
    # 3. Check combined text (headline + snippet context)
    combined = clean_org_text(f"{org_text} {headline} {snippet}")
    for key, dom in sorted(lookup_dict.items(), key=lambda x: len(x[0]), reverse=True):
        if key in combined:
            return dom
            
    # 4. Check if any .gov.uk or .nhs.uk or .org.uk domain is mentioned directly in snippet
    domain_match = re.search(r'([a-zA-Z0-9.-]+\.(?:gov\.uk|nhs\.uk|police\.uk|org\.uk|ac\.uk|net|org|com))', f"{org_text} {snippet}")
    if domain_match:
        extracted_dom = domain_match.group(1).lower()
        if not extracted_dom.startswith("linkedin.") and not extracted_dom.startswith("google."):
            return extracted_dom
            
    return ""


def verify_domain_mx(domain: str):
    """
    Queries DNS MX records to verify active mail exchangers with local caching.
    Returns: (is_valid: bool, status_label: str, mx_hosts: list)
    """
    if not domain:
        return False, "No Domain", []
    domain = domain.lower().strip()
    if domain in _MX_CACHE:
        return _MX_CACHE[domain]
        
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
    return res



def synthesize_email(first_name: str, last_name: str, domain: str, pattern: str = "{first}.{last}@{domain}") -> str:
    """
    Synthesizes corporate/public sector email based on naming pattern formula.
    """
    if not first_name or not last_name or not domain:
        return ""
        
    f_clean = re.sub(r'[^a-zA-Z0-9]', '', first_name.lower())
    l_clean = re.sub(r'[^a-zA-Z0-9]', '', last_name.lower())
    
    if not f_clean or not l_clean:
        return ""
        
    f_initial = f_clean[0]
    l_initial = l_clean[0]
    
    try:
        formatted = pattern.format(
            first=f_clean,
            last=l_clean,
            f=f_initial,
            l=l_initial,
            domain=domain.lower()
        )
        return formatted
    except Exception:
        return f"{f_clean}.{l_clean}@{domain.lower()}"


def api_enrich_lead(lead_dict: dict, provider: str = "builtin", api_key: str = "", pattern: str = "{first}.{last}@{domain}", industry: str = "fire", custom_domain: str = "") -> dict:
    """
    Core enrichment function supporting Built-in MX Engine, Hunter.io, Apollo, and Snov.io.
    """
    full_name = lead_dict.get("Name", "")
    headline = lead_dict.get("Headline / Role", "")
    org = lead_dict.get("Organisation", "")
    snippet = lead_dict.get("Snippet", "")
    
    first_name, last_name, display_name = parse_lead_name(full_name)
    if not first_name and lead_dict.get("First Name"):
        first_name = lead_dict.get("First Name")
    if not last_name and lead_dict.get("Last Name"):
        last_name = lead_dict.get("Last Name")
        
    domain = lead_dict.get("Domain") or resolve_organization_domain(org, headline, snippet, industry, custom_domain)
    
    # 1. External API: Hunter.io
    if provider == "hunter" and api_key and domain and first_name and last_name:
        try:
            url = f"https://api.hunter.io/v2/email-finder?domain={domain}&first_name={first_name}&last_name={last_name}&api_key={api_key}"
            resp = requests.get(url, timeout=10)
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
            url = "https://api.apollo.io/v1/people/match"
            payload = {"api_key": api_key, "first_name": first_name, "last_name": last_name, "domain": domain}
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                person = resp.json().get("person", {})
                email = person.get("email", "")
                if email:
                    return {
                        "First Name": first_name,
                        "Last Name": last_name,
                        "Domain": domain,
                        "Enriched Email": email,
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
        email = synthesize_email(first_name, last_name, domain, pattern)
        
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
            "Enriched Email": "",
            "Deliverability": "Not Found (Unknown Domain)",
            "Deliverability Badge": "⚪ Not Found",
            "MX Server": "None",
            "Score": 0
        }


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
        self.verifier_filter_var = tk.StringVar(value="")

        # Start Local Enrichment REST Server in background thread
        threading.Thread(target=start_local_enrichment_server, daemon=True).start()

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
        
        # Tab 3: Email & CSV Verifier (MX & SMTP Handshake)
        self.tab_verifier = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.tab_verifier, text=" 🛡️ Email & CSV Verifier (MX/SMTP) ")
        self._build_tab_verifier()
        
        # Tab 4: Search Operators Cheat Sheet
        self.tab_cheatsheet = ttk.Frame(self.notebook, padding="8")
        self.notebook.add(self.tab_cheatsheet, text=" 📖 Search Operators Cheat Sheet ")
        self._build_tab_cheatsheet()
        
        # Tab 5: Search Query History Log
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
        
        self.single_enrich_btn = ttk.Button(enrich_bar, text="⚡ Enrich Selected", style="Accent.TButton", command=self._enrich_selected_lead)
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
        
        # 4. Main View Container (Holds both Interactive Treeview Table and Text Box)
        self.view_container = ttk.Frame(self.tab_results)
        self.view_container.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        
        # A. Interactive Table View (ttk.Treeview)
        self.tree_frame = ttk.Frame(self.view_container)
        
        tree_cols = ("#", "first_name", "last_name", "role", "org", "email", "status", "domain", "url")
        self.col_titles = {
            "#": "#",
            "first_name": "First Name",
            "last_name": "Surname",
            "role": "Job Role / Title",
            "org": "Organisation / Service",
            "email": "Enriched Email",
            "status": "Deliverability",
            "domain": "Resolved Domain",
            "url": "Source URL"
        }
        
        self.tree = ttk.Treeview(self.tree_frame, columns=tree_cols, show="headings", selectmode="extended")
        
        for col in tree_cols:
            self.tree.heading(col, text=self.col_titles[col], command=lambda c=col: self._sort_by_column(c))
        
        self.tree.column("#", width=42, minwidth=30, anchor="center")
        self.tree.column("first_name", width=95, minwidth=75, anchor="w")
        self.tree.column("last_name", width=105, minwidth=80, anchor="w")
        self.tree.column("role", width=175, minwidth=120, anchor="w")
        self.tree.column("org", width=185, minwidth=130, anchor="w")
        self.tree.column("email", width=215, minwidth=150, anchor="w")
        self.tree.column("status", width=135, minwidth=100, anchor="center")
        self.tree.column("domain", width=145, minwidth=100, anchor="w")
        self.tree.column("url", width=130, minwidth=90, anchor="w")
        
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
        
        # Right-click context menu
        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label="⚡ Enrich Selected Contact(s)", command=self._enrich_selected_lead)
        self.tree_menu.add_command(label="🏢 Filter Table by this Organisation", command=self._filter_by_selected_org)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="✉️ Copy Email", command=self._copy_selected_email)
        self.tree_menu.add_command(label="📋 Copy Row Details", command=self._copy_selected_row)
        self.tree_menu.add_command(label="🌐 Open Profile URL in Browser", command=self._open_selected_url)
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
        self.v_stop_btn.pack(side=tk.LEFT, padx=(0, 15))
        
        lbl_tout = ttk.Label(ctl_row1, text="Timeout (sec):")
        lbl_tout.pack(side=tk.LEFT, padx=(0, 4))
        
        tout_spin = ttk.Spinbox(ctl_row1, from_=2, to=30, textvariable=self.verifier_timeout_var, width=4)
        tout_spin.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(tout_spin, "SMTP handshake connection timeout in seconds (8s is recommended).")
        
        chk_call = ttk.Checkbutton(ctl_row1, text="Detect Catch-All Mailboxes", variable=self.verifier_catchall_var)
        chk_call.pack(side=tk.LEFT, padx=(0, 15))
        ToolTip(chk_call, "Tests a randomized non-existent address on the domain to detect catch-all mail servers.")
        
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
        
        # Right-click context menu
        self.v_tree_menu = tk.Menu(self, tearoff=0)
        self.v_tree_menu.add_command(label="🔍 Inspect Full Handshake Details", command=lambda: self._on_verifier_row_double_click(None))
        self.v_tree_menu.add_command(label="✉️ Copy Email Address", command=self._copy_selected_verifier_email)
        self.v_tree_menu.add_command(label="📋 Copy Row Details", command=self._copy_selected_verifier_row)
        
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
        total = len(self.verifier_data)
        
        deliverable_cnt = 0
        risky_cnt = 0
        undeliverable_cnt = 0
        errors_cnt = 0
        
        for idx, item in enumerate(self.verifier_data, 1):
            if self.verifier_stop_requested:
                break
                
            target_email = item.get("email", "")
            self.after(0, self.status_var.set, f"🛡️ Verifying ({idx}/{total}): {target_email}...")
            
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
        self.after(0, self.status_var.set, f"✅ Verification complete: {deliverable_cnt} deliverable, {undeliverable_cnt} undeliverable.")
        
        self.after(0, messagebox.showinfo, "✅ Verification Finished",
            f"✅ Deliverability & SMTP Handshake Complete!\n\n"
            f"Total Processed: {total}\n"
            f"🟢 Deliverable (250 OK): {deliverable_cnt}\n"
            f"🟡 Risky / Catch-All / Greylisted: {risky_cnt}\n"
            f"🔴 Undeliverable (550 / No MX): {undeliverable_cnt}\n\n"
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
            
            combined_text = f"{raw_title} {snippet}"
            emails = EMAIL_PATTERN.findall(combined_text)
            phones = PHONE_PATTERN.findall(combined_text)
            
            clean_title = raw_title.replace(" | LinkedIn", "").replace(" - LinkedIn", "")
            parts = [p.strip() for p in clean_title.split(" - ")]
            name = parts[0] if len(parts) > 0 else clean_title
            headline = parts[1] if len(parts) > 1 else ""
            company = parts[2] if len(parts) > 2 else ""
            
            # Intelligent name entity parsing
            first_name, last_name, display_name = parse_lead_name(name)
            
            # If company missing, attempt parsing from headline (e.g. "Head of IT at Greater Manchester Fire")
            if not company and " at " in headline:
                company = headline.split(" at ")[-1].strip()
            elif not company and " @ " in headline:
                company = headline.split(" @ ")[-1].strip()
                
            industry = self.enrich_industry_var.get() if hasattr(self, "enrich_industry_var") else "fire"
            custom_dom = self.custom_email_domain_var.get() if hasattr(self, "custom_email_domain_var") else ""
            resolved_dom = resolve_organization_domain(company, headline, snippet, industry, custom_dom)
            
            raw_email = ", ".join(list(dict.fromkeys(emails))) if emails else ""
            
            # Pre-synthesize email candidate if domain is resolved and no raw email was found
            if not raw_email and resolved_dom and first_name and last_name:
                pat = self.enrich_pattern_var.get() if hasattr(self, "enrich_pattern_var") else "{first}.{last}@{domain}"
                enriched_email = synthesize_email(first_name, last_name, resolved_dom, pat)
                deliv_status = "Pending Verification"
                deliv_badge = "⚪ Pending"
            else:
                enriched_email = raw_email
                deliv_status = "Valid (Scraped)" if raw_email else "Not Enriched"
                deliv_badge = "🟢 Scraped" if raw_email else "⚪ Not Found"
            
            normalized_leads.append({
                "First Name": first_name,
                "Last Name": last_name,
                "Name": display_name or name,
                "Headline / Role": headline,
                "Organisation": company,
                "Domain": resolved_dom,
                "Enriched Email": enriched_email,
                "Deliverability": deliv_status,
                "Deliverability Badge": deliv_badge,
                "MX Server": "",
                "Email": raw_email,
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
            messagebox.showinfo("No Email Found", "The selected contact(s) do not have an email address yet.\n\nTip: Click '⚡ Enrich Selected' to discover and verify their email.")

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
                    lines.append(f"{r.get('First Name', '')} {r.get('Last Name', '')} | {r.get('Headline / Role', '')} | {r.get('Organisation', '')} | {email_val} | {r.get('Deliverability', '')} | {r.get('URL', '')}")
            except Exception:
                pass
        if lines:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
            self.status_var.set(f"Copied {len(lines)} contact row(s) to clipboard.")
            messagebox.showinfo("Copied Details", f"Copied {len(lines)} row(s) to clipboard!")

    def _open_selected_url(self):
        """Opens profile URL of selected contact in default web browser."""
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
            "🚒 UK Fire & Rescue Services (50+ official .gov.uk domains)",
            "🏥 NHS Trusts & Health Boards (.nhs.uk domains)",
            "🏛️ UK Local Councils & Authorities (.gov.uk)",
            "👮 UK Police Constabularies (.police.uk)",
            "🏢 Custom Domain (Specified below)"
        )
        
        curr_ind = self.enrich_industry_var.get()
        if curr_ind == "nhs":
            ind_combo.current(1)
        elif curr_ind == "council":
            ind_combo.current(2)
        elif curr_ind == "police":
            ind_combo.current(3)
        elif curr_ind == "custom":
            ind_combo.current(4)
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
            "{first}.{last}@{domain} (e.g. john.smith@london-fire.gov.uk - UK Public Sector Standard)",
            "{f}{last}@{domain} (e.g. jsmith@london-fire.gov.uk)",
            "{first}{last}@{domain} (e.g. johnsmith@london-fire.gov.uk)",
            "{first}_{last}@{domain} (e.g. john_smith@london-fire.gov.uk)",
            "{last}.{first}@{domain} (e.g. smith.john@london-fire.gov.uk)"
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
            if "NHS" in raw_ind:
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
