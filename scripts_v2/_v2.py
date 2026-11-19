"""Módulo comum do fluxo V2 (download direto, sem tasks do Google Earth Engine).

Todos os scripts V2 importam este módulo e são independentes entre si: cada um baixa o que precisa
(inclusive a área de estudo, se ainda não existir) e grava em <BASE>/<pasta>/.
Limite espacial: zona costeira do Estado da Bahia (faixa terrestre de DIST_TERRA_KM e faixa marinha de
DIST_MAR_KM a partir da linha de costa do IBGE), dividida nos setores S1–S6.
"""
import json
import math
import os
import sys
import time

import numpy as np
import requests

REPO = os.environ.get("COASTSHIFT_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.environ.get("COASTSHIFT_V2_BASE", os.path.join(os.path.dirname(REPO), "dados_bahia_v2"))
CRS = "EPSG:31984"          # SIRGAS 2000 / UTM 24S
RES = 30.0                  # m
DIST_TERRA_KM = 15.0
DIST_MAR_KM = 5.0
UA = {"User-Agent": "CoastShift-V2/1.0 (pesquisa academica)"}

# Setores (mesmos do fluxo V1). ponto_mar = ponto offshore para ondas/maré; aberta = costa exposta a ondas.
SETORES = {
    "S1_Litoral_Norte":          {"bbox": [-38.40, -12.95, -37.30, -11.40], "ponto_mar": [-37.90, -12.40], "aberta": True,  "declividade_praia": 0.05},
    "S2_Salvador_BTS":           {"bbox": [-39.00, -13.15, -38.30, -12.50], "ponto_mar": [-38.50, -13.10], "aberta": False, "declividade_praia": 0.03},
    "S3_Baixo_Sul":              {"bbox": [-39.30, -14.20, -38.80, -13.15], "ponto_mar": [-38.80, -13.70], "aberta": False, "declividade_praia": 0.03},
    "S4_Costa_do_Cacau":         {"bbox": [-39.30, -15.75, -38.80, -14.20], "ponto_mar": [-38.90, -15.00], "aberta": True,  "declividade_praia": 0.04},
    "S5_Costa_do_Descobrimento": {"bbox": [-39.40, -17.05, -38.75, -15.75], "ponto_mar": [-38.90, -16.40], "aberta": True,  "declividade_praia": 0.04},
    "S6_Costa_das_Baleias":      {"bbox": [-39.80, -18.40, -39.00, -17.05], "ponto_mar": [-39.00, -17.80], "aberta": True,  "declividade_praia": 0.03},
}
SALVADOR = (-38.5172, -12.9739)   # marégrafo UHSLC 708 / RMPG SAL


# ----------------------------------------------------------------------------- utilidades
def p(*parts):
    """Caminho dentro de BASE (cria a pasta-mãe)."""
    f = os.path.join(BASE, *parts)
    os.makedirs(os.path.dirname(f) if os.path.splitext(f)[1] else f, exist_ok=True)
    return f


def log(*a):
    msg = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(msg, flush=True)
    with open(p("logs", "download_v2.log"), "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


def download(url, dest, headers=None, retries=4, quiet_404=False):
    """Baixa com retomada e repetição. Pula se o arquivo completo já existe. Retorna o caminho ou None (404)."""
    h = dict(UA, **(headers or {}))
    for k in range(retries):
        try:
            size = None
            hd = requests.head(url, headers=h, timeout=60, allow_redirects=True)
            if hd.status_code == 404:
                if not quiet_404:
                    log("404:", url)
                return None
            if hd.ok and hd.headers.get("Content-Length"):
                size = int(hd.headers["Content-Length"])
            if os.path.exists(dest) and (size is None or os.path.getsize(dest) == size):
                return dest
            part = dest + ".part"
            pos = os.path.getsize(part) if os.path.exists(part) else 0
            hh = dict(h, Range=f"bytes={pos}-") if pos else h
            with requests.get(url, headers=hh, stream=True, timeout=120, allow_redirects=True) as r:
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                mode = "ab" if pos and r.status_code == 206 else "wb"
                with open(part, mode) as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
            os.replace(part, dest)
            log(f"ok {os.path.basename(dest)} ({os.path.getsize(dest) / 1e6:.1f} MB)")
            return dest
        except Exception as e:  # noqa: BLE001
            log(f"tentativa {k + 1}/{retries} falhou: {url} -> {e}")
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"falha ao baixar {url}")


def get_json(url, params=None, headers=None, method="GET", body=None, retries=6):
    for k in range(retries):
        try:
            r = requests.request(method, url, params=params, json=body, headers=dict(UA, **(headers or {})), timeout=300)
            if r.status_code == 429:                       # limite de requisições: espera mais
                log(f"429 (limite) em {url}; aguardando {60 * (k + 1)} s")
                time.sleep(60 * (k + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            log(f"tentativa {k + 1}/{retries}: {url} -> {e}")
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"falha em {url}")


def salvar_json(obj, *parts):
    f = p(*parts)
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False, default=float)
    log("gravado", f)
    return f


# ----------------------------------------------------------------------------- área de estudo
def aoi(force=False):
    """Retorna (gdf_aoi, gdf_setores) em EPSG:4326. Constrói a partir das malhas do IBGE se necessário."""
    import geopandas as gpd
    from shapely.geometry import box, shape
    from shapely.ops import unary_union

    fa, fs = p("aoi", "aoi_costa_bahia.geojson"), p("aoi", "setores_costa_bahia.geojson")
    if os.path.exists(fa) and os.path.exists(fs) and not force:
        return gpd.read_file(fa), gpd.read_file(fs)
    log("construindo a zona costeira da Bahia a partir das malhas do IBGE…")
    api = "https://servicodados.ibge.gov.br/api/v3/malhas/{}"
    prm = {"formato": "application/vnd.geo+json", "qualidade": "maxima"}
    ba = get_json(api.format("estados/29"), prm)
    br = get_json(api.format("paises/BR"), prm)
    salvar_json(ba, "aoi", "ibge_bahia.geojson")
    g_ba = gpd.GeoSeries([unary_union([shape(f["geometry"]) for f in ba["features"]])], crs=4326).to_crs(CRS)
    g_br = gpd.GeoSeries([unary_union([shape(f["geometry"]) for f in br["features"]])], crs=4326).to_crs(CRS)
    ba_u, br_u = g_ba.iloc[0], g_br.iloc[0]
    costa = br_u.boundary.intersection(ba_u.buffer(2000))             # linha de costa da Bahia
    terra = ba_u.intersection(costa.buffer(DIST_TERRA_KM * 1000))
    mar = costa.buffer(DIST_MAR_KM * 1000).difference(br_u)
    zona = unary_union([terra, mar]).buffer(0)
    gpd.GeoDataFrame({"nome": ["linha_costa_bahia"]}, geometry=[costa], crs=CRS).to_crs(4326).to_file(
        p("aoi", "linha_costa_bahia.geojson"), driver="GeoJSON")
    g_aoi = gpd.GeoDataFrame({"nome": ["zona_costeira_bahia"], "area_km2": [zona.area / 1e6]}, geometry=[zona], crs=CRS)
    rows = []
    for nome, s in SETORES.items():
        b = gpd.GeoSeries([box(*s["bbox"])], crs=4326).to_crs(CRS).iloc[0]
        geo = zona.intersection(b)
        rows.append({"setor": nome, "area_km2": geo.area / 1e6, "aberta": s["aberta"], "geometry": geo})
    g_set = gpd.GeoDataFrame(rows, crs=CRS)
    g_aoi.to_crs(4326).to_file(fa, driver="GeoJSON")
    g_set.to_crs(4326).to_file(fs, driver="GeoJSON")
    log(f"zona costeira: {zona.area / 1e6:.0f} km²; setores: " +
        ", ".join(f"{r['setor']}={r['area_km2']:.0f}" for r in rows))
    return g_aoi.to_crs(4326), g_set.to_crs(4326)


def aoi_bounds_ll(pad=0.02):
    g, _ = aoi()
    x0, y0, x1, y1 = g.total_bounds
    return x0 - pad, y0 - pad, x1 + pad, y1 + pad


def grade_setor(setor):
    """Perfil rasterio (EPSG:31984, 30 m) do setor e máscara booleana da zona costeira."""
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.transform import from_origin
    _, gs = aoi()
    geo = gs[gs.setor == setor].to_crs(CRS).geometry.iloc[0]
    x0, y0, x1, y1 = geo.bounds
    x0, y0 = math.floor(x0 / RES) * RES, math.floor(y0 / RES) * RES
    x1, y1 = math.ceil(x1 / RES) * RES, math.ceil(y1 / RES) * RES
    w, h = int((x1 - x0) / RES), int((y1 - y0) / RES)
    prof = {"driver": "GTiff", "width": w, "height": h, "count": 1, "crs": rasterio.crs.CRS.from_string(CRS),
            "transform": from_origin(x0, y1, RES, RES), "compress": "deflate", "tiled": True,
            "blockxsize": 512, "blockysize": 512, "BIGTIFF": "IF_SAFER"}
    mask = ~geometry_mask([geo], (h, w), prof["transform"])
    return prof, mask


def reprojetar_para_setores(fontes, pasta, prefixo, resampling="bilinear", dtype="float32", nodata=-9999.0,
                            transform_fn=None, src_nodata=None, setores=None):
    """Reprojeta uma ou mais fontes (caminhos GDAL, inclusive /vsizip/) para a grade de cada setor.

    transform_fn(arr, src_dataset, window) -> arr permite converter valores antes (ex.: densidade de população).
    Grava <BASE>/<pasta>/<prefixo>_<setor>.tif. Retorna a lista de arquivos.
    """
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject, transform_bounds
    from rasterio.windows import from_bounds

    rs = getattr(Resampling, resampling)
    out = []
    for setor in setores or SETORES:
        prof, mask = grade_setor(setor)
        dst = np.full((prof["height"], prof["width"]), np.nan, "float32")
        b_ll = transform_bounds(CRS, "EPSG:4326", *_bounds(prof), densify_pts=21)
        for f in fontes:
            with rasterio.open(f) as src:
                sb = transform_bounds("EPSG:4326", src.crs, *b_ll, densify_pts=21)
                if sb[0] > src.bounds.right or sb[2] < src.bounds.left or sb[1] > src.bounds.top or sb[3] < src.bounds.bottom:
                    continue
                win = from_bounds(*sb, transform=src.transform).round_offsets().round_lengths()
                win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
                pad = 4
                win = rasterio.windows.Window(max(win.col_off - pad, 0), max(win.row_off - pad, 0),
                                              min(win.width + 2 * pad, src.width - max(win.col_off - pad, 0)),
                                              min(win.height + 2 * pad, src.height - max(win.row_off - pad, 0)))
                arr = src.read(1, window=win).astype("float32")
                nd = src_nodata if src_nodata is not None else src.nodata
                if nd is not None:
                    arr[arr == nd] = np.nan
                if transform_fn is not None:
                    arr = transform_fn(arr, src, win)
                tmp = np.full_like(dst, np.nan)
                reproject(arr, tmp, src_transform=src.window_transform(win), src_crs=src.crs, src_nodata=np.nan,
                          dst_transform=prof["transform"], dst_crs=prof["crs"], dst_nodata=np.nan, resampling=rs)
                sel = np.isnan(dst) & np.isfinite(tmp)
                dst[sel] = tmp[sel]
        dst[~mask] = np.nan
        f_out = p(pasta, f"{prefixo}_{setor}.tif")
        pr = dict(prof, dtype=dtype, nodata=nodata)
        with rasterio.open(f_out, "w", **pr) as d:
            d.write(np.where(np.isfinite(dst), dst, nodata).astype(dtype), 1)
        val = np.isfinite(dst).sum()
        log(f"{os.path.basename(f_out)}: {prof['width']}x{prof['height']} px, {val / max(mask.sum(), 1):.0%} da zona com dado")
        out.append(f_out)
    return out


def _bounds(prof):
    t, w, h = prof["transform"], prof["width"], prof["height"]
    return t.c, t.f + h * t.e, t.c + w * t.a, t.f


# ----------------------------------------------------------------------------- séries de maré (UHSLC)
def serie_uhslc(uid=708, versoes=("b",), fast=True):
    """Série horária UHSLC (m, zero da estação), combinando research-quality e fast-delivery. Baixa se preciso."""
    import pandas as pd
    parts = []
    for v in versoes:
        f = download(f"https://uhslc.soest.hawaii.edu/data/csv/rqds/atlantic/hourly/h{uid}{v}.csv", p("mares", f"uhslc_h{uid}{v}_rq.csv"))
        if f:
            parts.append(("rq", f))
    if fast:
        f = download(f"https://uhslc.soest.hawaii.edu/data/csv/fast/hourly/h{uid}.csv", p("mares", f"uhslc_h{uid}_fd.csv"), quiet_404=True)
        if f:
            parts.append(("fd", f))
    ss = []
    for kind, f in parts:
        d = pd.read_csv(f, header=None, names=["y", "m", "d", "h", "mm"])
        t = pd.to_datetime(dict(year=d.y, month=d.m, day=d.d, hour=d.h))
        s = pd.Series(d.mm.where(d.mm > -30000).values / 1000.0, index=t, name=kind)
        ss.append(s)
    if not ss:
        raise RuntimeError("série UHSLC indisponível")
    s = ss[0]
    for extra in ss[1:]:
        s = s.combine_first(extra)          # research-quality tem prioridade
    return s.sort_index().asfreq("h")


CONST = {"M2": 28.9841042, "S2": 30.0, "N2": 28.4397295, "K2": 30.0821373, "K1": 15.0410686, "O1": 13.9430356,
         "P1": 14.9589314, "Q1": 13.3986609, "M4": 57.9682084, "MS4": 58.9841042, "MN4": 57.4238337, "M6": 86.9523127,
         "Sa": 0.0410686, "Ssa": 0.0821373}


def harmonicos(s, nomes=None):
    """Ajuste harmônico por mínimos quadrados (sem correções nodais; adequado a séries ≥ 1 ano)."""
    nomes = nomes or list(CONST)
    t = (s.index - s.index[0]).total_seconds().values / 3600.0
    ok = np.isfinite(s.values)
    cols = [np.ones(ok.sum()), t[ok] / 8766.0]
    for n in nomes:
        w = np.deg2rad(CONST[n])
        cols += [np.cos(w * t[ok]), np.sin(w * t[ok])]
    A = np.column_stack(cols)
    c, *_ = np.linalg.lstsq(A, s.values[ok], rcond=None)
    amp = {n: float(np.hypot(c[2 + 2 * i], c[3 + 2 * i])) for i, n in enumerate(nomes)}
    fase = {n: float(np.rad2deg(np.arctan2(c[3 + 2 * i], c[2 + 2 * i])) % 360) for i, n in enumerate(nomes)}

    def prever(idx):
        tt = (idx - s.index[0]).total_seconds().values / 3600.0
        y = np.zeros(len(tt))
        for n in nomes:
            if n in ("Sa", "Ssa"):
                continue
            y += amp[n] * np.cos(np.deg2rad(CONST[n]) * tt - np.deg2rad(fase[n]))
        return y
    return amp, fase, float(c[1]), prever


def ajustar_gpd(exc):
    from scipy.stats import genpareto
    xi, _, sc = genpareto.fit(exc, floc=0)
    return float(xi), float(sc)
