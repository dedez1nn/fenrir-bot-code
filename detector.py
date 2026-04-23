import validators
from urllib.parse import urlparse

DOMAINS_FILE = "domains.txt"

# carrega lista
def load_domains():
    try:
        with open(DOMAINS_FILE, "r") as f:
            return set(line.strip().lower() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def save_domain(domain: str):
    with open(DOMAINS_FILE, "a") as f:
        f.write(domain.lower() + "\n")

CUSTOM_DOMAINS = load_domains()


def extract_domain(url: str):
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except:
        return ""


def domain_match_score(domain: str):
    """
    Score alto (quase determinístico)
    """
    for d in CUSTOM_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return 5  # peso alto
    return 0


def heuristic_score(url: str):
    score = 0

    if len(url) > 75:
        score += 1

    if "@" in url:
        score += 2

    if url.count("//") > 1:
        score += 1

    if any(tld in url for tld in [".xyz", ".ru", ".tk"]):
        score += 1

    return score


# ML opcional
try:
    from phishing_detection_py import PhishingDetector
    detector = PhishingDetector(model_type="url")
    ML_ENABLED = True
except:
    ML_ENABLED = False


def analyze_url(url: str):
    if not validators.url(url):
        return {"status": "invalid"}

    domain = extract_domain(url)

    base_score = heuristic_score(url)
    domain_score = domain_match_score(domain)

    total_score = base_score + domain_score

    # regra quase determinística
    if domain_score >= 5:
        return {
            "status": "blocked",
            "score": total_score,
            "reason": "custom_domain_match",
            "domain": domain
        }

    if total_score >= 2:
        if ML_ENABLED:
            result = detector.predict(url)
            return {
                "status": result,
                "score": total_score,
                "method": "heuristic+ml"
            }
        else:
            return {
                "status": "suspicious",
                "score": total_score,
                "method": "heuristic"
            }

    return {
        "status": "safe",
        "score": total_score,
        "method": "heuristic"
    }