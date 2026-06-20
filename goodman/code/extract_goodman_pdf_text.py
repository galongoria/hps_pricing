from __future__ import annotations

import csv
from pathlib import Path

from pypdf import PdfReader


def get_base_dir() -> Path:
    """
    For files stored in:
    hps_pricing/goodman/code/extract_goodman_pdf_text.py

    BASE_DIR becomes:
    hps_pricing/goodman
    """
    return Path(__file__).resolve().parents[1]


BASE_DIR = get_base_dir()

# Tries your project download folder first.
# Also checks a capitalized Goodman folder just in case.
PDF_DIR_CANDIDATES = [
    BASE_DIR / "downloads" / "goodman",
    BASE_DIR / "downloads" / "Goodman",
    Path.home() / "Downloads" / "Goodman",
    Path.home() / "Downloads" / "goodman",
]

DATA_DIR = BASE_DIR / "data"
TEXT_DIR = DATA_DIR / "goodman_pdf_text"

COMBINED_TEXT_FILE = DATA_DIR / "goodman_all_pdf_text.txt"
MANIFEST_FILE = DATA_DIR / "goodman_pdf_text_manifest.csv"


def find_pdf_dir() -> Path:
    for path in PDF_DIR_CANDIDATES:
        if path.exists() and path.is_dir():
            return path

    checked = "\n".join(str(path) for path in PDF_DIR_CANDIDATES)

    raise FileNotFoundError(
        "Could not find Goodman PDF folder. Checked:\n"
        f"{checked}"
    )


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extracts text from a digital PDF.

    If a PDF is scanned/image-only, this may return little or no text.
    """
    reader = PdfReader(str(pdf_path))

    pages_text = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception as e:
            page_text = f"[ERROR extracting page {page_number}: {e}]"

        pages_text.append(
            "\n".join(
                [
                    f"--- PAGE {page_number} ---",
                    page_text.strip(),
                ]
            )
        )

    return "\n\n".join(pages_text).strip()


def build_text_block(pdf_path: Path, extracted_text: str) -> str:
    """
    Puts the source filename at the top of each extraction.
    """
    return "\n".join(
        [
            "=" * 100,
            f"FILE NAME: {pdf_path.name}",
            f"FILE PATH: {pdf_path}",
            "=" * 100,
            "",
            extracted_text if extracted_text else "[NO TEXT EXTRACTED]",
            "",
        ]
    )


def main() -> None:
    pdf_dir = find_pdf_dir()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        raise RuntimeError(f"No PDF files found in: {pdf_dir}")

    print(f"PDF folder: {pdf_dir}")
    print(f"Found {len(pdf_files)} PDF files.")

    manifest_rows = []
    combined_blocks = []

    for index, pdf_path in enumerate(pdf_files, start=1):
        print(f"[{index}/{len(pdf_files)}] Extracting: {pdf_path.name}")

        extracted_text = extract_text_from_pdf(pdf_path)
        text_block = build_text_block(pdf_path, extracted_text)

        output_txt_path = TEXT_DIR / f"{pdf_path.stem}.txt"
        output_txt_path.write_text(text_block, encoding="utf-8")

        combined_blocks.append(text_block)

        manifest_rows.append(
            {
                "pdf_file_name": pdf_path.name,
                "pdf_file_path": str(pdf_path),
                "txt_file_name": output_txt_path.name,
                "txt_file_path": str(output_txt_path),
                "characters_extracted": len(extracted_text),
                "status": "ok" if extracted_text else "no_text_extracted",
            }
        )

    COMBINED_TEXT_FILE.write_text(
        "\n\n".join(combined_blocks),
        encoding="utf-8",
    )

    with MANIFEST_FILE.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "pdf_file_name",
            "pdf_file_path",
            "txt_file_name",
            "txt_file_path",
            "characters_extracted",
            "status",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    print("\nDone.")
    print(f"Individual text files saved to: {TEXT_DIR}")
    print(f"Combined text file saved to: {COMBINED_TEXT_FILE}")
    print(f"Manifest saved to: {MANIFEST_FILE}")


if __name__ == "__main__":
    main()
