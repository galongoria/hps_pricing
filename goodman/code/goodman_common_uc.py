from __future__ import annotations

import json
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


def get_base_dir() -> Path:
    """
    For files stored in hps_pricing/goodman/code, BASE_DIR becomes hps_pricing/goodman.
    """
    return Path(__file__).resolve().parents[1]


BASE_DIR = get_base_dir()

AUTH_DIR = BASE_DIR / "auth"
DATA_DIR = BASE_DIR / "data"
DOWNLOAD_DIR = BASE_DIR / "downloads" / "goodman"
DEBUG_DIR = BASE_DIR / "debug"

PROFILE_DIR = AUTH_DIR / "chrome_profile_goodman"
COOKIES_FILE = AUTH_DIR / "goodman_cookies.json"
METADATA_FILE = DATA_DIR / "goodman_invoices.csv"


def ensure_dirs() -> None:
    for path in [AUTH_DIR, DATA_DIR, DOWNLOAD_DIR, DEBUG_DIR, PROFILE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def build_driver(
    *,
    download_dir: Optional[Path] = None,
    headless: bool = False,
) -> uc.Chrome:
    """
    Build Chrome with a persistent local profile.

    This does not automate CAPTCHA or MFA.
    This does not store your username/password.
    It reuses the local Chrome profile saved in auth/chrome_profile_goodman.
    """
    ensure_dirs()

    if download_dir is None:
        download_dir = DOWNLOAD_DIR

    download_dir.mkdir(parents=True, exist_ok=True)

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
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

    driver = uc.Chrome(options=options, use_subprocess=True)
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


def save_cookies(driver: uc.Chrome) -> None:
    ensure_dirs()
    cookies = driver.get_cookies()

    with COOKIES_FILE.open("w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)

    print(f"Saved cookies to: {COOKIES_FILE}")


def is_logged_in(driver: uc.Chrome) -> bool:
    current_url = driver.current_url.lower()

    if "/ig/signin" in current_url:
        return False

    closed_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/ig/closed"]')
    signout_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/ig/signout"]')
    invoice_grid = driver.find_elements(By.CSS_SELECTOR, '[data-role="iginvoicetable"], .grid-table-responsive')

    return bool(closed_links or signout_links or invoice_grid or "/ig/summary" in current_url)


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
    """
    Watch a folder for a new completed download.
    Chrome temporary downloads usually end with .crdownload.
    """
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
