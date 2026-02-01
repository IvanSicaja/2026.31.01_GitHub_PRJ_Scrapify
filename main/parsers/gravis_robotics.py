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
    # Primary: standard Lever.co sections
    sections = detail_soup.find_all("div", class_="section page-centered")
    if sections:
        return "\n\n".join(
            section.get_text(separator="\n", strip=True) for section in sections
        )

    # Fallback 1: other common Lever containers
    alt_containers = [
        detail_soup.find("div", class_="posting-description"),
        detail_soup.find("div", class_="description"),
        detail_soup.find("article"),
        detail_soup.find("div", class_="content"),
        detail_soup.find("main"),
    ]
    for container in alt_containers:
        if container:
            text = container.get_text(separator="\n", strip=True)
            if len(text) > 200:  # reasonable minimum length
                return text

    # Ultimate fallback: whole body text, cleaned
    body_text = detail_soup.get_text(separator="\n", strip=True)
    lines = [line for line in body_text.splitlines() if len(line.strip()) > 10]
    return "\n".join(lines)


CONFIG = {
    "url": "https://jobs.lever.co/gravisrobotics",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    },
    "note": "Lever.co standard – added fallback selectors for varying job layouts"
}