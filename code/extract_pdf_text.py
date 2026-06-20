from __future__ import annotations

import csv
import sys
from pathlib import Path
from pypdf import PdfReader


def get_project_dir() -> Path:
    """
    This file should live at:

    hps_pricing/code/extract_pdf_text.py

    PROJECT_DIR becomes:

    hps_pricing
    """
    return Path(__file__).resolve().parents[1]


PROJECT_DIR = get_project_dir()


def find_project_folders() -> list[Path]:
    """
    Finds supplier/project folders inside hps_pricing.

    A valid project folder is one that has a downloads folder.

    Example:
    hps_pricing/goodman/downloads
    """
    project_folders = []

    for path in sorted(PROJECT_DIR.iterdir()):
        if not path.is_dir():
            continue

        if path.name.startswith("."):
            continue

        if path.name in {"code", "__pycache__", "data", "downloads"}:
            continue

        downloads_dir = path / "downloads"

        if downloads_dir.exists() and downloads_dir.is_dir():
            project_folders.append(path)

    return project_folders


def choose_project_with_dialog(project_folders: list[Path]) -> Path:
    """
    Opens a small dialog box asking which project to use.

    Falls back to a terminal prompt if tkinter is unavailable.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox

        selected_project: dict[str, Path | None] = {"path": None}

        root = tk.Tk()
        root.title("Choose PDF Project")
        root.geometry("420x320")
        root.resizable(False, False)

        label = tk.Label(
            root,
            text="Choose which supplier/project folder to extract PDFs from:",
            padx=12,
            pady=12,
        )
        label.pack()

        listbox = tk.Listbox(root, width=45, height=10)

        for folder in project_folders:
            listbox.insert(tk.END, folder.name)

        listbox.pack(padx=12, pady=8)

        if project_folders:
            listbox.selection_set(0)

        def confirm_selection() -> None:
            selection = listbox.curselection()

            if not selection:
                messagebox.showwarning("No project selected", "Please select a project.")
                return

            selected_project["path"] = project_folders[selection[0]]
            root.destroy()

        def cancel() -> None:
            root.destroy()

        button_frame = tk.Frame(root)
        button_frame.pack(pady=12)

        ok_button = tk.Button(button_frame, text="Use Selected Project", command=confirm_selection)
        ok_button.pack(side=tk.LEFT, padx=8)

        cancel_button = tk.Button(button_frame, text="Cancel", command=cancel)
        cancel_button.pack(side=tk.LEFT, padx=8)

        root.mainloop()

        if selected_project["path"] is None:
            print("No project selected. Exiting.")
            sys.exit(0)

        return selected_project["path"]

    except Exception:
        print("Could not open dialog box. Falling back to terminal selection.\n")
        return choose_project_in_terminal(project_folders)


def choose_project_in_terminal(project_folders: list[Path]) -> Path:
    print("Available projects:")

    for index, folder in enumerate(project_folders, start=1):
        print(f"{index}. {folder.name}")

    while True:
        choice = input("\nEnter project number: ").strip()

        try:
            index = int(choice)

            if 1 <= index <= len(project_folders):
                return project_folders[index - 1]

        except ValueError:
            pass

        print("Invalid choice. Try again.")


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from a digital PDF.

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
    Put the source filename at the top of each PDF's extracted text.
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


def extract_pdf_folder(project_folder: Path) -> None:
    project_name = project_folder.name

    pdf_dir = project_folder / "downloads"
    data_dir = project_folder / "data"

    data_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        raise RuntimeError(f"No PDF files found in: {pdf_dir}")

    combined_text_file = data_dir / f"{project_name}_all_pdf_text.txt"
    manifest_file = data_dir / f"{project_name}_pdf_text_manifest.csv"

    print(f"Project: {project_name}")
    print(f"PDF folder: {pdf_dir}")
    print(f"Data folder: {data_dir}")
    print(f"Found {len(pdf_files)} PDF files.")

    manifest_rows = []
    combined_blocks = []

    for index, pdf_path in enumerate(pdf_files, start=1):
        print(f"[{index}/{len(pdf_files)}] Extracting: {pdf_path.name}")

        extracted_text = extract_text_from_pdf(pdf_path)
        text_block = build_text_block(pdf_path, extracted_text)

        combined_blocks.append(text_block)

        manifest_rows.append(
            {
                "project": project_name,
                "pdf_file_name": pdf_path.name,
                "pdf_file_path": str(pdf_path),
                "characters_extracted": len(extracted_text),
                "status": "ok" if extracted_text else "no_text_extracted",
            }
        )

    combined_text_file.write_text(
        "\n\n".join(combined_blocks),
        encoding="utf-8",
    )

    with manifest_file.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "project",
            "pdf_file_name",
            "pdf_file_path",
            "characters_extracted",
            "status",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    print("\nDone.")
    print(f"Combined text file saved to: {combined_text_file}")
    print(f"Manifest saved to: {manifest_file}")


def main() -> None:
    project_folders = find_project_folders()

    if not project_folders:
        raise RuntimeError(
            "No project folders found. Expected folders like:\n"
            "hps_pricing/goodman/downloads"
        )

    selected_project = choose_project_with_dialog(project_folders)

    extract_pdf_folder(selected_project)


if __name__ == "__main__":
    main()
