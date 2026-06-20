from __future__ import annotations

import csv
import re
import time
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from goodman_common_uc import (
    CLOSED_URL,
    DATA_DIR,
    DEBUG_DIR,
    DOWNLOAD_DIR,
    END_DATE,
    METADATA_FILE,
    START_DATE,
    build_driver,
    is_logged_in,
    take_debug_screenshot,
    wait_for_download_to_finish,
)


def clean_filename(value: str) -> str:
    value = value or "unknown"
    value = re.sub(r"[^\w\-.]+", "_", value.strip())
    return value.strip("_") or "unknown"


def wait_for_closed_page(driver, timeout_seconds: int = 60) -> None:
    WebDriverWait(driver, timeout_seconds).until(
        lambda d: (
            d.find_elements(By.CSS_SELECTOR, ".headerDropdownFilter")
            or d.find_elements(By.CSS_SELECTOR, '[data-role="iginvoicetable"]')
            or d.find_elements(By.CSS_SELECTOR, ".grid-table-responsive")
        )
    )


def apply_bill_date_filter(driver) -> None:
    """
    Opens the Closed tab filter dropdown and applies:
    Bill Date from START_DATE through END_DATE.

    Based on the uploaded dropdown HTML:
    - popup container: #popupWindow
    - custom range radio: #ageRange_BillDate
    - from input: input[name='fromDisplay']
    - to input: input[name='toDisplay']
    - apply button: input[role='apply']
    """
    print(f"Applying Bill Date filter: {START_DATE} through {END_DATE}")

    driver.get(CLOSED_URL)
    wait_for_closed_page(driver)

    wait = WebDriverWait(driver, 60)

    dropdowns = wait.until(
        lambda d: d.find_elements(By.CSS_SELECTOR, ".headerDropdownFilter")
    )

    # Usually there is one dropdown per filterable header.
    # The BillDate dropdown is often the first date-style filter.
    dropdowns[0].click()

    wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "#popupWindow"))

    # Select custom range.
    age_range = wait.until(
        lambda d: d.find_element(By.CSS_SELECTOR, "#popupWindow #ageRange_BillDate")
    )
    driver.execute_script("arguments[0].click();", age_range)

    # Remove disabled attribute if Kendo leaves the fields disabled after selecting custom range.
    driver.execute_script(
        """
        document.querySelectorAll(
            "#popupWindow input[name='fromDisplay'], #popupWindow input[name='toDisplay']"
        ).forEach(el => el.removeAttribute("disabled"));
        """
    )

    from_input = wait.until(
        lambda d: d.find_element(By.CSS_SELECTOR, "#popupWindow input[name='fromDisplay']")
    )
    to_input = wait.until(
        lambda d: d.find_element(By.CSS_SELECTOR, "#popupWindow input[name='toDisplay']")
    )

    from_input.send_keys(Keys.COMMAND, "a")
    from_input.send_keys(START_DATE)

    to_input.send_keys(Keys.COMMAND, "a")
    to_input.send_keys(END_DATE)

    apply_button = wait.until(
        lambda d: d.find_element(By.CSS_SELECTOR, "#popupWindow input[role='apply']")
    )
    driver.execute_script("arguments[0].click();", apply_button)

    time.sleep(5)


def get_invoice_rows(driver):
    """
    The page uses a Kendo invoice grid. The uploaded HTML row template suggests
    each row has a data-id with DocumentId and an individual PDF icon.
    """
    wait = WebDriverWait(driver, 60)

    wait.until(
        lambda d: (
            d.find_elements(By.CSS_SELECTOR, "tr[data-id]")
            or d.find_elements(By.CSS_SELECTOR, ".view-pdf-download")
        )
    )

    rows = driver.find_elements(By.CSS_SELECTOR, "tr[data-id]")

    if not rows:
        # Fallback if Billtrust renders a different row structure.
        pdf_links = driver.find_elements(By.CSS_SELECTOR, ".view-pdf-download")
        rows = []
        for link in pdf_links:
            try:
                rows.append(link.find_element(By.XPATH, "./ancestor::tr[1]"))
            except Exception:
                pass

    return rows


def collect_visible_metadata(driver) -> list[dict]:
    rows = get_invoice_rows(driver)
    metadata = []

    for index, row in enumerate(rows, start=1):
        document_id = row.get_attribute("data-id") or ""
        row_text = row.text.strip()

        pdf_links = row.find_elements(By.CSS_SELECTOR, ".view-pdf-download")
        has_pdf = bool(pdf_links)

        pdf_url = ""
        encrypt_url = ""

        if has_pdf:
            pdf_url = pdf_links[0].get_attribute("data-pdf-url") or ""
            encrypt_url = pdf_links[0].get_attribute("data-url") or ""

        metadata.append(
            {
                "visible_row_number": index,
                "document_id": document_id,
                "row_text": row_text,
                "has_pdf": has_pdf,
                "pdf_url": pdf_url,
                "encrypt_url": encrypt_url,
            }
        )

    return metadata


def save_metadata_csv(rows: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "visible_row_number",
        "document_id",
        "row_text",
        "has_pdf",
        "pdf_url",
        "encrypt_url",
    ]

    with METADATA_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved invoice metadata to: {METADATA_FILE}")


def download_visible_invoice_pdfs(driver) -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    rows = get_invoice_rows(driver)
    print(f"Found {len(rows)} visible invoice rows.")

    for index, row in enumerate(rows, start=1):
        document_id = row.get_attribute("data-id") or f"row_{index}"
        document_id_clean = clean_filename(document_id)

        links = row.find_elements(By.CSS_SELECTOR, ".view-pdf-download")
        if not links:
            print(f"Skipping row {index}: no PDF icon found.")
            continue

        before_files = set(DOWNLOAD_DIR.glob("*"))

        print(f"Clicking PDF for row {index}, document_id={document_id_clean}")
        driver.execute_script("arguments[0].click();", links[0])

        downloaded_file = wait_for_download_to_finish(
            DOWNLOAD_DIR,
            before_files,
            timeout=60,
        )

        if downloaded_file is None:
            print(f"Download not detected for row {index}. Saving screenshot.")
            take_debug_screenshot(driver, f"download_failed_{document_id_clean}.png")
            continue

        target_path = DOWNLOAD_DIR / f"goodman_{document_id_clean}.pdf"

        # If Chrome gives us a weird extension/name, rename to our standard name.
        try:
            if target_path.exists():
                target_path.unlink()
            downloaded_file.rename(target_path)
            print(f"Saved: {target_path}")
        except Exception:
            print(f"Downloaded but could not rename: {downloaded_file}")

        time.sleep(1)


def main() -> None:
    driver = build_driver(headless=False)

    try:
        driver.get(CLOSED_URL)

        if not is_logged_in(driver):
            raise RuntimeError(
                "Not logged in. Run this first:\n"
                "python code/goodman_login_uc.py"
            )

        apply_bill_date_filter(driver)

        metadata = collect_visible_metadata(driver)
        save_metadata_csv(metadata)

        download_visible_invoice_pdfs(driver)

        print("\nDone.")

    except Exception:
        take_debug_screenshot(driver, "goodman_download_error.png")
        raise

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
