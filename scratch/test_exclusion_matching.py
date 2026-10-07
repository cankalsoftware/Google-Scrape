import re
import urllib.parse

def should_exclude_result(url: str, title: str = "", snippet: str = "", exclusions: str = "") -> bool:
    """
    Checks whether a search result card matches active negative exclusion rules.
    Inspects words in the domain (including subdomains like uk.indeed.com), URL path,
    title, and snippet against negative exclusion tokens (e.g. -indeed, -careers, -tripadvisor).
    """
    if not exclusions or not exclusions.strip():
        return False
        
    url_lower = (url or "").lower()
    parsed = urllib.parse.urlparse(url_lower)
    netloc = parsed.netloc.lower()
    clean_netloc = re.sub(r'^www\.', '', netloc)
    path = parsed.path.lower()
    
    # Split domain into sub-parts (e.g. 'uk.indeed.com' -> ['uk', 'indeed', 'com'])
    domain_parts = [p for p in re.split(r'[\.\-_]', clean_netloc) if p]
    
    title_lower = (title or "").lower()
    snippet_lower = (snippet or "").lower()

    # Extract all negative exclusion tokens from the exclusion string (tokens starting with -)
    tokens = [t.strip().lstrip('-').lower() for t in exclusions.split() if t.strip().startswith('-')]
    
    for tok in tokens:
        if not tok:
            continue
            
        # Clean operator prefixes like site: or inurl: or intext:
        clean_tok = re.sub(r'^(?:site|inurl|intext|intitle):\s*', '', tok).strip()
        if not clean_tok:
            continue
            
        # If token has a dot (e.g. indeed.com, tripadvisor.com, bbc.co.uk)
        if "." in clean_tok:
            tok_root = clean_tok.split('.')[0] # e.g. 'indeed', 'tripadvisor', 'booking'
            # 1. Check exact or root word match in domain / netloc (matches uk.indeed.com, indeed.co.uk, etc.)
            if clean_tok in clean_netloc or (len(tok_root) >= 3 and tok_root in domain_parts):
                return True
            if clean_tok in url_lower or (len(tok_root) >= 3 and tok_root in url_lower):
                return True
        else:
            # Word token without dot (e.g. 'indeed', 'career', 'careers', 'jobs', 'recruiting', 'directory', 'news')
            # 1. Check if word exists in domain / subdomain parts (e.g. 'uk.indeed.com', 'careers.hilton.com', 'jobs.theguardian.com')
            if clean_tok in domain_parts or clean_tok in clean_netloc:
                return True
                
            # 2. Check if word exists in URL path boundaries (e.g. /careers/, /career/, /jobs/, /job/)
            tok_stem = clean_tok.rstrip('s') if len(clean_tok) > 4 else clean_tok
            if re.search(r'[/_\-]' + re.escape(tok_stem) + r'(?:s)?(?:[/_\-.]|$)', path):
                return True
                
            # 3. Check for specific strong noise keywords in title / snippet if excluded
            if len(clean_tok) >= 4 and clean_tok in ["career", "careers", "job", "jobs", "recruiting", "recruiter", "hiring", "vacancies", "vacancy"]:
                if re.search(r'\b' + re.escape(tok_stem) + r'(?:s|ing)?\b', title_lower):
                    return True

    return False

test_cases = [
    ("https://uk.indeed.com/viewjob?jk=123", "Waiter in Didim", "Apply now on indeed", "-tripadvisor.com -booking.com -jobs -careers -indeed.com", True),
    ("https://careers.hilton.com/jobs/waiter", "Careers at Hilton", "Join our team", "-tripadvisor.com -booking.com -jobs -careers", True),
    ("https://www.marriott.com/careers/positions", "Marriott Careers", "Open positions", "-careers", True),
    ("https://www.tripadvisor.com.tr/Restaurant_Review-g123-d456", "Top Didim Restaurants", "Reviews and photos", "-tripadvisor.com", True),
    ("https://www.hilton.com/en/hotels/ist-didim/", "Hilton Didim Hotel", "Official website booking", "-indeed.com -careers -tripadvisor.com", False),
    ("https://www.didimrestaurant.com/menu", "Didim Fresh Seafood", "Best fish in Altinkum", "-indeed.com -careers -jobs -tripadvisor.com -booking.com", False),
    ("https://www.yell.com/biz/restaurant-didim-123/", "Didim Restaurant on Yell", "Local directory listing", "-yell.com -directory", True),
    ("https://en.wikipedia.org/wiki/Didim", "Didim - Wikipedia", "Didim is a small town...", "-wikipedia.org", True),
]

if __name__ == '__main__':
    all_passed = True
    for url, title, snip, ex, expected in test_cases:
        res = should_exclude_result(url, title, snip, ex)
        status = "PASS" if res == expected else "FAIL"
        if res != expected:
            all_passed = False
        print(f"[{status}] URL: {url} | Excluded: {res} (Expected: {expected})")
    print(f"\nOverall Result: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
