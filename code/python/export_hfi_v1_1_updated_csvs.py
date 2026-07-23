from __future__ import annotations

import csv
import os
import shutil
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "hfi_v1_1_updated_csv_files"
SITE = ROOT / "outputs" / "hfi-explorer-v1-1-33-hospitals"
PRISTINE = ROOT / "outputs" / "hfi_pristine_rebuild_v1_1" / "data"


FILES = [
    (
        SITE / "data" / "hfi_hospitals.csv",
        OUT / "hfi_v1_1_nyc_cms_acute_hospital_universe_33.csv",
        "Full NYC CMS-listed acute-care hospital universe used by the Explorer; includes HCAHPS validation flag and linked tract HFI context.",
    ),
    (
        PRISTINE / "nyc_hcahps_validation_analysis_file_corrected_hfi_v1_1.csv",
        OUT / "hfi_v1_1_nyc_hcahps_validation_hospitals_32.csv",
        "HCAHPS-complete hospital validation analysis file; restricted to the 32 hospitals with required HCAHPS linear communication/experience outcomes.",
    ),
    (
        SITE / "data" / "hfi_tract_data.csv",
        OUT / "hfi_v1_1_nyc_tract_surface_2229.csv",
        "Corrected tract-level HFI surface used by the Explorer; one row per NYC census tract.",
    ),
    (
        PRISTINE / "nyc_acute_care_hospital_universe_33.csv",
        OUT / "hfi_v1_1_nyc_hospital_universe_33_full_analysis_columns.csv",
        "Full 33-hospital universe with broader analysis columns preserved from the manuscript rebuild.",
    ),
]


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_manifest(rows: list[dict[str, str]]) -> None:
    fields = ["file", "rows", "description", "notes"]
    with (OUT / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_inclusion_audit(hospitals: list[dict[str, str]]) -> None:
    fields = [
        "facility_id",
        "facility_name",
        "hospital_system",
        "borough",
        "included_in_hcahps_validation",
        "hcahps_exclusion_reason",
        "GEOID",
        "fragmentation_index",
        "communication_index",
        "patient_experience_index",
    ]
    with (OUT / "hfi_v1_1_hospital_inclusion_audit_33.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(hospitals)


def write_system_summary(hospitals: list[dict[str, str]]) -> None:
    summary: dict[tuple[str, str], dict[str, object]] = {}
    for row in hospitals:
        key = (row.get("hospital_system", "Unclassified"), row.get("borough", ""))
        item = summary.setdefault(
            key,
            {
                "hospital_system": key[0],
                "borough": key[1],
                "cms_acute_hospitals": 0,
                "hcahps_complete_hospitals": 0,
            },
        )
        item["cms_acute_hospitals"] = int(item["cms_acute_hospitals"]) + 1
        if row.get("included_in_hcahps_validation") == "Yes":
            item["hcahps_complete_hospitals"] = int(item["hcahps_complete_hospitals"]) + 1

    fields = ["hospital_system", "borough", "cms_acute_hospitals", "hcahps_complete_hospitals"]
    rows = sorted(summary.values(), key=lambda r: (str(r["hospital_system"]), str(r["borough"])))
    with (OUT / "hfi_v1_1_hospital_system_summary_by_borough.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for src, dst, description in FILES:
        shutil.copy2(src, dst)
        _, rows = read_rows(dst)
        manifest.append(
            {
                "file": dst.name,
                "rows": str(len(rows)),
                "description": description,
                "notes": "",
            }
        )

    _, hospitals = read_rows(OUT / "hfi_v1_1_nyc_cms_acute_hospital_universe_33.csv")
    write_inclusion_audit(hospitals)
    write_system_summary(hospitals)

    for extra in [
        (
            "hfi_v1_1_hospital_inclusion_audit_33.csv",
            "33",
            "Compact inclusion audit for colleague review; shows which hospitals are in the HCAHPS validation sample and why any hospital is not included.",
        ),
        (
            "hfi_v1_1_hospital_system_summary_by_borough.csv",
            "33 grouped",
            "Hospital-system summary by borough, derived from the 33-hospital universe.",
        ),
    ]:
        manifest.append({"file": extra[0], "rows": extra[1], "description": extra[2], "notes": ""})

    write_manifest(manifest)
    now = time.time()
    for path in OUT.rglob("*"):
        os.utime(path, (now, now))
    os.utime(OUT, (now, now))
    archive = shutil.make_archive(str(OUT), "zip", OUT)
    os.utime(archive, (now, now))
    print(OUT)
    print(archive)


if __name__ == "__main__":
    main()
