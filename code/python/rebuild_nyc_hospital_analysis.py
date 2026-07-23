import csv
import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent
RAW = BASE / "raw"
DERIVED = BASE / "derived"
DERIVED.mkdir(parents=True, exist_ok=True)

HOSPITAL_GENERAL_URL = "https://data.cms.gov/provider-data/sites/default/files/resources/893c372430d9d71a1c52737d01239d47_1777413958/Hospital_General_Information.csv"
HCAHPS_URL = "https://data.cms.gov/provider-data/sites/default/files/resources/78a50346fbe828ea0ce2837847af6a7c_1777413952/HCAHPS-Hospital.csv"

TRACT_GEOJSON = Path("/Users/giacomo/Documents/Codex/2026-07-07/is/work/hfi-explorer-site-updated-v2/data/hfi_tracts.geojson")
TRACT_DATA = Path("/Users/giacomo/Documents/Codex/2026-07-07/is/work/hfi-explorer-site-updated-v2/data/hfi_tract_data.csv")
CURRENT_HOSPITALS = Path("/Users/giacomo/Documents/Codex/2026-07-07/is/work/hfi-explorer-site-updated-v2/data/hfi_hospitals.csv")

NYC_COUNTIES = {"BRONX", "KINGS", "NEW YORK", "QUEENS", "RICHMOND"}

SYSTEM_MAP = {
    "BELLEVUE HOSPITAL CENTER": ("NYC Health + Hospitals", "Public"),
    "ELMHURST HOSPITAL CENTER": ("NYC Health + Hospitals", "Public"),
    "HARLEM HOSPITAL CENTER": ("NYC Health + Hospitals", "Public"),
    "JACOBI MEDICAL CENTER": ("NYC Health + Hospitals", "Public"),
    "KINGS COUNTY HOSPITAL CENTER": ("NYC Health + Hospitals", "Public"),
    "LINCOLN MEDICAL & MENTAL HEALTH CENTER": ("NYC Health + Hospitals", "Public"),
    "METROPOLITAN HOSPITAL CENTER": ("NYC Health + Hospitals", "Public"),
    "QUEENS HOSPITAL CENTER": ("NYC Health + Hospitals", "Public"),
    "SOUTH BROOKLYN HEALTH": ("NYC Health + Hospitals", "Public"),
    "WOODHULL MEDICAL & MENTAL HEALTH CENTER": ("NYC Health + Hospitals", "Public"),
    "BRONXCARE HOSPITAL CENTER": ("BronxCare Health System", "Private nonprofit"),
    "BROOKDALE HOSPITAL MEDICAL CENTER": ("One Brooklyn Health", "Private nonprofit"),
    "BROOKLYN HOSPITAL CENTER - DOWNTOWN CAMPUS": ("The Brooklyn Hospital Center", "Private nonprofit"),
    "FLUSHING HOSPITAL MEDICAL CENTER": ("MediSys Health Network", "Private nonprofit"),
    "HOSPITAL FOR SPECIAL SURGERY": ("Hospital for Special Surgery", "Private nonprofit"),
    "JAMAICA HOSPITAL MEDICAL CENTER": ("MediSys Health Network", "Private nonprofit"),
    "LENOX HILL HOSPITAL": ("Northwell Health", "Private nonprofit"),
    "MAIMONIDES MEDICAL CENTER": ("Maimonides Health", "Private nonprofit"),
    "MONTEFIORE MEDICAL CENTER": ("Montefiore Health System", "Private nonprofit"),
    "MOUNT SINAI BETH ISRAEL": ("Mount Sinai Health System", "Private nonprofit"),
    "MOUNT SINAI HOSPITAL": ("Mount Sinai Health System", "Private nonprofit"),
    "MOUNT SINAI WEST": ("Mount Sinai Health System", "Private nonprofit"),
    "NY EYE AND EAR INFIRMARY OF MOUNT SINAI": ("Mount Sinai Health System", "Private nonprofit"),
    "NEW YORK COMMUNITY HOSPITAL OF BROOKLYN, INC.": ("New York Community Hospital", "Private nonprofit"),
    "NEW YORK-PRESBYTERIAN HOSPITAL": ("NewYork-Presbyterian", "Private nonprofit"),
    "NEW YORK-PRESBYTERIAN/QUEENS": ("NewYork-Presbyterian", "Private nonprofit"),
    "NYU LANGONE HOSPITALS": ("NYU Langone Health", "Private nonprofit"),
    "RICHMOND UNIVERSITY MEDICAL CENTER": ("Richmond University Medical Center", "Private nonprofit"),
    "ST BARNABAS HOSPITAL": ("St. Barnabas Hospital / SBH Health System", "Private nonprofit"),
    "ST JOHN'S EPISCOPAL HOSPITAL AT SOUTH SHORE": ("Episcopal Health Services", "Private nonprofit"),
    "STATEN ISLAND UNIVERSITY HOSPITAL": ("Northwell Health", "Private nonprofit"),
    "SUNY/DOWNSTATE UNIVERSITY HOSPITAL OF BROOKLYN": ("SUNY Downstate Health Sciences University", "Public"),
    "WYCKOFF HEIGHTS MEDICAL CENTER": ("Wyckoff Heights Medical Center", "Private nonprofit"),
}

GEOCODE_FALLBACKS = {
    # Census geocoder misses these CMS address strings; fallback coordinates are
    # from OpenStreetMap/Nominatim hospital matches and are flagged in output.
    "330194": (-73.9981068, 40.6394203, "osm_nominatim_hospital_fallback"),
    "330128": (-73.8856505, 40.7447748, "osm_nominatim_hospital_fallback"),
}

PIVOT_MEASURES = {
    "H_CLEAN_LINEAR_SCORE": "hcahps_clean_linear",
    "H_CLEAN_STAR_RATING": "hcahps_clean_star",
    "H_COMP_1_LINEAR_SCORE": "hcahps_nurse_comm_linear",
    "H_COMP_1_STAR_RATING": "hcahps_nurse_comm_star",
    "H_COMP_2_LINEAR_SCORE": "hcahps_doctor_comm_linear",
    "H_COMP_2_STAR_RATING": "hcahps_doctor_comm_star",
    "H_COMP_5_LINEAR_SCORE": "hcahps_medicine_comm_linear",
    "H_COMP_5_STAR_RATING": "hcahps_medicine_comm_star",
    "H_COMP_6_LINEAR_SCORE": "hcahps_discharge_linear",
    "H_COMP_6_STAR_RATING": "hcahps_discharge_star",
    "H_HSP_RATING_LINEAR_SCORE": "hcahps_overall_linear",
    "H_HSP_RATING_STAR_RATING": "hcahps_overall_star",
    "H_QUIET_LINEAR_SCORE": "hcahps_quiet_linear",
    "H_QUIET_STAR_RATING": "hcahps_quiet_star",
    "H_RECMND_LINEAR_SCORE": "hcahps_recommend_linear",
    "H_RECMND_STAR_RATING": "hcahps_recommend_star",
    "H_STAR_RATING": "hcahps_summary_star",
}


def download_if_missing(url, path):
    if path.exists() and path.stat().st_size > 1000:
        return
    with urllib.request.urlopen(url) as response, path.open("wb") as out:
        out.write(response.read())


def clean_num(value):
    if pd.isna(value):
        return math.nan
    text = str(value).strip()
    if not text or text.lower() in {"not available", "not applicable"}:
        return math.nan
    try:
        return float(text)
    except ValueError:
        return math.nan


def geocode_address(address, city, state, zip_code):
    one_line = f"{address}, {city}, {state} {zip_code}"
    params = urllib.parse.urlencode({
        "address": one_line,
        "benchmark": "Public_AR_Current",
        "format": "json",
    })
    url = f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{params}"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            data = json.load(response)
    except Exception:
        return None, None, "geocode_request_failed"
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None, None, "no_census_match"
    coords = matches[0].get("coordinates", {})
    return coords.get("x"), coords.get("y"), "census_geocoder"


def point_in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-30) + xi)
        if intersects:
            inside = not inside
        j = i
    return inside


def point_in_polygon(x, y, coords):
    if not coords:
        return False
    if not point_in_ring(x, y, coords[0]):
        return False
    for hole in coords[1:]:
        if point_in_ring(x, y, hole):
            return False
    return True


def point_in_geometry(x, y, geom):
    typ = geom.get("type")
    coords = geom.get("coordinates", [])
    if typ == "Polygon":
        return point_in_polygon(x, y, coords)
    if typ == "MultiPolygon":
        return any(point_in_polygon(x, y, poly) for poly in coords)
    return False


def tract_lookup(x, y, features):
    for feature in features:
        if point_in_geometry(x, y, feature.get("geometry", {})):
            props = feature.get("properties", {})
            return str(props.get("GEOID") or props.get("GEOID20") or props.get("geoid") or "")
    return ""


def zscore(series):
    s = pd.to_numeric(series, errors="coerce")
    return (s - s.mean()) / s.std(ddof=1)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    download_if_missing(HOSPITAL_GENERAL_URL, RAW / "Hospital_General_Information.csv")
    download_if_missing(HCAHPS_URL, RAW / "HCAHPS-Hospital.csv")

    general = pd.read_csv(RAW / "Hospital_General_Information.csv", dtype=str)
    hcahps = pd.read_csv(RAW / "HCAHPS-Hospital.csv", dtype=str)

    nyc = general[
        (general["State"] == "NY")
        & (general["County/Parish"].str.upper().isin(NYC_COUNTIES))
        & (general["Hospital Type"] == "Acute Care Hospitals")
    ].copy()
    nyc = nyc.sort_values(["County/Parish", "Facility Name"]).reset_index(drop=True)

    hc = hcahps[hcahps["Facility ID"].isin(nyc["Facility ID"])].copy()
    hc["measure_value"] = hc["HCAHPS Linear Mean Value"].where(
        hc["HCAHPS Linear Mean Value"].notna() & (hc["HCAHPS Linear Mean Value"].str.strip() != ""),
        hc["Patient Survey Star Rating"],
    )
    wide = hc[hc["HCAHPS Measure ID"].isin(PIVOT_MEASURES)].pivot_table(
        index="Facility ID",
        columns="HCAHPS Measure ID",
        values="measure_value",
        aggfunc="first",
    ).rename(columns=PIVOT_MEASURES).reset_index()
    for col in PIVOT_MEASURES.values():
        if col in wide.columns:
            wide[col] = wide[col].map(clean_num)

    survey_meta = hc.groupby("Facility ID").agg(
        number_of_completed_surveys=("Number of Completed Surveys", "first"),
        survey_response_rate_percent=("Survey Response Rate Percent", "first"),
        hcahps_start_date=("Start Date", "first"),
        hcahps_end_date=("End Date", "first"),
    ).reset_index()

    out = nyc.merge(wide, on="Facility ID", how="left").merge(survey_meta, on="Facility ID", how="left")
    out["hospital_system"] = out["Facility Name"].map(lambda x: SYSTEM_MAP.get(str(x).upper(), ("Needs verification", ""))[0])
    out["public_private_designation"] = out["Facility Name"].map(lambda x: SYSTEM_MAP.get(str(x).upper(), ("", "Needs verification"))[1])

    required = [
        "hcahps_nurse_comm_linear",
        "hcahps_doctor_comm_linear",
        "hcahps_medicine_comm_linear",
        "hcahps_discharge_linear",
        "hcahps_overall_linear",
        "hcahps_recommend_linear",
    ]
    out["included_in_hcahps_validation"] = out[required].notna().all(axis=1)
    out["hcahps_exclusion_reason"] = ""
    out.loc[~out["included_in_hcahps_validation"], "hcahps_exclusion_reason"] = "Missing one or more required HCAHPS linear communication/experience outcomes"

    for col in ["hcahps_overall_linear", "hcahps_recommend_linear", "hcahps_nurse_comm_linear", "hcahps_doctor_comm_linear", "hcahps_medicine_comm_linear", "hcahps_discharge_linear"]:
        out["z_" + col.replace("hcahps_", "").replace("_linear", "")] = zscore(out[col])
    out["communication_index"] = out[["hcahps_nurse_comm_linear", "hcahps_doctor_comm_linear"]].mean(axis=1)
    zcols = ["z_overall", "z_recommend", "z_nurse_comm", "z_doctor_comm", "z_medicine_comm", "z_discharge"]
    out["patient_experience_index"] = out[zcols].mean(axis=1)

    current = pd.read_csv(CURRENT_HOSPITALS, dtype=str)
    coord_by_id = current.set_index("facility_id")[["_CX", "_CY"]].to_dict("index")
    xs, ys, sources = [], [], []
    for _, row in out.iterrows():
        fid = row["Facility ID"]
        if fid in coord_by_id and coord_by_id[fid].get("_CX") and coord_by_id[fid].get("_CY"):
            xs.append(float(coord_by_id[fid]["_CX"]))
            ys.append(float(coord_by_id[fid]["_CY"]))
            sources.append("existing_hfi_layer")
            continue
        if fid in GEOCODE_FALLBACKS:
            x, y, source = GEOCODE_FALLBACKS[fid]
            xs.append(x)
            ys.append(y)
            sources.append(source)
            continue
        x, y, source = geocode_address(row["Address"], row["City/Town"], row["State"], row["ZIP Code"])
        time.sleep(0.15)
        xs.append(x)
        ys.append(y)
        sources.append(source)
    out["_CX"] = xs
    out["_CY"] = ys
    out["geocode_source"] = sources

    with TRACT_GEOJSON.open() as f:
        tracts_geo = json.load(f)
    features = tracts_geo["features"]
    out["GEOID"] = [
        tract_lookup(float(x), float(y), features) if pd.notna(x) and pd.notna(y) else ""
        for x, y in zip(out["_CX"], out["_CY"])
    ]

    tract_data = pd.read_csv(TRACT_DATA, dtype={"GEOID": str})
    hfi_cols = ["GEOID", "borough", "fragmentation_index", "FI_combined", "FI", "FI2", "z_access_map", "providers", "density", "min_dist", "income", "poverty_rate"]
    out = out.merge(tract_data[[c for c in hfi_cols if c in tract_data.columns]], on="GEOID", how="left")
    out["access_z"] = pd.to_numeric(out.get("z_access_map"), errors="coerce")
    out["fragmentation"] = -out["access_z"]

    rename = {
        "Facility ID": "facility_id",
        "Facility Name": "facility_name",
        "Address": "address",
        "City/Town": "city",
        "State": "state",
        "ZIP Code": "zip",
        "County/Parish": "county",
        "Telephone Number": "telephone_number",
        "Hospital Type": "hospital_type",
        "Hospital Ownership": "hospital_ownership",
        "Emergency Services": "emergency_services",
        "Meets criteria for promoting interoperability of EHRs": "ehr_interop",
        "Meets criteria for birthing friendly designation": "birthing_friendly",
        "Hospital overall rating": "hospital_overall_rating",
    }
    out = out.rename(columns={k: v for k, v in rename.items() if k in out.columns})

    first_cols = [
        "facility_id", "facility_name", "hospital_system", "public_private_designation",
        "address", "city", "state", "zip", "county", "telephone_number",
        "hospital_type", "hospital_ownership", "hospital_overall_rating",
        "included_in_hcahps_validation", "hcahps_exclusion_reason",
        "GEOID", "_CX", "_CY", "geocode_source", "borough",
        "fragmentation_index", "fragmentation", "access_z",
        "communication_index", "patient_experience_index",
    ]
    ordered = [c for c in first_cols if c in out.columns] + [c for c in out.columns if c not in first_cols]
    out = out[ordered]

    out.to_csv(DERIVED / "nyc_acute_care_hospital_universe_33.csv", index=False)
    out[out["included_in_hcahps_validation"]].to_csv(DERIVED / "nyc_hcahps_validation_analysis_file.csv", index=False)

    summary_rows = [
        ["cms_nyc_acute_care_hospitals", len(out)],
        ["hcahps_complete_validation_hospitals", int(out["included_in_hcahps_validation"].sum())],
        ["not_hcahps_complete_or_unlinked", int((~out["included_in_hcahps_validation"]).sum())],
        ["missing_geocode", int(out["_CX"].isna().sum())],
        ["missing_hfi_tract_link", int((out["GEOID"] == "").sum() + out["GEOID"].isna().sum())],
    ]
    with (DERIVED / "rebuild_summary.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerows(summary_rows)

    audit_cols = ["facility_id", "facility_name", "county", "hospital_system", "included_in_hcahps_validation", "hcahps_exclusion_reason", "GEOID", "geocode_source"]
    out[audit_cols].to_csv(DERIVED / "facility_inclusion_audit.csv", index=False)

    print(pd.read_csv(DERIVED / "rebuild_summary.csv").to_string(index=False))


if __name__ == "__main__":
    main()
