from bs4 import BeautifulSoup

def listing_parser(soup):
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

def detail_parser(detail_soup):
    sections = detail_soup.find_all("div", class_="section page-centered")
    return "\n\n".join(s.get_text(separator="\n", strip=True) for s in sections)

CONFIG = {
    "url": "https://jobs.lever.co/rivr",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    },
    "note": "Lever.co standard"
}