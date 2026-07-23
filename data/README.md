# HFI Explorer data

This folder contains the GitHub Pages-ready data release for the HFI Explorer.

- `hfi_tract_data.csv` — full v1.1 tract-level HFI web-release data, 2,229 mapped NYC tracts.
- `hfi_tracts.geojson` — browser-ready tract geometry and HFI attributes for Leaflet.
- `hfi_tracts.js` — embedded JavaScript version of the tract map layer.
- `hfi_hospitals.csv` — CMS acute-care hospital universe and HCAHPS validation data used by the Explorer, 33 CMS-listed acute-care hospitals, including 32 HCAHPS-complete validation hospitals.
- `hfi_hospitals.js` — embedded JavaScript version of the hospital CSV.

The larger raw coordinate export used to generate the GeoJSON is archived separately because GitHub's web uploader rejects individual files larger than 25 MB.
