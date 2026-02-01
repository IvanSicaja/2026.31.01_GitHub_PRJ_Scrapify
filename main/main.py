import sys
import json
import time
import requests
from bs4 import BeautifulSoup
import openpyxl
from openpyxl import Workbook
from openpyxl.utils.exceptions import IllegalCharacterError
from datetime import date
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QMessageBox, QProgressBar, QTextEdit, QComboBox,
    QRadioButton, QGroupBox
)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# ---------------------------------------------------------------------------
# LOAD CONFIGURATIONS FROM EXTERNAL JSON
# ---------------------------------------------------------------------------
CONFIG_FILE = "companies.json"

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    print(f"Warning: {CONFIG_FILE} not found. Using empty config.")
    CONFIG = {}
except Exception as e:
    print(f"Error loading {CONFIG_FILE}: {e}")
    CONFIG = {}

# Companies without config (placeholders)
COMPANIES_NO_CONFIG = ["Hexagon AB", "Flink Robotics"]

# ---------------------------------------------------------------------------
# PARSER FUNCTIONS
# ---------------------------------------------------------------------------

HEADERS_DEFAULT = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def lever_listing_parser(soup):
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

def lever_detail_parser(detail_soup):
    sections = detail_soup.find_all("div", class_="section page-centered")
    return "\n\n".join(s.get_text(separator="\n", strip=True) for s in sections)

def anybotics_listing_parser(soup):
    # Uses Workable API directly
    api_url = "https://api.workable.com/organization/anybotics/jobs"
    try:
        resp = requests.get(api_url, headers=HEADERS_DEFAULT, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        jobs = []
        for job in data.get("jobs", []):
            title = job.get("title", "").strip()
            url = job.get("url", "").strip()
            if title and url:
                jobs.append((title, url))
        return jobs
    except Exception:
        return []

def anybotics_detail_parser(detail_soup):
    desc_div = detail_soup.find("div", class_="description")
    if desc_div:
        return desc_div.get_text(separator="\n", strip=True)
    main = detail_soup.find("main") or detail_soup.find("div", class_="content")
    if main:
        return main.get_text(separator="\n", strip=True)
    return detail_soup.get_text(separator="\n", strip=True)

def mimic_listing_parser(soup):
    jobs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(kw in href.lower() for kw in ["/jobs/", "/careers/", "/job/"]):
            title = a.get_text(strip=True)
            if title and len(title) > 3:
                jobs.append((title, href if href.startswith("http") else "https://www.mimicrobotics.com" + href))
    return jobs

def mimic_detail_parser(detail_soup):
    for tag in ["main", "article"]:
        el = detail_soup.find(tag)
        if el:
            return el.get_text(separator="\n", strip=True)
    body = detail_soup.find("body")
    return body.get_text(separator="\n", strip=True) if body else ""

def leica_listing_parser(soup):
    try:
        api = "https://careers.hexagon.com/api/v1/jobs?brand=leica-geosystems&limit=100"
        resp = requests.get(api, headers=HEADERS_DEFAULT, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        jobs = []
        for job in data.get("jobs", data.get("results", [])):
            title = job.get("title", job.get("name", "")).strip()
            url = job.get("url", job.get("link", "")).strip()
            if title and url:
                jobs.append((title, url))
        return jobs
    except Exception:
        jobs = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "job" in href.lower() and ("leica" in href.lower() or "hexagon" in href.lower()):
                title = a.get_text(strip=True)
                if title and len(title) > 3:
                    jobs.append((title, href if href.startswith("http") else "https://leica-geosystems.com" + href))
        return jobs

def leica_detail_parser(detail_soup):
    for cls in ["job-description", "description", "content"]:
        el = detail_soup.find(class_=cls)
        if el:
            return el.get_text(separator="\n", strip=True)
    main = detail_soup.find("main")
    if main:
        return main.get_text(separator="\n", strip=True)
    return ""

def hexagon_robotics_listing_parser(soup):
    jobs = []
    for h5 in soup.find_all("h5"):
        a = h5.find("a", href=True)
        if a:
            title = a.get_text(strip=True)
            url = a["href"]
            if title and url:
                jobs.append((title, url if url.startswith("http") else "https://robotics.hexagon.com" + url))
    return jobs

def hexagon_robotics_detail_parser(detail_soup):
    for cls in ["job-description", "description", "content", "oj-content"]:
        el = detail_soup.find(class_=cls)
        if el:
            return el.get_text(separator="\n", strip=True)
    main = detail_soup.find("main") or detail_soup.find("body")
    if main:
        text = main.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if len(l.strip()) > 20]
        return "\n".join(lines)
    return ""

def flexion_listing_parser(soup):
    jobs = []
    seen = set()
    for h5 in soup.find_all("h5"):
        a = h5.find("a", href=True)
        if not a:
            parent_a = h5.find_parent("a", href=True)
            if parent_a:
                a = parent_a
            else:
                continue
        title = h5.get_text(strip=True)
        href = a["href"]
        if href.startswith("./"):
            url = "https://flexion.ai" + href[1:]
        elif href.startswith("/"):
            url = "https://flexion.ai" + href
        elif not href.startswith("http"):
            url = "https://flexion.ai/" + href
        else:
            url = href
        if title and url and url not in seen:
            seen.add(url)
            jobs.append((title, url))
    return jobs

def flexion_detail_parser(detail_soup):
    for cls in ["description", "job-description", "content"]:
        el = detail_soup.find(class_=cls)
        if el:
            return el.get_text(separator="\n", strip=True)
    body = detail_soup.find("body")
    if body:
        text = body.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if len(l.strip()) > 15]
        return "\n".join(lines)
    return ""

def flyability_listing_parser(soup):
    jobs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(kw in href.lower() for kw in ["/career/", "/careers/", "/job/", "/position/"]):
            title = a.get_text(strip=True)
            if title and len(title) > 3 and not any(
                skip in title.lower() for skip in ["open position", "back", "apply", "see all", "view all"]
            ):
                url = href if href.startswith("http") else "https://www.flyability.com" + href
                jobs.append((title, url))
    seen_titles = set()
    unique = []
    for t, u in jobs:
        if t not in seen_titles:
            seen_titles.add(t)
            unique.append((t, u))
    return unique

def flyability_detail_parser(detail_soup):
    for cls in ["job-description", "description", "content", "entry-content"]:
        el = detail_soup.find(class_=cls)
        if el:
            return el.get_text(separator="\n", strip=True)
    main = detail_soup.find("main") or detail_soup.find("article")
    if main:
        return main.get_text(separator="\n", strip=True)
    return ""

# ---------------------------------------------------------------------------
# MAP PARSER NAMES → FUNCTIONS (must be AFTER all definitions!)
# ---------------------------------------------------------------------------
PARSER_MAP = {
    "lever_listing_parser": lever_listing_parser,
    "lever_detail_parser": lever_detail_parser,
    "anybotics_listing_parser": anybotics_listing_parser,
    "anybotics_detail_parser": anybotics_detail_parser,
    "mimic_listing_parser": mimic_listing_parser,
    "mimic_detail_parser": mimic_detail_parser,
    "leica_listing_parser": leica_listing_parser,
    "leica_detail_parser": leica_detail_parser,
    "hexagon_robotics_listing_parser": hexagon_robotics_listing_parser,
    "hexagon_robotics_detail_parser": hexagon_robotics_detail_parser,
    "flexion_listing_parser": flexion_listing_parser,
    "flexion_detail_parser": flexion_detail_parser,
    "flyability_listing_parser": flyability_listing_parser,
    "flyability_detail_parser": flyability_detail_parser,
}

# ---------------------------------------------------------------------------
# WORKER THREAD
# ---------------------------------------------------------------------------

class Worker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str, list)  # success, message, errors

    def __init__(self, selected_companies: list):
        super().__init__()
        self.selected_companies = selected_companies

    def run(self):
        errors = []
        all_jobs = []
        today_date = date.today().strftime("%m/%d/%Y")
        total = len(self.selected_companies)

        for idx, company in enumerate(self.selected_companies, 1):
            if company not in CONFIG:
                errors.append(f"{company}: No configuration in companies.json")
                self.log.emit(f"⚠ {company} — no config, skipping.")
                continue

            cfg = CONFIG[company]
            self.log.emit(f"\n── {company} ({idx}/{total}) ──")
            if cfg.get("note"):
                self.log.emit(f"ℹ {cfg['note']}")

            base_prog = int((idx-1) / total * 80)
            range_prog = int(80 / total) if total > 0 else 0

            try:
                self.status.emit(f"[{company}] Fetching listings…")
                resp = requests.get(
                    cfg["url"],
                    headers=cfg.get("headers", HEADERS_DEFAULT),
                    timeout=20
                )
                resp.raise_for_status()
            except Exception as e:
                err_msg = f"{company}: Failed to fetch listings page – {str(e)}"
                errors.append(err_msg)
                self.log.emit(f"✗ {err_msg}")
                continue

            self.progress.emit(base_prog + int(range_prog * 0.15))

            soup = BeautifulSoup(resp.text, "html.parser")
            try:
                listing_func_name = cfg["listing_parser"]
                listing_func = PARSER_MAP.get(listing_func_name)
                if not listing_func:
                    raise KeyError(f"Parser '{listing_func_name}' not found in PARSER_MAP")
                job_list = listing_func(soup)
            except Exception as e:
                err_msg = f"{company}: Listing parser failed – {str(e)}"
                errors.append(err_msg)
                self.log.emit(f"✗ {err_msg}")
                continue

            num = len(job_list)
            if num == 0:
                self.log.emit(f"⚠ No postings found.")
                self.progress.emit(base_prog + range_prog)
                continue

            self.log.emit(f"Found {num} postings")
            self.progress.emit(base_prog + int(range_prog * 0.25))

            detail_step = (range_prog * 0.60) / num if num else 0
            for i, (title, url) in enumerate(job_list, 1):
                self.status.emit(f"[{company}] {i}/{num}: {title}")
                try:
                    detail_resp = requests.get(
                        url,
                        headers=cfg.get("headers", HEADERS_DEFAULT),
                        timeout=15
                    )
                    detail_resp.raise_for_status()
                    detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

                    detail_func_name = cfg["detail_parser"]
                    detail_func = PARSER_MAP.get(detail_func_name)
                    if not detail_func:
                        raise KeyError(f"Parser '{detail_func_name}' not found in PARSER_MAP")
                    desc = detail_func(detail_soup)

                    if desc.strip():
                        all_jobs.append((today_date, company, title, desc.strip()))
                        self.log.emit(f"✔ {title}")
                    else:
                        self.log.emit(f"✗ No description: {title}")
                except Exception as e:
                    err_msg = f"{company} – {title}: {str(e)}"
                    errors.append(err_msg)
                    self.log.emit(f"✗ {err_msg}")

                self.progress.emit(base_prog + int(range_prog * 0.25 + i * detail_step))
                time.sleep(0.5)

            self.progress.emit(base_prog + range_prog)

        # Save to Excel
        if not all_jobs:
            self.finished.emit(True, "Scraping complete — no job descriptions collected.", errors)
            return

        self.status.emit("Saving to Excel…")
        file_name = "Scrapify.xlsx"
        try:
            wb = openpyxl.load_workbook(file_name)
        except FileNotFoundError:
            wb = Workbook()
            ws = wb.active
            ws.title = "Sheet1"
            ws.append(["Date", "Company", "Role", "Role description"])
        ws = wb["Sheet1"]

        insert_step = 20 / len(all_jobs) if all_jobs else 0
        prog = 80
        for job in reversed(all_jobs):
            ws.insert_rows(2)
            try:
                ws.cell(2, 1, job[0])
                ws.cell(2, 2, job[1])
                ws.cell(2, 3, job[2])
                ws.cell(2, 4, job[3])
            except IllegalCharacterError:
                clean = ''.join(c for c in job[3] if c.isprintable())
                ws.cell(2, 4, clean)
            prog += insert_step
            self.progress.emit(int(prog))

        wb.save(file_name)
        self.progress.emit(100)
        self.finished.emit(True, f"Added {len(all_jobs)} job(s) to {file_name}.", errors)

# ---------------------------------------------------------------------------
# GUI (unchanged except finished signal now has 3 args)
# ---------------------------------------------------------------------------

class ScraperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scrapify — Job Scraper")
        self.setFixedSize(560, 520)
        # Your full stylesheet here (copy from your original code)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QLabel { color: #e0e0e0; font-size: 14px; font-family: -apple-system, sans-serif; }
            QGroupBox { color: #aaa; font-size: 13px; border: 1px solid #333; border-radius: 8px; margin-top: 10px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QRadioButton { color: #ccc; font-size: 13px; spacing: 6px; }
            QRadioButton::indicator { width: 16px; height: 16px; border-radius: 8px; border: 2px solid #555; background: #2a2a2a; }
            QRadioButton::indicator:checked { background: #0a84ff; border-color: #0a84ff; }
            QComboBox { background-color: #2a2a2a; color: #e0e0e0; border: 1px solid #444; border-radius: 8px; padding: 6px 10px; font-size: 13px; }
            QComboBox:disabled { background-color: #1e1e1e; color: #555; border-color: #333; }
            QProgressBar { height: 14px; border-radius: 7px; background: #2a2a2a; text-align: center; color: #aaa; font-size: 11px; }
            QProgressBar::chunk { background-color: #0a84ff; border-radius: 7px; }
            QTextEdit { background-color: #121212; color: #d0d0d0; border: none; border-radius: 10px; padding: 10px; font-family: Consolas, monospace; font-size: 12px; }
            QPushButton { background-color: #0a84ff; color: white; border: none; border-radius: 12px; padding: 12px; font-size: 15px; font-weight: 600; }
            QPushButton:hover { background-color: #0070e0; }
            QPushButton:disabled { background-color: #444; color: #888; }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title_label = QLabel("Scrapify — Job Scraper")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #fff;")
        layout.addWidget(title_label)

        mode_group = QGroupBox("Scrape target")
        mode_layout = QVBoxLayout()
        mode_layout.setContentsMargins(12, 6, 12, 8)
        mode_layout.setSpacing(6)

        self.radio_all = QRadioButton("All companies")
        self.radio_all.setChecked(True)
        self.radio_all.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.radio_all)

        single_row = QHBoxLayout()
        single_row.setSpacing(8)
        self.radio_single = QRadioButton("One company")
        self.radio_single.toggled.connect(self._on_mode_changed)
        single_row.addWidget(self.radio_single)

        self.company_combo = QComboBox()
        self.company_combo.setFixedHeight(30)
        self.company_combo.setEnabled(False)
        for name in CONFIG:
            self.company_combo.addItem(name)
        for name in COMPANIES_NO_CONFIG:
            self.company_combo.addItem(f"{name} (no config)")
        single_row.addWidget(self.company_combo, stretch=1)
        mode_layout.addLayout(single_row)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text, stretch=1)

        self.scrape_button = QPushButton("Run Scraper")
        self.scrape_button.setFixedHeight(46)
        self.scrape_button.clicked.connect(self.start_scraper)
        layout.addWidget(self.scrape_button)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def _on_mode_changed(self):
        self.company_combo.setEnabled(self.radio_single.isChecked())

    def _get_selected_companies(self):
        if self.radio_all.isChecked():
            return list(CONFIG.keys())
        else:
            chosen = self.company_combo.currentText()
            if chosen.endswith("(no config)"):
                QMessageBox.warning(self, "Warning", "Selected company has no configuration.")
                return []
            return [chosen]

    def start_scraper(self):
        companies = self._get_selected_companies()
        if not companies:
            return

        self.scrape_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting…")
        self.log_text.clear()

        self.worker = Worker(companies)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(self.status_label.setText)
        self.worker.log.connect(self.log_text.append)
        self.worker.finished.connect(self.scraper_finished)
        self.worker.start()

    def scraper_finished(self, success: bool, message: str, errors: list):
        self.progress_bar.setValue(100 if success else self.progress_bar.value())
        self.scrape_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            QMessageBox.information(self, "Scrapify", message)
            self.status_label.setText("Done")
        else:
            QMessageBox.critical(self, "Error", message)
            self.status_label.setText("Failed")

        if errors:
            error_text = "The following errors occurred during scraping:\n\n" + "\n".join(f"• {e}" for e in errors)
            QMessageBox.warning(self, "Scraping Issues", error_text + "\n\nCopy this text if you want to report/fix them.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScraperApp()
    window.show()
    sys.exit(app.exec())