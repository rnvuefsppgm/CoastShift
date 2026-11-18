# %% [markdown]
# # 10 — Harmonização vertical: EGM2008 → elipsoide → altitude normal SGB (hgeoHNOR2020) → NMM local
# Eqs. 1–3 do documento de métodos:
#   h  = H_EGM08 + N_EGM08                (pyproj; grade us_nga_egm08_25 da PROJ CDN)
#   HN = h − η_hgeoHNOR2020               (IBGE, 2021/2023)
#   z  = HN − NMM_SGB(local)              (nível médio local em altitude normal, via marégrafo RMPG ↔ RN)
# Entradas: GeoTIFFs dos scripts 03 em <BASE>/gee/ (ou na pasta do Drive), tiles ANADEM opcionais em anadem_tiles/,
# grade η do IBGE em hgeohnor/ (GeoTIFF ou texto 'lon lat eta [sigma]'). Sem a grade, usa-se ETA_CONST (aviso!).
# Saída: <BASE>/gee/dem_<fonte>_<setor>_nmm.tif

# %%
import glob
import os
import sys

import numpy as np
import rasterio
from pyproj import Transformer, network
from rasterio.merge import merge
from rasterio.warp import Resampling, reproject

if "google.colab" in sys.modules:
    sys.path.insert(0, "/content/CoastShift/scripts")
from _comum import load_config, path, IN_COLAB, ondulacao_egm08, eta_hgeohnor

cfg = load_config()
network.set_network_enabled(True)
ETA_CONST = None   # use só se não houver grade hgeoHNOR2020 (m)
NMM_SGB = cfg.get("nmm_salvador_sgb_m")
GEE_DIRS = [path("gee")] + ([f"/content/drive/MyDrive/{cfg['drive_folder']}"] if IN_COLAB else [])


def achar(nome):
    for d in GEE_DIRS:
        f = sorted(glob.glob(os.path.join(d, nome + "*.tif")))
        if f:
            return f
    return []


def grade_lonlat(prof):
    ny, nx = prof["height"], prof["width"]
    cols, rows = np.meshgrid(np.arange(nx), np.arange(ny))
    xs, ys = rasterio.transform.xy(prof["transform"], rows.ravel(), cols.ravel(), offset="center")
    lon, lat = Transformer.from_crs(prof["crs"], "EPSG:4326", always_xy=True).transform(np.array(xs), np.array(ys))
    return np.asarray(lon).reshape(ny, nx), np.asarray(lat).reshape(ny, nx)


def mosaico_anadem(prof):
    tiles = glob.glob(path("anadem_tiles", "*.tif"))
    if not tiles:
        return None
    srcs = [rasterio.open(t) for t in tiles]
    arr, tr = merge(srcs)
    dst = np.full((prof["height"], prof["width"]), np.nan, "float32")
    reproject(arr[0], dst, src_transform=tr, src_crs=srcs[0].crs, src_nodata=srcs[0].nodata, dst_transform=prof["transform"],
              dst_crs=prof["crs"], dst_nodata=np.nan, resampling=Resampling.bilinear)
    return dst


# %%
if NMM_SGB is None:
    print("AVISO: nmm_salvador_sgb_m ausente no config — z ficará relativo ao datum SGB (Imbituba), não ao NMM local.")
for nome in cfg["setores"]:
    ref = achar(f"dem_cop_{nome}")
    if not ref:
        print("sem DEM Copernicus para", nome)
        continue
    with rasterio.open(ref[0]) as src:
        prof = src.profile.copy()
    lon, lat = grade_lonlat(prof)
    N = ondulacao_egm08(lon, lat)
    eta = eta_hgeohnor(lon, lat, ETA_CONST)
    corr = N - eta - (NMM_SGB or 0.0)     # z = H_EGM08 + N − η − NMM
    fontes = {f: achar(f"dem_{f}_{nome}") for f in ("cop", "fabdem", "anadem")}
    for f, arqs in fontes.items():
        if arqs:
            with rasterio.open(arqs[0]) as src:
                H = src.read(1).astype("float32")
                if src.nodata is not None:
                    H[H == src.nodata] = np.nan
        elif f == "anadem":
            H = mosaico_anadem(prof)
            if H is None:
                continue
        else:
            continue
        z = H + corr
        p = prof.copy()
        p.update(dtype="float32", nodata=-9999, compress="deflate")
        with rasterio.open(path("gee", f"dem_{f}_{nome}_nmm.tif"), "w", **p) as dst:
            dst.write(np.where(np.isfinite(z), z, -9999).astype("float32"), 1)
        print(nome, f, f"correção média {np.nanmean(corr):+.2f} m (N−η−NMM)")
