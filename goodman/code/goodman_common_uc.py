from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By


LOGIN_URL = "https://secure.billtrust.com/DAIKINCOMFORT/ig/signin"
CLOSED_URL = "https://secure.billtrust.com/DAIKINCOMFORT/ig/closed"

START_DATE = "01/01/2019"
END_DATE = datetime.now().strftime("%m/%d/%Y")

# Your Chrome is currently 149, so force UC to use matching ChromeDriver.
# You can change this later if Chrome updates.
CHROME_VERSION_MAIN = int(os.getenv("CHROME_VERSION_MAIN", "149"))

CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def get_base_dir() -> Path:
    """
    For files stored in hps_pricing/goodman/code,
    BASE_DIR becomes hps_pricing/goodman.
    """
    return Path(__file__).resolve().parents[1]


BASE_DIR = get_base_dir()

DATA_DIR = BASE_DIR / "data"
DOWNLOAD_DIR = BASE_DIR / "downloads"
DEBUG_DIR = BASE_DIR / "debug"
METADATA_FILE = DATA_DIR / "goodman_invoices.csv"


def ensure_dirs() -> None:
    for path in [DATA_DIR, DOWNLOAD_DIR, DEBUG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def build_driver(
    *,
    download_dir: Optional[Path] = None,
    headless: bool = False,
) -> uc.Chrome:
    """
    Build a fresh Chrome driver every time.

    No cookie reuse.
    No saved Chrome profile reuse.
    Login happens every run.
    """
    ensure_dirs()

    if download_dir is None:
        download_dir = DOWNLOAD_DIR

    download_dir.mkdir(parents=True, exist_ok=True)

    options = uc.ChromeOptions()

    if Path(CHROME_BINARY).exists():
        options.binary_location = CHROME_BINARY

    options.add_argument("--start-maximized")
    options.add_argument("--disable-popup-blocking")

    if headless:
        options.add_argument("--headless=new")

    prefs = {
        "download.default_directory": str(download_dir.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    options.add_experimental_option("prefs", prefs)

    driver = uc.Chrome(
        options=options,
        use_subprocess=True,
        version_main=CHROME_VERSION_MAIN,
    )

    driver.set_page_load_timeout(90)

    try:
        driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {
                "behavior": "allow",
                "downloadPath": str(download_dir.resolve()),
            },
        )
    except Exception:
        pass

    return driver


def take_debug_screenshot(driver: uc.Chrome, name: str) -> Path:
    ensure_dirs()
    path = DEBUG_DIR / name
    driver.save_screenshot(str(path))
    print(f"Saved screenshot: {path}")
    return path


def wait_for_download_to_finish(
    download_dir: Path,
    before_files: set[Path],
    timeout: int = 60,
) -> Optional[Path]:
    start = time.time()

    while time.time() - start < timeout:
        current_files = set(download_dir.glob("*"))
        new_files = current_files - before_files

        finished = [
            p for p in new_files
            if p.is_file() and not p.name.endswith(".crdownload")
        ]

        if finished:
            return max(finished, key=lambda p: p.stat().st_mtime)

        time.sleep(0.5)

    return None
