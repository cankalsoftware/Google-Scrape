import re

def format_as_or_tokens(text: str) -> str:
    if not text:
        return ""
    clean = text.strip()
    if clean.startswith("e.g.") or clean.startswith("(e.g."):
        return ""
    if clean.startswith("(") and clean.endswith(")"):
        inner = clean[1:-1].strip()
        if re.fullmatch(r'("[^"]+"\s+OR\s+)+"[^"]+"', inner, re.IGNORECASE) or re.fullmatch(r'"[^"]+"', inner):
            return clean
        clean = inner

    lines = [ln.strip() for ln in clean.splitlines() if ln.strip()]
    raw_items = []
    for ln in lines:
        if "," in ln:
            raw_items.extend([p.strip() for p in ln.split(",") if p.strip()])
        elif re.search(r'\s+(?:OR|or)\s+', ln):
            raw_items.extend([p.strip() for p in re.split(r'\s+(?:OR|or)\s+', ln) if p.strip()])
        else:
            quoted_matches = re.findall(r'"([^"]+)"|\'([^\']+)\'', ln)
            if quoted_matches and len(quoted_matches) > 1:
                for q1, q2 in quoted_matches:
                    q = q1 or q2
                    if q.strip():
                        raw_items.append(q.strip())
            else:
                raw_items.append(ln.strip())

    items = []
    for item in raw_items:
        item_clean = item.strip().strip('"\'').strip()
        if item_clean and item_clean.upper() != "OR":
            items.append(item_clean)

    if not items:
        return ""
    return "(" + " OR ".join(f'"{item}"' for item in items) + ")"

test_inputs = [
    'hotels, restaurants, travel agencies',
    '"hotels", "restaurants", "travel agencies"',
    'Didim or altinkum or Bodrum',
    '"Didim" OR "altinkum"',
    '("Didim" OR "altinkum")',
    'Managing Director, Operations Director, General Manager',
    'hotels\nrestaurants\ntours',
    '"hotels" "restaurants" "resorts"',
    'SingleTerm',
    'Didim, altinkum and turkey'
]

if __name__ == '__main__':
    for inp in test_inputs:
        out = format_as_or_tokens(inp)
        print(f"IN : {inp!r} --> OUT: {out!r}")
