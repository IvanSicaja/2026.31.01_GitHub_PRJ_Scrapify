import sys
import time
import requests
from bs4 import BeautifulSoup
import openpyxl
from openpyxl import Workbook
from openpyxl.utils.exceptions import IllegalCharacterError
from datetime import date, datetime
import importlib
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QMessageBox, QProgressBar, QTextEdit, QComboBox,
    QRadioButton, QGroupBox
)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt, QThread, pyqtSignal

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
        all_jobs = []  # (date, company, title, description)
        today_date = date.today().strftime("%m/%d/%Y")
        total = len(self.selected_companies)

        for idx, company in enumerate(self.selected_companies, 1):
            module_name = company.lower().replace(" ", "_")
            try:
                module = importlib.import_module(f"parsers.{module_name}")
                cfg = module.CONFIG
                listing_parser = module.listing_parser
                detail_parser = module.detail_parser
            except ImportError:
                err = f"{company}: No parser file (parsers/{module_name}.py)"
                errors.append(err)
                self.log.emit(f"⚠ {err} — skipping.")
                continue
            except AttributeError as e:
                err = f"{company}: Invalid parser file – {str(e)} (missing CONFIG/listing_parser/detail_parser?)"
                errors.append(err)
                self.log.emit(f"✗ {err}")
                continue

            self.log.emit(f"\n── {company} ({idx}/{total}) ──")
            if cfg.get("note"):
                self.log.emit(f" ℹ {cfg['note']}")

            base_progress = int((idx - 1) / total * 80)
            company_progress_range = int(80 / total) if total > 0 else 0

            # Fetch listing page
            self.status.emit(f"[{company}] Fetching listings page…")
            try:
                response = requests.get(
                    cfg["url"],
                    headers=cfg.get("headers", {}),
                    timeout=20
                )
                response.raise_for_status()
            except Exception as e:
                err = f"{company}: Failed to fetch listing page: {str(e)}"
                errors.append(err)
                self.log.emit(f" ✗ {err}")
                continue
            self.progress.emit(base_progress + int(company_progress_range * 0.15))

            soup = BeautifulSoup(response.text, "html.parser")
            try:
                job_list = listing_parser(soup)
            except Exception as e:
                err = f"{company}: Listing parser error: {str(e)}"
                errors.append(err)
                self.log.emit(f" ✗ {err}")
                continue

            num_jobs = len(job_list)
            if num_jobs == 0:
                self.log.emit(f" ⚠ No job postings found.")
                self.progress.emit(base_progress + company_progress_range)
                continue

            self.log.emit(f" Found {num_jobs} posting(s)")
            self.progress.emit(base_progress + int(company_progress_range * 0.25))

            # Fetch details
            detail_step = (company_progress_range * 0.60) / num_jobs if num_jobs else 0
            for i, (title, detail_url) in enumerate(job_list, 1):
                self.status.emit(f"[{company}] {i}/{num_jobs}: {title}")
                try:
                    detail_resp = requests.get(
                        detail_url,
                        headers=cfg.get("headers", {}),
                        timeout=30
                    )
                    detail_resp.raise_for_status()
                    detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

                    description = detail_parser(detail_soup)

                    if description.strip():
                        all_jobs.append((today_date, company, title, description.strip()))
                        self.log.emit(f" ✔ {title}")
                    else:
                        self.log.emit(f" ✗ No description: {title}")
                except Exception as e:
                    err = f"{company} ({title}): {str(e)}"
                    errors.append(err)
                    self.log.emit(f" ✗ {err}")

                self.progress.emit(base_progress + int(company_progress_range * 0.25 + i * detail_step))
                time.sleep(0.4)

            self.progress.emit(base_progress + company_progress_range)

        # Save to Excel
        if not all_jobs:
            self.finished.emit(True, "No jobs collected.", errors)
            return

        self.status.emit("Saving to Excel…")
        file_name = "Scrapify.xlsx"
        sheet_name = "Sheet1"

        try:
            wb = openpyxl.load_workbook(file_name)
        except FileNotFoundError:
            wb = Workbook()
            ws = wb.active
            ws.title = sheet_name
            ws.append(["Date", "Time", "Company", "Role", "Role description"])

        ws = wb[sheet_name]

        insert_step = 15 / len(all_jobs) if all_jobs else 0
        prog = 80

        for j, job in enumerate(reversed(all_jobs), 1):
            ws.insert_rows(2)
            try:
                ws.cell(row=2, column=1, value=job[0])  # Date
                ws.cell(row=2, column=2, value=datetime.now().strftime("%H:%M:%S"))  # Time
                ws.cell(row=2, column=3, value=job[1])  # Company
                ws.cell(row=2, column=4, value=job[2])  # Role
                ws.cell(row=2, column=5, value=job[3])  # Role description
            except IllegalCharacterError:
                cleaned = "".join(c for c in job[3] if c.isprintable())
                ws.cell(row=2, column=5, value=cleaned)
            prog += insert_step
            self.progress.emit(int(prog))

        wb.save(file_name)
        self.progress.emit(100)
        self.finished.emit(True, f"Added {len(all_jobs)} job(s) to {file_name}.", errors)


# ---------------------------------------------------------------------------
# GUI (unchanged)
# ---------------------------------------------------------------------------

class ScraperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scrapify — Job Scraper")
        self.setFixedSize(560, 520)
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
        parsers_folder = "parsers"
        available_companies = []
        if os.path.exists(parsers_folder):
            for file in os.listdir(parsers_folder):
                if file.endswith(".py") and file != "__init__.py":
                    name = file[:-3].replace("_", " ").title()
                    available_companies.append(name)
        self.company_combo.addItems(sorted(available_companies))
        for name in ["Hexagon AB", "Flink Robotics"]:
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
            companies = []
            parsers_folder = "parsers"
            if os.path.exists(parsers_folder):
                for file in os.listdir(parsers_folder):
                    if file.endswith(".py") and file != "__init__.py":
                        name = file[:-3].replace("_", " ").title()
                        companies.append(name)
            return sorted(companies)
        else:
            chosen = self.company_combo.currentText()
            if chosen.endswith("(no config)"):
                QMessageBox.warning(self, "Warning", "Selected company has no configuration.")
                return []
            return [chosen]

    def start_scraper(self):
        companies = self._get_selected_companies()
        if not companies:
            QMessageBox.warning(self, "No companies", "No configured companies found in parsers/ folder.")
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