import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("/Users/giacomo/Documents/Codex/2026-07-07/is")
DESKTOP = Path("/Users/giacomo/Desktop/Wagner/SUNY + UMich/Datasets")
BASE = ROOT / "outputs/hfi_surface_rebuild_2026_07_22"
BASE.mkdir(parents=True, exist_ok=True)

TRACT_FULL = DESKTOP / "hfi_tract_data_full.csv"
TRACT_GEOJSON = ROOT / "work/hfi-explorer-site-updated-v2/data/hfi_tracts.geojson"
PROVIDERS = DESKTOP / "providers_with_time_weights.dta"
PROVIDER_TO_TRACT = DESKTOP / "provider_to_tract.dta"
CMS_UNIVERSE = ROOT / "outputs/hospital_rebuild_2026_07_22/derived/nyc_acute_care_hospital_universe_33.csv"


CMS_PROVIDER_MATCHES = {
    "330009": "exact_or_nearest",
    "330127": "exact_or_nearest",
    "330080": "exact_or_nearest",
    "330059": "add_cms",       # CMS row represents consolidated Montefiore Medical Center.
    "330399": "add_cms",       # Main St Barnabas Hospital absent as named acute-care row.
    "330233": "exact_or_nearest",
    "330056": "exact_or_nearest",
    "330202": "exact_or_nearest",
    "330194": "exact_or_nearest",
    "330019": "add_cms",       # New York Community Hospital absent from provider layer.
    "330196": "exact_or_nearest",
    "330350": "add_cms",       # CMS naming differs from University Hospital of Brooklyn.
    "330396": "exact_or_nearest",
    "330221": "exact_or_nearest",
    "330204": "exact_or_nearest",
    "330240": "exact_or_nearest",
    "330270": "exact_or_nearest",
    "330119": "exact_or_nearest",
    "330199": "exact_or_nearest",
    "330169": "add_cms",       # Main Mount Sinai Beth Israel absent at CMS address.
    "330024": "exact_or_nearest",
    "330046": "exact_or_nearest",
    "330101": "add_cms",       # Use CMS address for NYP consolidated hospital.
    "330100": "exact_or_nearest",
    "330214": "exact_or_nearest",
    "330128": "exact_or_nearest",
    "330193": "exact_or_nearest",
    "330014": "exact_or_nearest",
    "330055": "exact_or_nearest",
    "330231": "exact_or_nearest",
    "330395": "add_cms",       # Main St John's Episcopal CMS address preferred.
    "330028": "exact_or_nearest",
    "330160": "exact_or_nearest",
}


def norm_name(value):
    return re.sub(r"[^A-Z0-9]+", " ", str(value).upper()).strip()


def zscore(s):
    s = pd.to_numeric(s, errors="coerce")
    return (s - s.mean()) / s.std(ddof=1)


def point_in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)):
            cross = (xj - xi) * (y - yi) / ((yj - yi) or 1e-30) + xi
            if x < cross:
                inside = not inside
        j = i
    return inside


def point_in_polygon(x, y, coords):
    if not coords or not point_in_ring(x, y, coords[0]):
        return False
    for hole in coords[1:]:
        if point_in_ring(x, y, hole):
            return False
    return True


def point_in_geometry(x, y, geom):
    if geom["type"] == "Polygon":
        return point_in_polygon(x, y, geom["coordinates"])
    if geom["type"] == "MultiPolygon":
        return any(point_in_polygon(x, y, poly) for poly in geom["coordinates"])
    return False


def geom_bbox(geom):
    xs, ys = [], []
    def collect(coords):
        if isinstance(coords[0], (float, int)):
            xs.append(coords[0]); ys.append(coords[1])
        else:
            for c in coords:
                collect(c)
    collect(geom["coordinates"])
    return min(xs), min(ys), max(xs), max(ys)


def make_tract_index():
    with TRACT_GEOJSON.open() as f:
        geo = json.load(f)
    index = []
    for feat in geo["features"]:
        props = feat.get("properties", {})
        geoid = str(props.get("GEOID") or props.get("GEOID20") or props.get("geoid"))
        bbox = geom_bbox(feat["geometry"])
        index.append((geoid, bbox, feat["geometry"]))
    return index


def tract_for_point(x, y, tract_index):
    for geoid, bbox, geom in tract_index:
        minx, miny, maxx, maxy = bbox
        if x < minx or x > maxx or y < miny or y > maxy:
            continue
        if point_in_geometry(x, y, geom):
            return geoid
    return ""


def min_dist_to_providers(tracts, providers):
    pcoords = providers[["lon", "lat"]].dropna().to_numpy(float)
    out = []
    for lon, lat in tracts[["lon_t", "lat_t"]].to_numpy(float):
        d = np.sqrt(((pcoords[:, 0] - lon) ** 2) + ((pcoords[:, 1] - lat) ** 2))
        out.append(float(d.min()))
    return out


def compute_surface(tract_base, providers, label):
    tracts = tract_base.copy()
    counts = providers.groupby("tract_id").agg(
        providers=("prov_id", "count"),
        provider_time_weight_sum=("time_weight", "sum"),
        avg_provider_time_weight=("time_weight", "mean"),
    ).reset_index()
    tracts = tracts.merge(counts, on="tract_id", how="left")
    tracts["providers"] = tracts["providers"].fillna(0).astype(int)
    tracts["provider_time_weight_sum"] = tracts["provider_time_weight_sum"].fillna(0.0)
    tracts["avg_provider_time_weight"] = tracts["avg_provider_time_weight"].fillna(0.0)
    tracts["density"] = tracts["provider_time_weight_sum"] / tracts["population"].replace(0, np.nan)
    tracts["z_density"] = -zscore(tracts["density"])
    tracts["min_dist"] = min_dist_to_providers(tracts, providers)
    tracts["inv_dist"] = 1 / (tracts["min_dist"] + 0.1)
    tracts["z_access"] = zscore(tracts["inv_dist"])
    tracts["FI"] = -tracts["z_access"]
    tracts["FI2"] = tracts["FI"] + tracts["z_density"]
    tracts["fragmentation_index"] = zscore(tracts["FI2"])
    tracts["FI_combined"] = tracts["fragmentation_index"]
    tracts["surface_version"] = label
    return tracts


def build_corrected_providers():
    providers = pd.read_stata(PROVIDERS)
    providers = providers.rename(columns={"lat": "lat", "lon": "lon"})
    providers["source"] = "nys_health_facility_provider_layer"
    providers["cms_facility_id"] = ""
    providers["name_norm"] = providers["facilityname"].map(norm_name)
    providers["prov_id"] = pd.to_numeric(providers["prov_id"], errors="coerce")
    max_id = int(providers["prov_id"].max())

    cms = pd.read_csv(CMS_UNIVERSE, dtype=str)
    cms["name_norm"] = cms["facility_name"].map(norm_name)
    audit = []
    used_provider_idx = set()
    for _, h in cms.iterrows():
        fid = h["facility_id"]
        mode = CMS_PROVIDER_MATCHES.get(fid, "exact_or_nearest")
        hx, hy = float(h["_CX"]), float(h["_CY"])
        exact = providers[providers["name_norm"].eq(h["name_norm"])]
        selected_idx = None
        method = "added_cms_acute_hospital"
        if mode != "add_cms":
            if len(exact):
                exact = exact.assign(_dist=np.sqrt((exact["lon"] - hx) ** 2 + (exact["lat"] - hy) ** 2))
                selected_idx = exact.sort_values("_dist").index[0]
                method = "matched_existing_provider_by_name"
            else:
                providers["_dist"] = np.sqrt((providers["lon"] - hx) ** 2 + (providers["lat"] - hy) ** 2)
                nearest = providers.sort_values("_dist").iloc[0]
                if float(nearest["_dist"]) <= 0.0025:
                    selected_idx = nearest.name
                    method = "matched_existing_provider_by_distance"
        if selected_idx is not None and selected_idx not in used_provider_idx:
            used_provider_idx.add(selected_idx)
            old_weight = providers.at[selected_idx, "time_weight"]
            old_name = providers.at[selected_idx, "facilityname"]
            old_category = providers.at[selected_idx, "provider_category"]
            providers.at[selected_idx, "facilityid"] = fid
            providers.at[selected_idx, "facilityname"] = h["facility_name"]
            providers.at[selected_idx, "facilitycounty"] = h["county"].title()
            providers.at[selected_idx, "lat"] = hy
            providers.at[selected_idx, "lon"] = hx
            providers.at[selected_idx, "provider_category"] = "CMS acute-care hospital"
            providers.at[selected_idx, "hours_week"] = 168.0
            providers.at[selected_idx, "time_weight"] = 1.0
            providers.at[selected_idx, "source"] = "cms_acute_hospital_corrected_existing_provider"
            providers.at[selected_idx, "cms_facility_id"] = fid
            audit.append({
                "facility_id": fid,
                "facility_name": h["facility_name"],
                "action": method,
                "old_provider_name": old_name,
                "old_category": old_category,
                "old_time_weight": old_weight,
                "new_time_weight": 1.0,
            })
        else:
            max_id += 1
            new_row = {
                "facilityid": fid,
                "facilityname": h["facility_name"],
                "facilitycounty": h["county"].title(),
                "lat": hy,
                "lon": hx,
                "prov_id": float(max_id),
                "provider_category": "CMS acute-care hospital",
                "hours_week": 168.0,
                "time_weight": 1.0,
                "source": "cms_acute_hospital_added",
                "cms_facility_id": fid,
                "name_norm": h["name_norm"],
            }
            providers = pd.concat([providers, pd.DataFrame([new_row])], ignore_index=True)
            audit.append({
                "facility_id": fid,
                "facility_name": h["facility_name"],
                "action": "added_cms_acute_hospital",
                "old_provider_name": "",
                "old_category": "",
                "old_time_weight": "",
                "new_time_weight": 1.0,
            })
    return providers.drop(columns=[c for c in ["_dist"] if c in providers.columns]), pd.DataFrame(audit)


def main():
    released = pd.read_csv(TRACT_FULL, dtype={"tract_id": str})
    tract_base = released[["population", "tract_id", "poverty_rate", "income", "lat_t", "lon_t"]].copy()
    tract_index = make_tract_index()

    providers = pd.read_stata(PROVIDERS)
    p2t = pd.read_stata(PROVIDER_TO_TRACT)
    p2t["prov_id"] = pd.to_numeric(p2t["prov_id"], errors="coerce")
    p2t["tract_id"] = p2t["tract_id"].astype(str)
    providers["prov_id"] = pd.to_numeric(providers["prov_id"], errors="coerce")
    providers = providers.merge(p2t, on="prov_id", how="left")
    providers["tract_id"] = providers["tract_id"].astype(str)
    providers_audit = providers[["facilityid", "facilityname", "facilitycounty", "lat", "lon", "prov_id", "provider_category", "hours_week", "time_weight", "tract_id"]].copy()

    replicated = released.copy()
    replicated["replication_check_FI"] = -zscore(replicated["inv_dist"])
    replicated["replication_check_z_density"] = -zscore(replicated["density"])
    replicated["replication_check_FI2"] = replicated["replication_check_FI"] + replicated["replication_check_z_density"]
    replicated["replication_check_fragmentation_index"] = zscore(replicated["replication_check_FI2"])
    rep_summary = pd.DataFrame([
        ["released_rows", len(released)],
        ["max_abs_diff_FI", float((replicated["FI"] - replicated["replication_check_FI"]).abs().max())],
        ["max_abs_diff_z_density", float((replicated["z_density"] - replicated["replication_check_z_density"]).abs().max())],
        ["max_abs_diff_FI2", float((replicated["FI2"] - replicated["replication_check_FI2"]).abs().max())],
        ["max_abs_diff_fragmentation_index", float((replicated["FI_combined"] - replicated["replication_check_fragmentation_index"]).abs().max())],
    ], columns=["metric", "value"])

    corrected_providers, cms_audit = build_corrected_providers()
    corrected_providers["tract_id"] = [
        tract_for_point(float(lon), float(lat), tract_index) if pd.notna(lon) and pd.notna(lat) else ""
        for lon, lat in zip(corrected_providers["lon"], corrected_providers["lat"])
    ]
    corrected_providers = corrected_providers[corrected_providers["tract_id"].ne("")]
    corrected = compute_surface(tract_base, corrected_providers, "HFI_v1_1_corrected_actual_provider_density_cms_acute_enforced")

    released_compare = released[["tract_id", "FI_combined"]].rename(columns={"FI_combined": "released_fragmentation_index"})
    corrected = corrected.merge(released_compare, on="tract_id", how="left")
    corrected["change_from_released"] = corrected["fragmentation_index"] - corrected["released_fragmentation_index"]
    corrected["abs_change_from_released"] = corrected["change_from_released"].abs()

    providers_audit.to_csv(BASE / "provider_layer_original_audit.csv", index=False)
    corrected_providers.to_csv(BASE / "provider_layer_corrected_cms_acute_enforced.csv", index=False)
    cms_audit.to_csv(BASE / "cms_acute_hospital_provider_corrections_audit.csv", index=False)
    replicated.to_csv(BASE / "released_hfi_surface_replication_audit.csv", index=False)
    rep_summary.to_csv(BASE / "released_hfi_surface_replication_summary.csv", index=False)
    corrected.to_csv(BASE / "hfi_tract_surface_v1_1_corrected.csv", index=False)

    summary = pd.DataFrame([
        ["corrected_provider_rows", len(corrected_providers)],
        ["corrected_tract_rows", len(corrected)],
        ["tracts_with_any_provider", int((corrected["providers"] > 0).sum())],
        ["tracts_with_no_provider", int((corrected["providers"] == 0).sum())],
        ["mean_abs_change_from_released", corrected["abs_change_from_released"].mean()],
        ["median_abs_change_from_released", corrected["abs_change_from_released"].median()],
        ["max_abs_change_from_released", corrected["abs_change_from_released"].max()],
        ["correlation_with_released", corrected["fragmentation_index"].corr(corrected["released_fragmentation_index"])],
    ], columns=["metric", "value"])
    summary.to_csv(BASE / "hfi_v1_1_rebuild_summary.csv", index=False)
    print(rep_summary.to_string(index=False))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
