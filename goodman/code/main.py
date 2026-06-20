from __future__ import annotations

import sys

from goodman_common_uc import ensure_dirs
from goodman_login_uc import main as login_main
from goodman_download_invoices_uc import main as download_main


def main() -> None:
    """
    Main orchestration function.

    Current workflow:
    - No cookie reuse
    - No Chrome profile reuse
    - Login happens fresh each run inside the downloader
    """
    print("=" * 70)
    print("HPS PRICING - GOODMAN INVOICE DOWNLOADER")
    print("=" * 70)

    print("\n[Step 1/2] Checking directories...")
    try:
        ensure_dirs()
        print("✓ All directories ready")
    except Exception as e:
        print(f"✗ Failed to create directories: {e}")
        raise

    print("\nChoose an option:")
    print("1. Test Goodman login only")
    print("2. Login and download Goodman invoices")

    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        print("\n[Step 2/2] Testing login...")
        login_main()

    elif choice == "2":
        print("\n[Step 2/2] Starting login + invoice download...")
        download_main()

    else:
        raise ValueError("Invalid choice. Enter 1 or 2.")

    print("\n" + "=" * 70)
    print("✓ WORKFLOW COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Workflow interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
