# HFI v1.1 Code Release

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
