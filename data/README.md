# HFI v1 data folder

This folder contains the official data inputs used by the current HFI Explorer build.

## Source files

- `hfi_tract_data.csv` — tract-level HFI values and provider-time metrics.
- `nytracts_shp.csv` — original coordinate export used to reconstruct tract polygons. Not included in the GitHub web-upload package because it exceeds GitHub's 25 MB browser upload limit.
- `hfi_hospitals.csv` — linked hospital/HCAHPS validation file.

## Browser-ready derived file

- `hfi_tracts.geojson` — generated from `hfi_tract_data.csv` and `nytracts_shp.csv` for fast Leaflet rendering.

The original CSV files are preserved for transparency and download. The GeoJSON file is derived only to make the public web explorer faster and easier to maintain.
