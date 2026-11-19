"""07 — Edificações: Microsoft Global ML Building Footprints (Bing Maps; ODbL), particionado por quadkey nível 9.
Lê o índice público dataset-links.csv, baixa só as partições que intersectam a zona costeira da Bahia e
conta edificações (centróides) por célula de 30 m. Alternativa: Google Open Buildings v3 (polígonos por célula S2).
Saídas: <BASE>/raw/ms_buildings/*.csv.gz e <BASE>/exposicao/buildings_<setor>.tif (contagem por célula)
"""
import gzip
import io
import json
import math
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
import _v2

INDICE = "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"


def quadkey(x, y, z):
    q = ""
    for i in range(z, 0, -1):
        d = 0
        m = 1 << (i - 1)
        if x & m:
            d += 1
        if y & m:
            d += 2
        q += str(d)
    return q


def tile_xy(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


if __name__ == "__main__":
    from shapely.geometry import box
    g, _ = _v2.aoi()
    zona = g.geometry.iloc[0]
    x0, y0, x1, y1 = _v2.aoi_bounds_ll()
    z = 9
    (tx0, ty0), (tx1, ty1) = tile_xy(x0, y1, z), tile_xy(x1, y0, z)
    qks = set()
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            n = 2 ** z
            lo0, lo1 = tx / n * 360 - 180, (tx + 1) / n * 360 - 180
            la0 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + 1) / n))))
            la1 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
            if zona.intersects(box(lo0, la0, lo1, la1)):
                qks.add(quadkey(tx, ty, z))
    idx = pd.read_csv(_v2.download(INDICE, _v2.p("raw", "ms_buildings", "dataset-links.csv")), dtype=str)
    sel = idx[(idx.Location == "Brazil") & idx.QuadKey.isin(qks)]
    _v2.log(f"MS Buildings: {len(qks)} quadkeys na zona, {len(sel)} arquivos")
    tr = Transformer.from_crs("EPSG:4326", _v2.CRS, always_xy=True)
    xs, ys = [], []
    for _, r in sel.iterrows():
        f = _v2.download(r.Url, _v2.p("raw", "ms_buildings", f"{r.QuadKey}_{r.Url.split('/')[-1]}"))
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    geo = json.loads(line)["geometry"]["coordinates"][0]
                except Exception:  # noqa: BLE001
                    continue
                a = np.asarray(geo)
                xs.append(a[:, 0].mean())
                ys.append(a[:, 1].mean())
    X, Y = tr.transform(np.array(xs), np.array(ys))
    _v2.log(f"MS Buildings: {len(X):,} edificações lidas")
    for setor in _v2.SETORES:
        prof, mask = _v2.grade_setor(setor)
        t = prof["transform"]
        col = ((X - t.c) / t.a).astype(int)
        row = ((Y - t.f) / t.e).astype(int)
        ok = (col >= 0) & (col < prof["width"]) & (row >= 0) & (row < prof["height"])
        cnt = np.zeros((prof["height"], prof["width"]), "float32")
        np.add.at(cnt, (row[ok], col[ok]), 1)
        cnt[~mask] = np.nan
        with rasterio.open(_v2.p("exposicao", f"buildings_{setor}.tif"), "w", **dict(prof, dtype="float32", nodata=-9999.0)) as d:
            d.write(np.where(np.isfinite(cnt), cnt, -9999.0).astype("float32"), 1)
        _v2.log(f"  buildings_{setor}: {np.nansum(cnt):,.0f} edificações")
