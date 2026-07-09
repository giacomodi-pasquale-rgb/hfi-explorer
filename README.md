# HFI Explorer

Official companion website scaffold for the Healthcare Fragmentation Index research program.

This is a static, GitHub Pages-ready website designed to become the public home for the HFI project and eventual deployment at `hfi-index.org`.

## Included pages

- Home
- HFI Explorer interactive Leaflet map
- About HFI
- Publications
- Download Data
- Download Code
- Citation
- Future Versions

## Data files expected

Place the following files in `/data/`:

```text
data/hfi_tract_data.csv
data/hfi_hospitals.csv
```

The interactive map reads these files directly in the browser using PapaParse and Leaflet.

## Geometry requirements

The original `nytracts_shp.csv` coordinate export is not required for the live site because the generated `hfi_tracts.geojson` and `hfi_tracts.js` are already included. If regenerating the map layer, `nytracts_shp.csv` should contain a tract identifier column and one geometry column. The explorer can parse either:

- WKT `POLYGON` / `MULTIPOLYGON`, or
- GeoJSON geometry text.

Recommended columns:

```text
GEOID, borough, geometry
```

The script accepts common alternatives including `geoid`, `tract_geoid`, `GEOID20`, `geom`, `wkt`, and `the_geom`.

## HFI tract data requirements

Recommended columns:

```text
GEOID, hfi_v1
```

The script accepts common alternatives including `hfi`, `hfi_score`, `fragmentation`, `FI_time_space_std`, `FI_time_adjusted_std`, and `FI_complexity_std`.

## Hospital data requirements

Recommended columns:

```text
hospital_name, latitude, longitude, communication_index
```

The script accepts common alternatives including `facility_name`, `name`, `lat`, `lon`, `lng`, `_CX`, `_CY`, and `patient_experience_index`.

## Local preview

Because the explorer loads local CSV files, preview through a local server rather than opening HTML files directly.

```bash
cd hfi-explorer-site
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

## GitHub Pages deployment

1. Create a GitHub repository, for example `hfi-explorer`.
2. Upload all files in this folder.
3. Add the three CSV files to `/data/`.
4. Commit and push.
5. In GitHub, go to **Settings → Pages**.
6. Select the main branch and root folder.
7. Save.

## Custom domain

When ready to use `hfi-index.org`:

1. Rename `CNAME.example` to `CNAME`.
2. Confirm the file contains only:

```text
hfi-index.org
```

3. Configure DNS according to GitHub Pages custom domain instructions.

## Notes before public release

Before treating this as a final public research product, add:

- final author names and affiliations;
- accepted citation or preprint DOI;
- data dictionary;
- code repository link;
- license file;
- accessibility review;
- final domain DNS settings.


## Data files included

- `data/hfi_tract_data.csv` — 670 tract-level HFI records.
- `data/nytracts_shp.csv` — original coordinate export used to build tract polygons; archive separately or add via Git LFS if needed.
- `data/hfi_tracts.geojson` — browser-ready tract map layer generated from the two tract files.
- `data/hfi_hospitals.csv` — 22 linked hospital records.


## Local preview note

The Explorer now includes embedded JavaScript copies of the tract GeoJSON and hospital CSV so it can render even when opened from a local folder. For the most reliable local preview, still use a simple local server:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000/explorer.html`.


## Local testing note

Run `python3 -m http.server 8000` from inside this folder and open `http://localhost:8000/explorer.html?v=5`. Version 5 uses a fixed-grid Leaflet layout to avoid partial tile rendering during local testing.


## Version 6 notes

This release polishes the Explorer as a scientific web product:

- Stronger HFI tract symbology using a blue-to-red fragmentation scale.
- Clearer quantile legend with least-to-most fragmented interpretation.
- More visible hospital markers.
- Tract and hospital click panels.
- Reset map and Zoom to NYC buttons.
- More stable map layout for local testing and GitHub Pages.
- Deployment checklist in `docs/deployment-checklist.md`.

## Run locally

```bash
cd hfi-explorer-site-v6
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/explorer.html?v=6
```

## Publish online with GitHub Pages

Upload the contents of this folder to a GitHub repository, then enable GitHub Pages from **Settings → Pages → Deploy from branch → main → /root**. See `docs/deployment-checklist.md` for the full checklist.


## GitHub web upload note

This package excludes `data/nytracts_shp.csv` because the raw coordinate export is larger than GitHub's 25 MB browser upload limit. The live Explorer does not need that file: it reads the already-generated `data/hfi_tracts.geojson` and `data/hfi_tracts.js`.
