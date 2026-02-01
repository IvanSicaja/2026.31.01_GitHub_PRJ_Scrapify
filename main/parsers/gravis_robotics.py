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
    sections = detail_soup.find_all("div", class_="section page-centered")
    full_text = "\n\n".join(
        section.get_text(separator="\n", strip=True) for section in sections
    )
    return full_text


CONFIG = {
    "url": "https://jobs.lever.co/gravisrobotics",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    },
    "note": "Lever.co standard"
}