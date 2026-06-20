from __future__ import annotations

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from goodman_common_uc import (
    CLOSED_URL,
    LOGIN_URL,
    PROFILE_DIR,
    build_driver,
    is_logged_in,
    save_cookies,
    take_debug_screenshot,
)


def wait_for_manual_login(driver, timeout_seconds: int = 600) -> None:
    print("\nBrowser opened.")
    print("Log in manually in the Goodman / Daikin Billtrust portal.")
    print("Do not close the browser yet.")
    print("The script will detect when you are logged in.")

    wait = WebDriverWait(driver, timeout_seconds)
    wait.until(lambda d: is_logged_in(d))

    print("\nLogin detected.")


def main() -> None:
    driver = build_driver(headless=False)

    try:
        driver.get(LOGIN_URL)
        time.sleep(2)

        if not is_logged_in(driver):
            wait_for_manual_login(driver)

        save_cookies(driver)

        print("\nTesting access to Closed invoices page...")
        driver.get(CLOSED_URL)

        WebDriverWait(driver, 60).until(
            lambda d: (
                d.find_elements(By.CSS_SELECTOR, ".headerDropdownFilter")
                or d.find_elements(By.CSS_SELECTOR, '[data-role="iginvoicetable"]')
                or d.find_elements(By.CSS_SELECTOR, 'a[href*="/ig/signout"]')
            )
        )

        print("Closed page loaded successfully.")
        print(f"Chrome profile saved at: {PROFILE_DIR}")
        print("\nYou can now reuse this login session in the invoice downloader.")

        input("\nPress Enter to close the browser... ")

    except Exception:
        take_debug_screenshot(driver, "goodman_login_error.png")
        raise

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
