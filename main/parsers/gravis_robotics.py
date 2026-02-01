from bs4 import BeautifulSoup

def listing_parser(soup: BeautifulSoup):
    jobs = []
    for post in soup.find_all("div", class_="posting"):
        title_elem = post.find("h5")
        if not title_elem:
            continue
        title = title_elem.text.strip()
        link_elem = post.find("a", class_="posting-title")
        if not link_elem or not link_elem.get("href"):
            continue
        jobs.append((title, link_elem["href"]))
    return jobs

def detail_parser(detail_soup: BeautifulSoup):
    # Primary selector
    sections = detail_soup.find_all("div", class_="section-wrapper page-centered")
    if sections:
        return "\n\n".join(
            s.get_text(separator="\n", strip=True) for s in sections
        )

    # Fallback selectors
    fallback_selectors = [
        "div.section-wrapper",
        "div.posting-page-description",
        "div.description",
        "div.job-description",
        "article",
        "main",
        "body"
    ]
    for selector in fallback_selectors:
        elements = detail_soup.find_all(selector)
        text = "\n\n".join(
            el.get_text(separator="\n", strip=True) for el in elements
        )
        if text.strip() and len(text) > 200:
            return text

    # Cleaned full page fallback
    full_text = detail_soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in full_text.splitlines() if len(l.strip()) > 5 and not l.startswith("Apply for this job")]
    return "\n".join(lines)

CONFIG = {
    "url": "https://jobs.lever.co/gravisrobotics",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    },
    "note": "Lever.co - enhanced fallbacks for description extraction"
}