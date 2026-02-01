from bs4 import BeautifulSoup

def listing_parser(soup):
    """
    Find job cards/titles/links on https://flexion.ai/careers
    Framer sites often use h tags inside links or cards.
    """
    jobs = []
    seen_urls = set()

    # Look for headings that are likely job titles
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        # Get parent or self link
        link_tag = heading.find_parent('a', href=True) or heading.find('a', href=True)
        if not link_tag:
            continue

        title = heading.get_text(strip=True)
        if not title or len(title) < 8:
            continue

        href = link_tag['href']
        if not href.startswith('http'):
            href = 'https://flexion.ai' + (href if href.startswith('/') else '/' + href)

        if href not in seen_urls:
            seen_urls.add(href)
            jobs.append((title, href))

    return jobs


def detail_parser(detail_soup):
    """
    Extract only the job description part on Flexion detail pages.
    Avoids header, footer, sidebar, navigation, etc.
    """
    # Possible good containers (ordered by likelihood)
    candidates = [
        detail_soup.select_one('div[data-block-type="text"]'),           # Framer text block
        detail_soup.select_one('div.job-description'),
        detail_soup.select_one('div.description'),
        detail_soup.select_one('article'),
        detail_soup.select_one('div.content'),
        detail_soup.select_one('main'),
    ]

    for candidate in candidates:
        if not candidate:
            continue

        # Clean and filter
        text = candidate.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Skip if too short or looks like navigation/footer
        if len(lines) < 5 or any(
            word in text.lower() for word in ['footer', '©', 'all rights reserved', 'privacy policy', 'cookie', 'imprint']
        ):
            continue

        # Good candidate if long enough
        if len(text) > 300:
            return text

    # Last resort: whole page but aggressive filtering
    full_text = detail_soup.get_text(separator='\n', strip=True)
    lines = [l.strip() for l in full_text.splitlines() if len(l.strip()) > 15]

    # Try to cut off footer/nav by looking for common ending markers
    cutoff_keywords = ['©', 'all rights reserved', 'privacy', 'cookie', 'imprint', 'contact us', 'back to top']
    filtered_lines = []
    for line in lines:
        if any(kw in line.lower() for kw in cutoff_keywords):
            break
        filtered_lines.append(line)

    cleaned = '\n'.join(filtered_lines)
    if len(cleaned) > 200:
        return cleaned

    return ""  # truly nothing useful


CONFIG = {
    "url": "https://flexion.ai/careers",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    },
    "note": "Framer site – improved filtering to avoid header/footer noise"
}