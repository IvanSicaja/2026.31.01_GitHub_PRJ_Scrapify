import sys
import requests
from bs4 import BeautifulSoup
import openpyxl
from openpyxl import Workbook
from openpyxl.utils.exceptions import IllegalCharacterError
from datetime import date
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QLabel, QMessageBox, QProgressBar, QTextEdit
)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class Worker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    log = pyqtSignal(str)           # now only high-level job success/failure
    finished = pyqtSignal(bool, str)

    def run(self):
        try:
            url = "https://jobs.lever.co/rivr"
            company = "RIVR"
            today_date = date.today().strftime("%m/%d/%Y")

            self.status.emit("Fetching job listings page...")
            response = requests.get(url)
            response.raise_for_status()
            self.progress.emit(10)
            self.status.emit("Listings page fetched successfully")

            soup = BeautifulSoup(response.text, 'html.parser')
            postings = soup.find_all('div', class_='posting')
            num_jobs = len(postings)
            if num_jobs == 0:
                self.finished.emit(True, "No new jobs found.")
                return

            self.status.emit(f"Found {num_jobs} job postings")
            self.progress.emit(20)

            jobs = []
            job_progress_step = 60 / num_jobs if num_jobs > 0 else 0
            current_progress = 20

            for i, post in enumerate(postings, 1):
                title_elem = post.find('h5')
                if not title_elem:
                    continue
                title = title_elem.text.strip()

                link_elem = post.find('a', class_='posting-title')
                if not link_elem:
                    self.log.emit(f"✗ Skipped (no link): {title}")
                    continue
                job_url = link_elem['href']

                self.status.emit(f"Fetching details for job {i}/{num_jobs}: {title}")
                detail_response = requests.get(job_url)
                detail_response.raise_for_status()
                self.status.emit(f"Details fetched for job {i}/{num_jobs}")

                self.status.emit(f"Parsing description for job {i}/{num_jobs}")
                detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                description_sections = detail_soup.find_all('div', class_='section page-centered')
                description = ""
                for section in description_sections:
                    text = section.get_text(separator='\n', strip=True)
                    description += text + "\n\n"

                if description.strip():
                    jobs.append((today_date, company, title, description))
                    self.log.emit(f"✔ Scraped: {title}")
                else:
                    self.log.emit(f"✗ No description: {title}")

                current_progress += job_progress_step
                self.progress.emit(int(current_progress))
                self.status.emit(f"Processed job {i}/{num_jobs}")

            if not jobs:
                self.finished.emit(True, "No valid jobs found after parsing.")
                return

            self.status.emit("Preparing Excel file...")
            file_name = "Scrapify.xlsx"
            sheet_name = "Sheet1"
            try:
                wb = openpyxl.load_workbook(file_name)
            except FileNotFoundError:
                wb = Workbook()
                ws = wb.active
                ws.title = sheet_name
                ws.append(["Date", "Company", "Role", "Role description"])

            ws = wb[sheet_name]

            self.status.emit("Inserting new jobs into sheet...")
            insert_progress_step = 10 / len(jobs) if jobs else 0
            for j, job in enumerate(reversed(jobs), 1):
                ws.insert_rows(2)
                try:
                    ws.cell(row=2, column=1, value=job[0])
                    ws.cell(row=2, column=2, value=job[1])
                    ws.cell(row=2, column=3, value=job[2])
                    ws.cell(row=2, column=4, value=job[3])
                except IllegalCharacterError:
                    cleaned_desc = ''.join(c for c in job[3] if c.isprintable())
                    ws.cell(row=2, column=4, value=cleaned_desc)
                self.progress.emit(80 + int(j * insert_progress_step))

            self.status.emit("Saving Excel file...")
            wb.save(file_name)
            self.progress.emit(95)
            self.status.emit("File saved successfully")

            self.finished.emit(True, f"Added {len(jobs)} new jobs to {file_name}.")

        except Exception as e:
            self.finished.emit(False, f"An error occurred: {str(e)}")


class ScraperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scrapify — Job Scraper")
        self.setFixedSize(520, 440)

        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QLabel {
                color: #e0e0e0;
                font-size: 15px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }
            QProgressBar {
                height: 16px;
                border-radius: 8px;
                background: #2a2a2a;
                text-align: center;
                color: #aaa;
            }
            QProgressBar::chunk {
                background-color: #0a84ff;
                border-radius: 8px;
            }
            QTextEdit {
                background-color: #121212;
                color: #d0d0d0;
                border: none;
                border-radius: 10px;
                padding: 10px;
                font-family: SF Mono, Menlo, monospace;
                font-size: 13px;
            }
            QPushButton {
                background-color: #0a84ff;
                color: white;
                border: none;
                border-radius: 12px;
                padding: 12px;
                font-size: 15px;
                font-weight: 600;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }
            QPushButton:hover { background-color: #0070e0; }
            QPushButton:pressed { background-color: #0060c0; }
            QPushButton:disabled { background-color: #444; color: #888; }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        self.label = QLabel("Scrape jobs from https://jobs.lever.co/rivr")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.scrape_button.setFixedHeight(48)
        self.scrape_button.clicked.connect(self.start_scraper)
        layout.addWidget(self.scrape_button)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def start_scraper(self):
        self.scrape_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting...")
        self.log_text.clear()

        self.worker = Worker()
        self.worker.progress.connect(self.update_progress)
        self.worker.status.connect(self.update_status)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.scraper_finished)
        self.worker.start()

    def update_progress(self, value: int):
        self.progress_bar.setValue(value)

    def update_status(self, text: str):
        self.status_label.setText(text)

    def append_log(self, text: str):
        self.log_text.append(text)
        self.log_text.ensureCursorVisible()

    def scraper_finished(self, success: bool, message: str):
        self.progress_bar.setValue(100)
        self.scrape_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            QMessageBox.information(self, "Scrapify", message)
            self.status_label.setText("Done")
        else:
            QMessageBox.critical(self, "Error", message)
            self.status_label.setText("Failed")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScraperApp()
    window.show()
    sys.exit(app.exec())