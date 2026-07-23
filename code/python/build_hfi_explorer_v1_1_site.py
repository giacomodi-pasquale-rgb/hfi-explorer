from __future__ import annotations

import csv
import json
import os
import re
import shutil
import time
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SITE = ROOT / "work" / "hfi-explorer-site-updated-v2"
OUT_SITE = ROOT / "outputs" / "hfi-explorer-v1-1-33-hospitals"
TRACT_SURFACE = ROOT / "outputs" / "hfi_pristine_rebuild_v1_1" / "data" / "hfi_tract_surface_v1_1_corrected.csv"
HOSPITAL_UNIVERSE = ROOT / "outputs" / "hospital_rebuild_2026_07_22" / "derived" / "nyc_acute_care_hospital_universe_33.csv"
OLD_TRACT_DATA = SOURCE_SITE / "data" / "hfi_tract_data.csv"
OLD_TRACT_GEOJSON = SOURCE_SITE / "data" / "hfi_tracts.geojson"

CACHE_TAG = "20260723-hfi33"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def csv_to_string(rows: list[dict[str, object]], fields: list[str]) -> str:
    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def county_to_borough(geoid: str) -> str:
    county = str(geoid).zfill(11)[2:5]
    return {
        "005": "Bronx",
        "047": "Brooklyn",
        "061": "Manhattan",
        "081": "Queens",
        "085": "Staten Island",
    }.get(county, "")


def quantiles(values: list[float], bins: int) -> list[float]:
    vals = sorted(values)
    return [vals[round((i / bins) * (len(vals) - 1))] for i in range(bins + 1)]


def hfi_label(value: float | None, breaks: list[float]) -> str:
    if value is None:
        return "No HFI value"
    labels = [
        "Least fragmented",
        "Low fragmentation",
        "Moderate-low fragmentation",
        "Moderate-high fragmentation",
        "High fragmentation",
        "Most fragmented",
    ]
    for i, high in enumerate(breaks[1:]):
        if value <= high:
            return labels[i]
    return labels[-1]


def slim_number(value: object) -> object:
    num = to_float(value)
    if num is None:
        return value if value is not None else ""
    if abs(num - round(num)) < 1e-12:
        return str(int(round(num)))
    return f"{num:.10g}"


def build_data_files(site: Path) -> None:
    old_tract_rows = {row["GEOID"]: row for row in read_csv(OLD_TRACT_DATA)}
    surface_rows = read_csv(TRACT_SURFACE)
    values = [to_float(row["fragmentation_index"]) for row in surface_rows]
    breaks = quantiles([v for v in values if v is not None], 6)

    tract_fields = [
        "GEOID",
        "map_id",
        "borough",
        "population",
        "poverty_rate",
        "income",
        "lat_t",
        "lon_t",
        "providers",
        "provider_time_weight_sum",
        "avg_provider_time_weight",
        "density",
        "z_density",
        "min_dist",
        "inv_dist",
        "z_access_map",
        "FI",
        "FI2",
        "fragmentation_index",
        "FI_combined",
        "frag_q",
        "surface_version",
        "_ID",
    ]
    tract_rows: list[dict[str, object]] = []
    surface_by_geoid: dict[str, dict[str, str]] = {}
    for row in surface_rows:
        geoid = row["tract_id"]
        old = old_tract_rows.get(geoid, {})
        hfi = to_float(row["fragmentation_index"])
        out = {
            "GEOID": geoid,
            "map_id": geoid,
            "borough": old.get("borough") or county_to_borough(geoid),
            "population": slim_number(row.get("population", "")),
            "poverty_rate": slim_number(row.get("poverty_rate", "")),
            "income": slim_number(row.get("income", "")),
            "lat_t": slim_number(row.get("lat_t", "")),
            "lon_t": slim_number(row.get("lon_t", "")),
            "providers": slim_number(row.get("providers", "")),
            "provider_time_weight_sum": slim_number(row.get("provider_time_weight_sum", "")),
            "avg_provider_time_weight": slim_number(row.get("avg_provider_time_weight", "")),
            "density": slim_number(row.get("density", "")),
            "z_density": slim_number(row.get("z_density", "")),
            "min_dist": slim_number(row.get("min_dist", "")),
            "inv_dist": slim_number(row.get("inv_dist", "")),
            "z_access_map": slim_number(row.get("z_access", "")),
            "FI": slim_number(row.get("FI", "")),
            "FI2": slim_number(row.get("FI2", "")),
            "fragmentation_index": slim_number(row.get("fragmentation_index", "")),
            "FI_combined": slim_number(row.get("FI_combined", row.get("fragmentation_index", ""))),
            "frag_q": hfi_label(hfi, breaks),
            "surface_version": row.get("surface_version", ""),
            "_ID": old.get("_ID", ""),
        }
        tract_rows.append(out)
        surface_by_geoid[geoid] = {k: str(v) for k, v in out.items()}

    write_csv(site / "data" / "hfi_tract_data.csv", tract_rows, tract_fields)

    with OLD_TRACT_GEOJSON.open(encoding="utf-8") as handle:
        geojson = json.load(handle)
    for feature in geojson.get("features", []):
        props = feature.setdefault("properties", {})
        geoid = str(props.get("GEOID") or props.get("map_id") or "")
        updated = surface_by_geoid.get(geoid)
        if not updated:
            continue
        props.update(updated)
        hfi = to_float(updated["fragmentation_index"])
        props["hfi"] = hfi
        props["hfi_v1_1"] = hfi
        props["hfi_v1"] = hfi
    geojson["name"] = "HFI Explorer NYC corrected tract release v1.1"
    (site / "data" / "hfi_tracts.geojson").write_text(json.dumps(geojson, separators=(",", ":")), encoding="utf-8")
    (site / "data" / "hfi_tracts.js").write_text(
        "window.HFI_TRACTS_GEOJSON = " + json.dumps(geojson, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )

    hospitals = read_csv(HOSPITAL_UNIVERSE)
    hospital_fields = [
        "facility_id",
        "facility_name",
        "hospital_system",
        "public_private_designation",
        "address",
        "city",
        "state",
        "zip",
        "county",
        "borough",
        "telephone_number",
        "hospital_type",
        "hospital_ownership",
        "hospital_overall_rating",
        "emergency_services",
        "birthing_friendly",
        "included_in_hcahps_validation",
        "hcahps_exclusion_reason",
        "GEOID",
        "tract_id",
        "_CX",
        "_CY",
        "fragmentation_index",
        "fragmentation",
        "access_z",
        "providers",
        "provider_time_weight_sum",
        "avg_provider_time_weight",
        "density",
        "min_dist",
        "communication_index",
        "patient_experience_index",
        "hcahps_nurse_comm_linear",
        "hcahps_doctor_comm_linear",
        "hcahps_medicine_comm_linear",
        "hcahps_discharge_linear",
        "hcahps_overall_linear",
        "hcahps_recommend_linear",
        "number_of_completed_surveys",
        "survey_response_rate_percent",
        "hcahps_start_date",
        "hcahps_end_date",
    ]
    hospital_rows: list[dict[str, object]] = []
    for row in hospitals:
        geoid = row.get("GEOID", "")
        tract = surface_by_geoid.get(geoid, {})
        hfi = tract.get("fragmentation_index", row.get("fragmentation_index", ""))
        included = str(row.get("included_in_hcahps_validation", "")).lower() == "true"
        out = {field: row.get(field, "") for field in hospital_fields}
        out.update(
            {
                "borough": row.get("borough") or county_to_borough(geoid),
                "tract_id": geoid,
                "included_in_hcahps_validation": "Yes" if included else "No",
                "fragmentation_index": hfi,
                "fragmentation": hfi,
                "access_z": tract.get("z_access_map", row.get("access_z", "")),
                "providers": tract.get("providers", row.get("providers", "")),
                "provider_time_weight_sum": tract.get("provider_time_weight_sum", row.get("provider_time_weight_sum", "")),
                "avg_provider_time_weight": tract.get("avg_provider_time_weight", row.get("avg_provider_time_weight", "")),
                "density": tract.get("density", row.get("density", "")),
                "min_dist": tract.get("min_dist", row.get("min_dist", "")),
            }
        )
        if not included:
            out["communication_index"] = ""
            out["patient_experience_index"] = ""
        hospital_rows.append(out)

    hospital_rows.sort(key=lambda r: (str(r.get("borough", "")), str(r.get("facility_name", ""))))
    write_csv(site / "data" / "hfi_hospitals.csv", hospital_rows, hospital_fields)
    csv_text = csv_to_string(hospital_rows, hospital_fields)
    (site / "data" / "hfi_hospitals.js").write_text(
        "window.HFI_HOSPITALS_CSV = " + json.dumps(csv_text) + ";\n",
        encoding="utf-8",
    )


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.escape(start) + r".*?" + re.escape(end)
    return re.sub(pattern, start + replacement + end, text, flags=re.S)


def update_explorer_js(site: Path) -> None:
    path = site / "assets" / "js" / "explorer.js"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "async function loadGeoJson(url) {\n  const res = await fetch(url, { cache: 'no-store' });\n  if (!res.ok) throw new Error(`${url}: ${res.status} ${res.statusText}`);\n  return await res.json();\n}",
        "async function loadGeoJson(url) {\n  if (window.HFI_TRACTS_GEOJSON) return window.HFI_TRACTS_GEOJSON;\n  const res = await fetch(url, { cache: 'no-store' });\n  if (!res.ok) throw new Error(`${url}: ${res.status} ${res.statusText}`);\n  return await res.json();\n}",
    )
    text = text.replace(
        "function loadCsv(url) {\n  return new Promise((resolve, reject) => {\n    Papa.parse(url, {",
        "function loadCsv(url) {\n  return new Promise((resolve, reject) => {\n    const inlineCsv = url.includes('hfi_hospitals') ? window.HFI_HOSPITALS_CSV : null;\n    Papa.parse(inlineCsv || url, {",
    )
    text = text.replace("download: true,", "download: !inlineCsv,")
    text = text.replace(
        "setStatus('ready', `Loaded ${tractFeatures.length.toLocaleString()} HFI tracts and ${hospitalRecords.length.toLocaleString()} linked hospitals.`);",
        "setStatus('ready', `Loaded ${tractFeatures.length.toLocaleString()} HFI tracts, ${hospitalRecords.length.toLocaleString()} CMS-listed acute-care hospitals, and ${countValidationHospitals(hospitalRecords).toLocaleString()} HCAHPS-complete validation hospitals.`);",
    )
    text = text.replace(
        "const comm = numberValue(getValue(row, CONFIG.communicationAliases));\n    const rating = numberValue(row.hospital_overall_rating);\n    const marker = L.circleMarker([lat, lon], {\n      pane: 'hospitalPane',\n      radius: 7.5,\n      color: '#07192c',\n      weight: 2.1,\n      fillColor: Number.isFinite(comm) ? '#ffd166' : '#ffffff',\n      fillOpacity: .98\n    });\n    marker.defaultStyle = {\n      radius: 7.5,\n      color: '#07192c',\n      weight: 2.1,\n      fillColor: Number.isFinite(comm) ? '#ffd166' : '#ffffff',\n      fillOpacity: .98\n    };",
        "const comm = numberValue(getValue(row, CONFIG.communicationAliases));\n    const rating = numberValue(row.hospital_overall_rating);\n    const included = isHcahpsComplete(row);\n    const markerStyle = {\n      pane: 'hospitalPane',\n      radius: included ? 7.8 : 7.2,\n      color: included ? '#07192c' : '#5d6b7c',\n      weight: included ? 2.1 : 1.9,\n      fillColor: included ? '#ffd166' : '#ffffff',\n      fillOpacity: included ? .98 : .92,\n      dashArray: included ? null : '3 2'\n    };\n    const marker = L.circleMarker([lat, lon], markerStyle);\n    marker.defaultStyle = markerStyle;",
    )
    text = text.replace(
        "showFeatureInfo('Hospital', row.name, {\n    Borough: standardBorough(row.county || ''),\n    'Overall CMS rating': formatNumber(rating, 0),\n    'Communication index': formatNumber(comm, 2),\n    'Doctor communication': formatNumber(numberValue(row.hcahps_doctor_comm_linear), 1),\n    'Nurse communication': formatNumber(numberValue(row.hcahps_nurse_comm_linear), 1),\n    'Linked tract HFI': formatNumber(numberValue(row.fragmentation), 3)\n  });",
        "showFeatureInfo('Hospital', row.name, {\n    System: row.hospital_system || 'Not classified',\n    Borough: row.borough || standardBorough(row.county || ''),\n    'Public/private': row.public_private_designation || row.hospital_ownership || 'Not classified',\n    'HCAHPS validation': validationLabel(row),\n    'Linked tract HFI': formatNumber(hospitalHfi(row), 3),\n    'Provider-time availability': formatNumber(numberValue(row.provider_time_weight_sum), 3),\n    'Overall CMS rating': formatNumber(rating, 0),\n    'Communication index': formatNumber(comm, 2),\n    'Doctor communication': formatNumber(numberValue(row.hcahps_doctor_comm_linear), 1),\n    'Nurse communication': formatNumber(numberValue(row.hcahps_nurse_comm_linear), 1)\n  });",
    )
    text = text.replace(
        "document.getElementById('hospital-count').textContent = filteredHospitals.length.toLocaleString();",
        "document.getElementById('hospital-count').textContent = filteredHospitals.length.toLocaleString();\n  const validationEl = document.getElementById('validation-count');\n  if (validationEl) validationEl.textContent = countValidationHospitals(filteredHospitals).toLocaleString();",
    )
    text = text.replace(
        "function updateStats(values, hospitals) {\n  document.getElementById('tract-count').textContent = tractFeatures.length.toLocaleString();\n  document.getElementById('hospital-count').textContent = hospitals.toLocaleString();",
        "function updateStats(values, hospitals) {\n  document.getElementById('tract-count').textContent = tractFeatures.length.toLocaleString();\n  document.getElementById('hospital-count').textContent = hospitals.toLocaleString();\n  const validationEl = document.getElementById('validation-count');\n  if (validationEl) validationEl.textContent = countValidationHospitals(hospitalRecords).toLocaleString();",
    )
    text = text.replace(
        "  if (hospitalEl) hospitalEl.textContent = hospitals.toLocaleString();\n  if (rangeEl) {",
        "  if (hospitalEl) hospitalEl.textContent = hospitals.toLocaleString();\n  const validationEl = document.getElementById('summary-validation-count');\n  if (validationEl) validationEl.textContent = countValidationHospitals(hospitalRecords.filter(h => !document.getElementById('borough-filter') || document.getElementById('borough-filter').value === 'all' || (h.borough || standardBorough(h.county || '')) === document.getElementById('borough-filter').value)).toLocaleString();\n  if (rangeEl) {",
    )
    text = text.replace(
        "function hospitalPopup(row, comm, rating) {\n  const tractHfi = numberValue(row.fragmentation);\n  return `<div class=\"popup-card\">\n    <strong>${escapeHtml(row.name)}</strong>\n    <span>${escapeHtml(row.address || '')}${row.city ? `, ${escapeHtml(row.city)}` : ''}</span>\n    <span>Communication index: ${formatNumber(comm, 2)}</span>\n    <span>CMS rating: ${formatNumber(rating, 0)}</span>\n    <span>Linked tract HFI: ${formatNumber(tractHfi, 3)}</span>\n  </div>`;\n}",
        "function hospitalPopup(row, comm, rating) {\n  const tractHfi = hospitalHfi(row);\n  return `<div class=\"popup-card\">\n    <strong>${escapeHtml(row.name)}</strong>\n    <span>${escapeHtml(row.address || '')}${row.city ? `, ${escapeHtml(row.city)}` : ''}</span>\n    <span>${escapeHtml(row.hospital_system || 'Hospital system not classified')}</span>\n    <span>HCAHPS validation: ${escapeHtml(validationLabel(row))}</span>\n    <span>Linked tract HFI: ${formatNumber(tractHfi, 3)}</span>\n    <span>Communication index: ${formatNumber(comm, 2)}</span>\n    <span>CMS rating: ${formatNumber(rating, 0)}</span>\n  </div>`;\n}",
    )
    insert = """
function isHcahpsComplete(row) {
  const flag = String(row?.included_in_hcahps_validation || '').toLowerCase();
  return flag === 'yes' || flag === 'true' || flag === '1';
}

function countValidationHospitals(records) {
  return (records || []).filter(isHcahpsComplete).length;
}

function validationLabel(row) {
  if (isHcahpsComplete(row)) return 'Included in HCAHPS-complete validation sample';
  return row?.hcahps_exclusion_reason || 'CMS-listed acute-care hospital; HCAHPS linear outcomes unavailable';
}

function hospitalHfi(row) {
  return numberValue(row.fragmentation_index) ?? numberValue(row.fragmentation);
}

"""
    text = text.replace("function resetHospitalMarker(marker) {", insert + "function resetHospitalMarker(marker) {")
    path.write_text(text, encoding="utf-8")


def update_static_pages(site: Path) -> None:
    replacements = {
        "HFI v1.0 · NYC release · July 2026": "HFI NYC analytic release · July 2026",
        "HFI v1.0 NYC release": "HFI NYC analytic release",
        "full v1.0 tract-level web-release dataset": "corrected tract-level HFI surface and CMS-listed acute-care hospital layer",
        "v1.0": "v1.1",
        "23 linked hospital records, including NYU Langone Hospitals": "33 CMS-listed acute-care hospitals, with 32 HCAHPS-complete validation hospitals",
        "23 linked hospitals": "33 CMS-listed acute-care hospitals",
        "23 linked hospital": "33 CMS-listed acute-care hospital",
        "linked hospitals": "CMS acute-care hospitals",
        "linked hospital": "CMS acute-care hospital",
        "HFI v1.1 is not a hospital quality score, a replacement for HCAHPS, or a definitive measure of all possible forms of care fragmentation.": "HFI is a reproducible spatial measurement framework. It complements hospital quality measures such as HCAHPS by describing the local care environment in which hospitals and patients are embedded.",
    }
    for path in site.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = re.sub(r"v=20260714-final-neutral|v=20260722-mapclick|v=20260722-canvastractselect", f"v={CACHE_TAG}", text)
        text = text.replace("Explore tract-level healthcare fragmentation and CMS acute-care hospital context for New York City.", "Explore the corrected tract-level HFI surface and CMS-listed acute-care hospital context for New York City.")
        if path.name == "index.html":
            text = text.replace('<div><strong id="home-hospital-count">23</strong><span>CMS acute-care hospitals</span></div>', '<div><strong id="home-hospital-count">33</strong><span>CMS acute-care hospitals</span></div>')
            text = text.replace('<div><strong>v1.1</strong><span>foundational index</span></div>', '<div><strong>32</strong><span>HCAHPS-complete hospitals</span></div>')
            text = text.replace(
                "The Healthcare Fragmentation Index is a reproducible tract-level framework for measuring whether healthcare resources form a coherent, reachable, and navigable system of care.",
                "The Healthcare Fragmentation Index is a reproducible tract-level framework for measuring whether healthcare resources form a coherent, reachable, and navigable system of care.",
            )
        if path.name == "explorer.html":
            text = text.replace(
                '<div><strong id="summary-hospital-count">—</strong><span>hospitals</span></div>\n        <div><strong id="summary-hfi-range">—</strong><span>HFI range</span></div>',
                '<div><strong id="summary-hospital-count">—</strong><span>CMS hospitals</span></div>\n        <div><strong id="summary-validation-count">—</strong><span>HCAHPS-complete</span></div>\n        <div><strong id="summary-hfi-range">—</strong><span>HFI range</span></div>',
            )
            text = text.replace(
                '<div><strong id="hospital-count">—</strong><span>hospitals</span></div>\n        <div><strong id="hfi-range">—</strong><span>HFI range</span></div>',
                '<div><strong id="hospital-count">—</strong><span>CMS hospitals</span></div>\n        <div><strong id="validation-count">—</strong><span>HCAHPS-complete</span></div>\n        <div><strong id="hfi-range">—</strong><span>HFI range</span></div>',
            )
            text = text.replace("Linked sites", "CMS acute-care sites")
            text = text.replace("Click a tract or hospital to view HFI, access, provider-time, and patient-experience context.", "Click a tract or hospital to view HFI, access, provider-time availability, hospital-system context, and HCAHPS validation status.")
            text = text.replace("HFI v1.1 combines local healthcare access, social need, demand pressure, and time-adjusted provider availability into a tract-level index for reproducible neighborhood comparison.", "HFI describes access as multidimensional: geographic reachability, provider availability, demand pressure, and the navigability of the surrounding care environment. The Explorer provides a public implementation of the corrected NYC HFI surface.")
            text = text.replace('<p class="note">Higher values indicate more fragmented and structurally constrained healthcare environments. Classes are computed from this release using quantile breaks.</p>', '<p class="note">Higher values indicate more fragmented and structurally constrained healthcare environments. Hospital markers show CMS-listed acute-care hospitals; filled gold markers are HCAHPS-complete validation hospitals.</p>')
        path.write_text(text, encoding="utf-8")

    for path in [site / "README.md", site / "data" / "README.md"]:
        text = path.read_text(encoding="utf-8")
        text = text.replace("v1.0", "v1.1")
        text = text.replace("23 linked hospital records, including NYU Langone Hospitals", "33 CMS-listed acute-care hospitals, including 32 HCAHPS-complete validation hospitals")
        text = text.replace("23 linked hospitals including NYU Langone Hospitals", "33 CMS-listed acute-care hospitals, including 32 HCAHPS-complete validation hospitals")
        text = text.replace("linked hospital/HCAHPS data", "CMS acute-care hospital universe and HCAHPS validation data")
        path.write_text(text, encoding="utf-8")


def update_css(site: Path) -> None:
    path = site / "assets" / "css" / "style.css"
    text = path.read_text(encoding="utf-8")
    text = text.replace(".explorer-summary { display: grid; grid-template-columns: 1fr 1fr;", ".explorer-summary { display: grid; grid-template-columns: 1fr 1fr;")
    text = text.replace(".metric-cards { display: grid; grid-template-columns: 1fr; gap: .6rem; }", ".metric-cards { display: grid; grid-template-columns: 1fr; gap: .6rem; }")
    if ".leaflet-interactive:hover" not in text:
        text += "\n.leaflet-interactive:hover { filter: saturate(1.08); }\n"
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if OUT_SITE.exists():
        shutil.rmtree(OUT_SITE)
    shutil.copytree(SOURCE_SITE, OUT_SITE, copy_function=shutil.copy)
    build_data_files(OUT_SITE)
    update_explorer_js(OUT_SITE)
    update_static_pages(OUT_SITE)
    update_css(OUT_SITE)
    for junk in OUT_SITE.rglob(".DS_Store"):
        junk.unlink()
    now = time.time()
    for path in sorted(OUT_SITE.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        os.utime(path, (now, now))
    os.utime(OUT_SITE, (now, now))
    archive = shutil.make_archive(str(OUT_SITE), "zip", OUT_SITE)
    print(OUT_SITE)
    print(archive)


if __name__ == "__main__":
    main()
