"""13 — Superfícies de referência vertical para a harmonização (métodos §5.1, Eqs. 1–3).
- EGM2008 (NGA; grade 2,5' da PROJ CDN us_nga_egm08_25.tif): ondulação N para h = H_EGM08 + N.
- hgeoHNOR2020 (IBGE): grade de conversão entre altitude elipsoidal e altitude normal do SGB, datum Imbituba
  (válido para a Bahia): HN = h − η. Download do geoftp do IBGE (grades-IMBITUBA.zip).
Saídas: <BASE>/geoide/egm08_N_bahia.tif, hgeohnor2020_eta_bahia.tif (EPSG:4326, recorte da zona costeira)
"""
import os
import zipfile

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import from_bounds

import _v2

EGM = "https://cdn.proj.org/us_nga_egm08_25.tif"
HGEO = ("https://geoftp.ibge.gov.br/modelos_digitais_de_superficie/modelo_de_ondulacao_geoidal/"
        "grades_hgeoHNOR2020/hgeoHNOR2020__grades-IMBITUBA.zip")


def recortar(src_path, dest, bounds):
    with rasterio.open(src_path) as s:
        w = from_bounds(*bounds, transform=s.transform).round_offsets().round_lengths()
        a = s.read(1, window=w)
        prof = dict(s.profile, driver="GTiff", width=a.shape[1], height=a.shape[0], transform=s.window_transform(w),
                    compress="deflate")
        prof.pop("blockxsize", None), prof.pop("blockysize", None), prof.pop("tiled", None)
    with rasterio.open(dest, "w", **prof) as d:
        d.write(a, 1)
    _v2.log(f"{os.path.basename(dest)}: {a.shape}, {np.nanmin(a):.2f} a {np.nanmax(a):.2f} m")


def texto_para_grade(txt, dest, bounds):
    """Lê grade em texto 'lat lon valor' ou 'lon lat valor' (formato IBGE) e grava GeoTIFF."""
    rows = []
    for ln in open(txt, encoding="latin-1"):
        parts = ln.replace(",", ".").split()
        try:
            v = [float(x) for x in parts[:3]]
        except ValueError:
            continue
        if len(v) == 3:
            rows.append(v)
    a = np.array(rows)
    # formato IBGE: "lon lat valor" com longitude 0–360 (ex.: 285.04 5.96 17.70); aceita também "lat lon valor"
    if np.abs(a[:, 0]).max() > 90:
        lon, lat = a[:, 0], a[:, 1]
    else:
        lat, lon = a[:, 0], a[:, 1]
    lon = np.where(lon > 180, lon - 360, lon)
    x0, y0, x1, y1 = bounds
    sel = (lon >= x0 - 0.2) & (lon <= x1 + 0.2) & (lat >= y0 - 0.2) & (lat <= y1 + 0.2)
    lat, lon, val = lat[sel], lon[sel], a[sel, 2]
    ux, uy = np.unique(np.round(lon, 6)), np.unique(np.round(lat, 6))
    dx, dy = np.median(np.diff(ux)), np.median(np.diff(uy))
    g = np.full((len(uy), len(ux)), np.nan, "float32")
    g[len(uy) - 1 - np.round((lat - uy[0]) / dy).astype(int), np.round((lon - ux[0]) / dx).astype(int)] = val
    prof = {"driver": "GTiff", "width": len(ux), "height": len(uy), "count": 1, "dtype": "float32", "crs": "EPSG:4326",
            "transform": from_origin(ux[0] - dx / 2, uy[-1] + dy / 2, dx, dy), "nodata": np.nan, "compress": "deflate"}
    with rasterio.open(dest, "w", **prof) as d:
        d.write(g, 1)
    _v2.log(f"{os.path.basename(dest)}: grade {g.shape}, passo {dx:.4f}°, {np.nanmin(g):.2f} a {np.nanmax(g):.2f} m")


if __name__ == "__main__":
    b = _v2.aoi_bounds_ll(pad=0.1)
    f = _v2.download(EGM, _v2.p("raw", "geoide", "us_nga_egm08_25.tif"))
    recortar(f, _v2.p("geoide", "egm08_N_bahia.tif"), b)
    z = _v2.download(HGEO, _v2.p("raw", "geoide", "hgeoHNOR2020_IMBITUBA.zip"))
    pasta = _v2.p("raw", "geoide", "hgeoHNOR2020_IMBITUBA")
    zipfile.ZipFile(z).extractall(pasta)
    arqs = [os.path.join(r, n) for r, _, ns in os.walk(pasta) for n in ns]
    _v2.log("hgeoHNOR2020 conteúdo:", [os.path.relpath(a, pasta) for a in arqs][:20])
    feito = False
    for a in sorted(arqs, key=lambda x: (not x.lower().endswith((".tif", ".gtx", ".grd", ".asc")), x)):
        try:
            if a.lower().endswith((".tif", ".gtx", ".grd", ".asc", ".img")):
                recortar(a, _v2.p("geoide", "hgeohnor2020_eta_bahia.tif"), b)
            elif a.lower().endswith((".txt", ".dat", ".xyz", ".csv")):
                texto_para_grade(a, _v2.p("geoide", "hgeohnor2020_eta_bahia.tif"), b)
            else:
                continue
            _v2.log("hgeoHNOR2020 usado:", os.path.basename(a))
            feito = True
            break
        except Exception as e:  # noqa: BLE001
            _v2.log(f"não lido {os.path.basename(a)}: {e}")
    if not feito:
        _v2.log("AVISO: grade hgeoHNOR2020 não reconhecida; o script 20 usará N(EGM2008) como aproximação.")
