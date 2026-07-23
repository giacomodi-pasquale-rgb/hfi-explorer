from __future__ import annotations

import csv
import os
import shutil
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "outputs" / "hfi-explorer-v1-1-33-hospitals"
CODE_DIR = SITE / "code"
STANDALONE = ROOT / "outputs" / "hfi_v1_1_code_release"


CODE_FILES = [
    (
        ROOT / "outputs" / "hfi_pristine_rebuild_v1_1" / "stata" / "run_hcahps_validation_analysis.do",
        "stata/run_hcahps_validation_analysis.do",
        "Stata do-file for HCAHPS validation models and Word-ready validation tables.",
    ),
    (
        ROOT / "outputs" / "hospital_rebuild_2026_07_22" / "run_hcahps_validation_analysis.do",
        "stata/archive_initial_hospital_rebuild_validation.do",
        "Earlier Stata validation do-file retained for audit trail.",
    ),
    (
        ROOT / "outputs" / "hfi_surface_rebuild_2026_07_22" / "rebuild_hfi_surface.py",
        "python/rebuild_hfi_surface.py",
        "Rebuilds the corrected tract-level HFI surface with the CMS acute-care hospital provider layer enforced.",
    ),
    (
        ROOT / "outputs" / "hospital_rebuild_2026_07_22" / "rebuild_nyc_hospital_analysis.py",
        "python/rebuild_nyc_hospital_analysis.py",
        "Builds the NYC CMS acute-care hospital universe and links hospital records to HCAHPS fields.",
    ),
    (
        ROOT / "outputs" / "hfi_surface_rebuild_2026_07_22" / "make_corrected_hfi_word_ready_tables.py",
        "python/make_corrected_hfi_word_ready_tables.py",
        "Creates Word-ready tables from the corrected HFI/HCAHPS analysis files.",
    ),
    (
        ROOT / "outputs" / "hfi_pristine_rebuild_v1_1" / "build_full_submission_manuscript.py",
        "python/build_full_submission_manuscript.py",
        "Generates the full submission manuscript document from the rebuilt results and figures.",
    ),
    (
        ROOT / "scripts" / "build_hfi_explorer_v1_1_site.py",
        "python/build_hfi_explorer_v1_1_site.py",
        "Builds the GitHub Pages-ready HFI Explorer package with the corrected 33-hospital layer.",
    ),
    (
        ROOT / "scripts" / "export_hfi_v1_1_updated_csvs.py",
        "python/export_hfi_v1_1_updated_csvs.py",
        "Exports the clean standalone CSV packet for colleague review and public download.",
    ),
    (
        ROOT / "scripts" / "build_hfi_v1_1_code_release.py",
        "python/build_hfi_v1_1_code_release.py",
        "Builds this curated public code release package.",
    ),
]


README = """# HFI v1.1 Code Release

This package contains the curated reproducibility code for the HFI NYC analytic release.

## What is included

- `stata/run_hcahps_validation_analysis.do`: Stata code for the hospital-level HCAHPS validation models.
- `python/rebuild_nyc_hospital_analysis.py`: hospital universe and HCAHPS linkage workflow.
- `python/rebuild_hfi_surface.py`: corrected tract-level HFI surface rebuild.
- `python/make_corrected_hfi_word_ready_tables.py`: table export workflow.
- `python/build_full_submission_manuscript.py`: manuscript generation workflow.
- `python/build_hfi_explorer_v1_1_site.py`: public Explorer website export.
- `python/export_hfi_v1_1_updated_csvs.py`: standalone CSV export.

## Recommended use

For readers who want the public-facing outputs, use the data downloads on the HFI Explorer website. For replication or audit, start with the Stata validation do-file and the Python rebuild scripts. The scripts assume the corresponding public source datasets and derived CSV files are organized as described in the manuscript and data release.

## Release scope

This is a curated code release rather than a full private working directory. It excludes intermediate scratch files, rendered manuscript drafts, and local system artifacts.
"""


def copy_code_files(target: Path) -> list[dict[str, str]]:
    rows = []
    for src, rel, description in CODE_FILES:
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        rows.append({"file": rel, "description": description})
    return rows


def write_manifest(target: Path, rows: list[dict[str, str]]) -> None:
    with (target / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "description"])
        writer.writeheader()
        writer.writerows(rows)


def stamp(target: Path) -> None:
    now = time.time()
    for path in target.rglob("*"):
        os.utime(path, (now, now))
    os.utime(target, (now, now))


def build(target: Path) -> str:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    rows = copy_code_files(target)
    write_manifest(target, rows)
    (target / "README.md").write_text(README, encoding="utf-8")
    stamp(target)
    archive = shutil.make_archive(str(target), "zip", target)
    os.utime(archive, (time.time(), time.time()))
    return archive


def main() -> None:
    site_archive = build(CODE_DIR)
    standalone_archive = build(STANDALONE)
    print(CODE_DIR)
    print(site_archive)
    print(STANDALONE)
    print(standalone_archive)


if __name__ == "__main__":
    main()
