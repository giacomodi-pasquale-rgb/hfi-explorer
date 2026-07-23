# HFI Explorer deployment checklist

## Local test

From the unzipped site folder:

```bash
python3 -m http.server 8000
```

Open:

```text
http://localhost:8000/explorer.html?v=6
```

## GitHub Pages deployment

1. Create a GitHub repository, for example `hfi-explorer`.
2. Upload the *contents* of this folder to the repository root. Do not upload the outer ZIP as a single file.
3. Confirm these paths exist in GitHub:
   - `index.html`
   - `explorer.html`
   - `assets/css/style.css`
   - `assets/js/explorer.js`
   - `data/hfi_tracts.geojson`
   - `data/hfi_hospitals.csv`
4. Go to **Settings → Pages**.
5. Under **Build and deployment**, choose:
   - Source: **Deploy from a branch**
   - Branch: **main**
   - Folder: **/root**
6. Save.
7. Wait for the Pages deployment to finish.
8. Open the URL GitHub gives you, usually:

```text
https://<username>.github.io/hfi-explorer/
```

## Custom domain later

When ready for `hfi-index.org`:

1. In GitHub Pages settings, add `hfi-index.org` as the custom domain.
2. Rename `CNAME.example` to `CNAME` and put only this line inside it:

```text
hfi-index.org
```

3. In your domain registrar DNS, add the GitHub Pages records requested by GitHub.
4. Turn on **Enforce HTTPS** once GitHub allows it.

## Common problems

- If `localhost:8000` does not open, the local server is not running or Terminal is in the wrong folder.
- If the map loads but data does not, check that `/data/hfi_tracts.geojson` and `/data/hfi_hospitals.csv` are present.
- If GitHub Pages shows a 404, wait a few minutes and confirm that `index.html` is at the repository root.
