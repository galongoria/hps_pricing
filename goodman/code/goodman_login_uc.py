from __future__ import annotations

import os
import random
import time

from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from goodman_common_uc import (
    BASE_DIR,
    CLOSED_URL,
    LOGIN_URL,
    build_driver,
    take_debug_screenshot,
)


PRESS_ENTER_AFTER_USERNAME = True


def random_typing_delay() -> float:
    """
    Random delay between keystrokes.
    Clipped between 1.0 and 2.3 seconds.
    """
    delay = random.normalvariate(mu=1.65, sigma=0.35)
    return max(0.2, min(0.9, delay))


def slow_type(element, text: str) -> None:
    for char in text:
        element.send_keys(char)
        time.sleep(random_typing_delay())


def login_completed(driver) -> bool:
    """
    Detects that the fresh login succeeded.

    This is not checking/reusing old cookies.
    It only checks whether the current login attempt has reached
    a logged-in Billtrust page.
    """
    current_url = driver.current_url.lower()

    if "/ig/signin" in current_url:
        return False

    closed_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/ig/closed"]')
    signout_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/ig/signout"]')
    invoice_grid = driver.find_elements(
        By.CSS_SELECTOR,
        '[data-role="iginvoicetable"], .grid-table-responsive',
    )

    return bool(
        closed_links
        or signout_links
        or invoice_grid
        or "/ig/summary" in current_url
        or "/ig/home" in current_url
    )


def wait_for_logged_in_or_manual_verification(driver, timeout_seconds: int = 600) -> None:
    print("\nIf CAPTCHA, MFA, or extra verification appears, complete it manually.")
    print("The script will wait until the portal is logged in.")

    wait = WebDriverWait(driver, timeout_seconds)
    wait.until(lambda d: login_completed(d))

    print("Login detected.")


def perform_login(driver) -> None:
    """
    Logs into Goodman / Daikin Billtrust every time.

    Requires:
    GOODMAN_USER=...
    GOODMAN_PASS=...
    in hps_pricing/goodman/.env
    """
    load_dotenv(BASE_DIR / ".env")

    username = os.getenv("GOODMAN_USER")
    password = os.getenv("GOODMAN_PASS")

    if not username or not password:
        raise RuntimeError(
            f"Missing GOODMAN_USER or GOODMAN_PASS in {BASE_DIR / '.env'}"
        )

    driver.get(LOGIN_URL)
    time.sleep(2)

    wait = WebDriverWait(driver, 60)

    username_input = wait.until(
        lambda d: d.find_element(By.CSS_SELECTOR, "#EUserName")
    )
    password_input = wait.until(
        lambda d: d.find_element(By.CSS_SELECTOR, "#EPassword")
    )

    username_input.clear()
    password_input.clear()

    print("Typing username...")
    username_input.click()
    slow_type(username_input, username)

    if PRESS_ENTER_AFTER_USERNAME:
        username_input.send_keys(Keys.ENTER)
    else:
        username_input.send_keys(Keys.TAB)

    time.sleep(random_typing_delay())

    print("Typing password...")
    password_input.click()
    slow_type(password_input, password)

    password_input.send_keys(Keys.ENTER)

    wait_for_logged_in_or_manual_verification(driver)


def main() -> None:
    driver = build_driver(headless=False)

    try:
        perform_login(driver)

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
        input("\nPress Enter to close the browser... ")

    except Exception:
        take_debug_screenshot(driver, "goodman_login_error.png")
        raise

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
