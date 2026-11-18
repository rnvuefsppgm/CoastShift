# %% [markdown]
# # 11 — Montar os pacotes de entrada do CoastShift (um por setor e por subdomínio)
# Junta: DEM no datum NMM local (script 10) + cobertura/água/pop/edificações (04) + AR6 (05) + marés (06)
# + extremos (07) + ondas (08) + pontos ICESat-2 convertidos ao mesmo datum (09 + Eqs. 1–3).
# Calcula o erro do DEM por classe (Eq. 11) e grava `pacotes/<nome>/params.json` + rasters alinhados.
# Formato descrito em docs/02_Formato_Pacote.md. Abra a pasta resultante na aba "1 Dados" do aplicativo.

# %%
import glob
import json
import os
import sys

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds
from scipy import ndimage

if "google.colab" in sys.modules:
    sys.path.insert(0, "/content/CoastShift/scripts")
from _comum import load_config, path, IN_COLAB, ondulacao_egm08, eta_hgeohnor, add_repo_to_path

add_repo_to_path()
from coastshift import io as csio, validation  # noqa: E402

cfg = load_config()
GEE_DIRS = [path("gee")] + ([f"/content/drive/MyDrive/{cfg['drive_folder']}"] if IN_COLAB else [])
ld = lambda f: json.load(open(path(*f), encoding="utf-8")) if os.path.exists(path(*f)) else {}  # noqa: E731
AR6, MARES, EXT, ONDAS = ld(("ar6", "ar6_setores.json")), ld(("mares", "mares_setores.json")), \
    ld(("mares", "extremos_setores.json")), ld(("ondas", "ondas_setores.json"))
ep = cfg["epoca_nmm_local"]

PADRAO = {  # parâmetros físicos padrão (editáveis no app, aba 4) — ver docs/01 §6
    "manning": {"default": 0.035, "by_class": {"24": 0.10, "5": 0.12, "3": 0.12, "9": 0.10, "33": 0.025, "23": 0.03}},
    "shoreline": {"d50_mm": 0.3, "berm_m": 2.0, "he_m": 3.0, "te_s": 10.0, "sandy_classes": [23]},
    "habitat": {"mangrove_classes": [5], "apicum_classes": [32], "barrier_classes": [24, 30, 25],
                "accretion_mm_yr": 3.0, "mangrove_min": 0.0, "mangrove_max_above_mhws": 0.0,
                "apicum_band_m": 0.3, "max_rsl_rate_mm_yr": 7.0},
    "damage": {"value_per_building": 150000.0, "people_depth_threshold": 0.15,
               "curve_depth": [0, 0.5, 1, 1.5, 2, 3, 4, 6], "curve_frac": [0, 0.25, 0.4, 0.5, 0.6, 0.75, 0.85, 1.0],
               "curve_source": "ILUSTRATIVA – substituir por Huizinga et al. (2017), América do Sul, e valores do IBGE/SINAPI"},
}


def achar(nome):
    for d in GEE_DIRS:
        f = sorted(glob.glob(os.path.join(d, nome + ".tif"))) or sorted(glob.glob(os.path.join(d, nome + "-*.tif")))
        if f:
            return f[0]
    return None


def ler_janela(f, bounds):
    with rasterio.open(f) as src:
        if bounds is None:
            return src.read(1).astype("float32"), src.profile.copy(), src.nodata
        w = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w).astype("float32")
        p = src.profile.copy()
        p.update(height=a.shape[0], width=a.shape[1], transform=src.window_transform(w))
        return a, p, src.nodata


def montar(nome, setor, bbox_ll=None):
    dem_f = next((achar(f"dem_{f}_{setor}_nmm") for f in (cfg["dem_principal"], "anadem", "fabdem", "cop")
                  if achar(f"dem_{f}_{setor}_nmm")), None)
    if dem_f is None:
        print("sem DEM convertido para", setor)
        return
    bounds = None
    if bbox_ll:
        with rasterio.open(dem_f) as src:
            t = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x0, y0 = t.transform(bbox_ll[0], bbox_ll[1])
        x1, y1 = t.transform(bbox_ll[2], bbox_ll[3])
        bounds = (x0, y0, x1, y1)
    dem, prof, nd = ler_janela(dem_f, bounds)
    dem[dem == nd] = np.nan
    out = path("pacotes", nome)
    os.makedirs(out, exist_ok=True)
    tmp_ref = os.path.join(out, "dem.tif")
    csio.write_raster(tmp_ref, dem, prof)
    lay = {}
    for k, how in [("landcover", "nearest"), ("gsw", "nearest"), ("buildings", "nearest"), ("pop", "density"), ("wbm", "nearest")]:
        f = achar(f"{k}_{setor}") or achar(f"dem_{k}_{setor}")
        if not f:
            continue
        if how == "density":  # pessoas/célula 100 m -> densidade -> pessoas/célula do DEM (Eq. 32)
            with rasterio.open(f) as src:
                a100 = abs(src.transform.a * src.transform.e)
            arr = csio.align_to(f, prof) / a100 * abs(prof["transform"].a * prof["transform"].e)
        else:
            arr = csio.align_to(f, prof)
        lay[k] = arr
    # máscara marinha/estuarina conectada ao oceano
    agua = np.zeros(dem.shape, bool)
    if "wbm" in lay:
        agua |= np.isin(lay["wbm"], [1, 3])
    if "gsw" in lay:
        agua |= lay["gsw"] >= 50
    if "landcover" in lay:
        agua |= lay["landcover"] == 33
    oceano = lay["wbm"] == 1 if "wbm" in lay else np.isnan(dem)
    lab, _ = ndimage.label(agua | oceano, structure=np.ones((3, 3)))
    sea = np.isin(lab, np.unique(lab[oceano & (lab > 0)]))
    dem[sea] = np.nan
    csio.write_raster(tmp_ref, dem, prof)
    csio.write_raster(os.path.join(out, "sea.tif"), sea.astype("float32"), prof, "uint8", 255)
    for k in ("landcover", "pop", "buildings"):
        if k in lay:
            csio.write_raster(os.path.join(out, f"{k}.tif"), np.nan_to_num(lay[k]), prof,
                              "int16" if k == "landcover" else "float32", -1 if k == "landcover" else -9999.0)
    # pontos ICESat-2 no mesmo datum (h_ref = h_elip − η − NMM)
    pts = path("icesat2", f"atl08_{setor}.csv")
    dem_error = {"default": {"bias": 0.0, "sd": 1.5}, "by_class": {}, "fonte": "padrão (sem validação)"}
    if os.path.exists(pts):
        df = pd.read_csv(pts)
        eta = eta_hgeohnor(df["lon"].values, df["lat"].values)
        df["h_ref"] = df["h_elip"] - eta - (cfg.get("nmm_salvador_sgb_m") or 0.0)
        df["x"], df["y"] = Transformer.from_crs("EPSG:4326", prof["crs"], always_xy=True).transform(df["lon"].values, df["lat"].values)
        vpath = os.path.join(out, "validacao_pontos_dem.csv")
        df.to_csv(vpath, index=False)
        lc = lay.get("landcover", np.zeros(dem.shape))
        stats, dem_error = validation.dem_vs_points(dem, prof, lc, vpath)
        stats.to_csv(os.path.join(out, "validacao_dem_por_classe.csv"), index=False)
        dem_error["fonte"] = "ICESat-2 ATL08 (script 09/11)"
        print(stats.head(8).to_string(index=False))
    dem_error["corr_length_m"] = 300.0
    w = ONDAS.get(nome, {})
    params = {
        "sector": nome, "crs": str(prof["crs"]), "dem_fonte": os.path.basename(dem_f),
        "baseline": {"center_year": (ep["inicio"] + ep["fim"]) / 2, "epoca_nmm": ep},
        "tide": {**MARES.get(nome, {"msl": 0.0, "mhws": np.nan, "mhhw": np.nan}), "amplification_factor": 1.0},
        "ar6": AR6.get(nome, {}), "vlm_extra_mm_yr": 0.0,
        "extremes": EXT.get(nome, {}),
        "waves": {"hs": w.get("hs", 0.0), "tp": w.get("tp", 0.0), "beach_slope": w.get("beach_slope", 0.0),
                  "costa_aberta": w.get("costa_aberta", False)},
        "dem_error": dem_error, **PADRAO,
    }
    with open(os.path.join(out, "params.json"), "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2, ensure_ascii=False, default=float)
    print("pacote pronto:", out, dem.shape)


# %%
for nome in cfg["setores"]:
    montar(nome, nome)
for sd, s in cfg["subdominios"].items():
    montar(sd, s["setor"], s["bbox"])
