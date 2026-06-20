from __future__ import annotations

import csv
import re
import time

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from goodman_common_uc import (
    CLOSED_URL,
    DATA_DIR,
    DOWNLOAD_DIR,
    METADATA_FILE,
    build_driver,
    take_debug_screenshot,
    wait_for_download_to_finish,
)

from goodman_login_uc import perform_login


def clean_filename(value: str) -> str:
    value = value or "unknown"
    value = re.sub(r"[^\w\-.]+", "_", value.strip())
    return value.strip("_") or "unknown"


def wait_for_closed_page(driver, timeout_seconds: int = 60) -> None:
    wait = WebDriverWait(driver, timeout_seconds)

    wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, '[data-role="iginvoicetable"]')
        )
    )

    wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".grid-table-responsive")
        )
    )


def manual_date_filter_pause(driver) -> None:
    print(f"Opening Closed invoices page: {CLOSED_URL}")

    driver.get(CLOSED_URL)
    wait_for_closed_page(driver)

    print("\nManual step:")
    print("1. Open the date dropdown in Chrome.")
    print("2. Select the From/range option.")
    print("3. Enter the date range manually.")
    print("4. Click Apply.")
    print("5. Wait until the invoice table reloads.")
    input("\nAfter the filtered invoice table loads, press Enter here to continue... ")

    time.sleep(3)


def get_cell_text(row, selector: str) -> str:
    try:
        return row.find_element(By.CSS_SELECTOR, selector).text.strip()
    except Exception:
        return ""


def get_document_type(row) -> str:
    return get_cell_text(row, "td.i-cell-itemtype .display-filed")


def get_invoice_number(row) -> str:
    return get_cell_text(row, "td.i-cell-invoicenumber .display-filed")


def get_invoice_date(row) -> str:
    return get_cell_text(row, "td.i-cell-billdate .display-filed")


def get_invoice_amount(row) -> str:
    return get_cell_text(row, "td.i-cell-totaldue .display-filed")


def get_po_number(row) -> str:
    return get_cell_text(row, "td.i-cell-ponumber .display-filed")


def get_rendered_rows(driver) -> list:
    """
    Gets rows currently rendered in the table.
    With a virtualized grid, this is not the full result set.
    """
    return driver.find_elements(By.CSS_SELECTOR, "tr[data-id]")


def get_document_id(row, fallback: str = "") -> str:
    try:
        return (row.get_attribute("data-id") or fallback).strip()
    except Exception:
        return fallback


def row_has_pdf(row) -> bool:
    try:
        return bool(row.find_elements(By.CSS_SELECTOR, ".view-pdf-download"))
    except Exception:
        return False


def row_is_invoice_with_pdf(row) -> bool:
    return get_document_type(row) == "I" and row_has_pdf(row)


def row_to_metadata(row, downloaded_path: str = "") -> dict:
    document_id = get_document_id(row)

    pdf_links = row.find_elements(By.CSS_SELECTOR, ".view-pdf-download")
    has_pdf = bool(pdf_links)

    pdf_url = ""
    encrypt_url = ""

    if has_pdf:
        pdf_url = pdf_links[0].get_attribute("data-pdf-url") or ""
        encrypt_url = pdf_links[0].get_attribute("data-url") or ""

    return {
        "document_id": document_id,
        "document_type": get_document_type(row),
        "invoice_number": get_invoice_number(row),
        "invoice_date": get_invoice_date(row),
        "invoice_amount": get_invoice_amount(row),
        "po_number": get_po_number(row),
        "has_pdf": has_pdf,
        "pdf_url": pdf_url,
        "encrypt_url": encrypt_url,
        "downloaded_path": downloaded_path,
        "row_text": row.text.strip(),
    }


def build_pdf_filename(row) -> str:
    document_id = clean_filename(get_document_id(row))
    invoice_number = clean_filename(get_invoice_number(row))
    invoice_date = clean_filename(get_invoice_date(row))

    if invoice_number and invoice_number != "unknown":
        stem = f"goodman_invoice_{invoice_number}"
    else:
        stem = f"goodman_{document_id}"

    if invoice_date and invoice_date != "unknown":
        stem = f"{stem}_{invoice_date}"

    return f"{stem}.pdf"


def click_pdf_link(row) -> bool:
    """
    Clicks the PDF icon using Selenium.
    """
    try:
        links = row.find_elements(By.CSS_SELECTOR, ".view-pdf-download")

        if not links:
            return False

        link = links[0]
        link.location_once_scrolled_into_view
        time.sleep(0.3)
        link.click()
        return True

    except ElementClickInterceptedException:
        try:
            ActionChains(row.parent).move_to_element(row).pause(0.2).perform()
            links = row.find_elements(By.CSS_SELECTOR, ".view-pdf-download")
            links[0].click()
            return True
        except Exception:
            return False

    except Exception:
        return False


def download_row_pdf(driver, row) -> dict | None:
    document_id = get_document_id(row)

    if not document_id:
        return None

    metadata = row_to_metadata(row)

    filename = build_pdf_filename(row)
    target_path = DOWNLOAD_DIR / filename

    before_files = set(DOWNLOAD_DIR.glob("*"))

    print(f"Downloading document_id={document_id}")

    clicked = click_pdf_link(row)

    if not clicked:
        print(f"Could not click PDF for document_id={document_id}")
        take_debug_screenshot(driver, f"click_failed_{clean_filename(document_id)}.png")
        return metadata

    downloaded_file = wait_for_download_to_finish(
        DOWNLOAD_DIR,
        before_files,
        timeout=60,
    )

    if downloaded_file is None:
        print(f"Download not detected for document_id={document_id}")
        take_debug_screenshot(driver, f"download_failed_{clean_filename(document_id)}.png")
        return metadata

    try:
        if target_path.exists():
            target_path.unlink()

        downloaded_file.rename(target_path)
        metadata["downloaded_path"] = str(target_path)
        print(f"Saved: {target_path}")

    except Exception:
        print(f"Downloaded but could not rename: {downloaded_file}")

    time.sleep(1)
    return metadata


def get_rendered_document_ids(driver) -> list[str]:
    ids = []

    for row in get_rendered_rows(driver):
        document_id = get_document_id(row)

        if document_id:
            ids.append(document_id)

    return ids


def scroll_down_until_middle_row_changes(driver, middle_document_id: str) -> bool:
    """
    Scrolls down until the previous halfway row is no longer in the rendered row set.

    Returns True if the rendered row set changed.
    Returns False if scrolling did not move us to a new rendered table section.
    """
    print(f"Scrolling until halfway row is gone: {middle_document_id}")

    previous_ids = get_rendered_document_ids(driver)

    for attempt in range(20):
        rows = get_rendered_rows(driver)

        if not rows:
            return False

        try:
            origin_row = rows[min(len(rows) - 1, max(0, len(rows) // 2))]
            origin = ScrollOrigin.from_element(origin_row)

            ActionChains(driver).scroll_from_origin(origin, 0, 700).perform()

        except Exception:
            ActionChains(driver).scroll_by_amount(0, 700).perform()

        time.sleep(1)

        current_ids = get_rendered_document_ids(driver)

        if middle_document_id not in current_ids:
            print("Halfway row is no longer rendered.")
            return True

        if current_ids != previous_ids:
            previous_ids = current_ids

    print("Could not move past the halfway row after several scroll attempts.")
    return False


def process_current_rendered_table(driver, seen_document_ids: set[str]) -> tuple[list[dict], int]:
    """
    Downloads all new currently-rendered invoice PDFs.

    Returns:
    - metadata rows collected
    - count of new downloadable invoice PDFs found
    """
    metadata_rows = []
    rows = get_rendered_rows(driver)

    print(f"Rendered rows visible now: {len(rows)}")

    document_type_counts = {}
    new_downloadable_count = 0

    for row_index in range(len(rows)):
        try:
            rows = get_rendered_rows(driver)

            if row_index >= len(rows):
                continue

            row = rows[row_index]
            document_id = get_document_id(row, fallback=f"row_{row_index + 1}")

            document_type = get_document_type(row)
            document_type_counts[document_type] = document_type_counts.get(document_type, 0) + 1

            if document_id in seen_document_ids:
                continue

            if not row_is_invoice_with_pdf(row):
                continue

            new_downloadable_count += 1
            seen_document_ids.add(document_id)

            metadata = download_row_pdf(driver, row)

            if metadata is not None:
                metadata_rows.append(metadata)

        except StaleElementReferenceException:
            print(f"Skipping row {row_index + 1}: stale row.")
            continue

    print(f"Document type counts in rendered table: {document_type_counts}")
    print(f"New downloadable invoice PDFs in this view: {new_downloadable_count}")

    return metadata_rows, new_downloadable_count


def save_metadata_csv(rows: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "document_id",
        "document_type",
        "invoice_number",
        "invoice_date",
        "invoice_amount",
        "po_number",
        "has_pdf",
        "pdf_url",
        "encrypt_url",
        "downloaded_path",
        "row_text",
    ]

    with METADATA_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved invoice metadata to: {METADATA_FILE}")


def process_virtual_table_by_scrolling(driver) -> list[dict]:
    """
    Main virtual-table loop.

    Process current rendered rows, then scroll until the halfway row disappears.
    Stop when an entire rendered table view has no new downloadable invoice PDFs.
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    all_metadata = []
    seen_document_ids = set()
    loop_number = 1

    while True:
        print("\n" + "=" * 70)
        print(f"SCROLL LOOP {loop_number}")
        print("=" * 70)

        rows = get_rendered_rows(driver)

        if not rows:
            print("No rendered rows found. Stopping.")
            break

        middle_row = rows[len(rows) // 2]
        middle_document_id = get_document_id(middle_row)

        metadata_rows, new_downloadable_count = process_current_rendered_table(
            driver,
            seen_document_ids,
        )

        all_metadata.extend(metadata_rows)

        if new_downloadable_count == 0:
            print("This entire rendered table view had no new downloadable invoice PDFs.")
            print("Stopping.")
            break

        if not middle_document_id:
            print("Could not identify halfway row. Stopping.")
            break

        moved = scroll_down_until_middle_row_changes(driver, middle_document_id)

        if not moved:
            print("Could not scroll to a new rendered table section. Stopping.")
            break

        loop_number += 1

    return all_metadata


def main() -> None:
    driver = build_driver(headless=False)

    try:
        perform_login(driver)

        manual_date_filter_pause(driver)

        metadata = process_virtual_table_by_scrolling(driver)

        save_metadata_csv(metadata)

        print("\nDone.")

    except Exception:
        take_debug_screenshot(driver, "goodman_download_error.png")
        raise

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
