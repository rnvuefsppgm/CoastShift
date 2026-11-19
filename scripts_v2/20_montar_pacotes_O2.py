"""20 — Monta os pacotes de entrada do Modelo 2 (O2) por setor a partir dos downloads V2 (01–14).
(Não é um download: depende das saídas dos scripts 02–13.)

Harmonização vertical (métodos §5.1):  h = H_EGM08 + N_EGM08 ;  HN = h − η_hgeoHNOR2020 ;  z = HN − NMM_SGB(Salvador)
Máscara do mar: faixa marinha da zona costeira ∪ água JRC (ocorrência ≥ 50 %) conectada a ela.
Erro do DEM por classe MapBiomas: pontos ICESat-2 (script 12) convertidos ao mesmo datum (validation.dem_vs_points).
Parâmetros: maré (09), extremos (10, transferidos pela razão M2+S2), ondas (11), AR6 (08).

Uso: python 20_montar_pacotes_O2.py [--dem fabdem|cop30] [--nmm-sgb 0.0]
  --nmm-sgb: NMM de Salvador em altitude normal do SGB (m), do relatório da RMPG (script 14). Sem ele usa 0,0
             e grava um aviso no params.json (cotas ficam relativas ao datum de Imbituba).
Saídas: <BASE>/pacotes/<setor>/ {dem, landcover, sea, pop, buildings}.tif, params.json, validacao_pontos_dem.csv
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.warp import reproject, Resampling
from scipy import ndimage

import _v2

import sys  # noqa: E402

sys.path.insert(0, _v2.REPO)
from coastshift import validation  # noqa: E402

PADRAO = {  # usados só se a variável correspondente não tiver sido baixada/calculada
    "tide": {"msl": 0.0, "mhhw": 1.05, "mhws": 1.25, "amplification_factor": 1.0},
    "extremes": {"threshold": 1.30, "scale": 0.09, "shape": -0.10, "rate": 4.0, "scale_se": 0.01, "shape_se": 0.05},
    "waves": {"hs": 2.0, "tp": 9.0, "beach_slope": 0.04, "costa_aberta": True},
    "dem_error": {"default": {"bias": 0.3, "sd": 0.6}, "by_class": {}},
}
FIXOS = {
    "manning": {"default": 0.04, "by_class": {"24": 0.10, "5": 0.12, "3": 0.12, "33": 0.025}},
    "shoreline": {"d50_mm": 0.35, "berm_m": 2.0, "he_m": 2.8, "te_s": 10.0, "sandy_classes": [23]},
    "habitat": {"mangrove_classes": [5], "apicum_classes": [32], "barrier_classes": [24], "accretion_mm_yr": 3.0,
                "mangrove_min": 0.0, "mangrove_max_above_mhws": 0.0, "apicum_band_m": 0.3, "max_rsl_rate_mm_yr": 7.0},
    "damage": {"value_per_building": 150000.0, "people_depth_threshold": 0.15,
               "curve_depth": [0, 0.5, 1, 1.5, 2, 3, 4, 6], "curve_frac": [0, 0.25, 0.4, 0.5, 0.6, 0.75, 0.85, 1.0],
               "curve_source": "ilustrativa – substituir por Huizinga et al. (2017), América do Sul"},
}


def ler_json(*parts):
    f = os.path.join(_v2.BASE, *parts)
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else None


def ler(f):
    with rasterio.open(f) as s:
        a = s.read(1).astype("float32")
        if s.nodata is not None:
            a[a == s.nodata] = np.nan
        return a, s.profile


def superficie_na_grade(f, prof):
    """Reamostra uma grade geodésica (EPSG:4326) para a grade do setor (bilinear)."""
    dst = np.full((prof["height"], prof["width"]), np.nan, "float32")
    with rasterio.open(f) as s:
        a = s.read(1).astype("float32")
        reproject(a, dst, src_transform=s.transform, src_crs=s.crs, src_nodata=np.nan, dst_transform=prof["transform"],
                  dst_crs=prof["crs"], dst_nodata=np.nan, resampling=Resampling.bilinear)
    return dst


def amostrar(f, lon, lat):
    with rasterio.open(f) as s:
        return np.array([v[0] for v in s.sample(zip(lon, lat))], float)


def gravar(path, arr, prof, dtype="float32", nodata=-9999.0):
    with rasterio.open(path, "w", **dict(prof, dtype=dtype, nodata=nodata, count=1)) as d:
        d.write(np.where(np.isfinite(arr), arr, nodata).astype(dtype), 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="fabdem", choices=["fabdem", "cop30"])
    ap.add_argument("--saida", default="", help="pasta dos pacotes (padrão <BASE>/pacotes)")
    ap.add_argument("--nmm-sgb", type=float, default=float(os.environ.get("NMM_SALVADOR_SGB_M", "nan")))
    a = ap.parse_args()
    if np.isnan(a.nmm_sgb):                          # valor calculado pelo script 14 (RMPG/IBGE)
        j = ler_json("mares", "nmm_salvador_sgb.json")
        if j:
            a.nmm_sgb = j["nmm_sgb_m"]
            _v2.log(f"NMM_SGB do script 14: {a.nmm_sgb} m")
    nmm_sgb = 0.0 if np.isnan(a.nmm_sgb) else a.nmm_sgb
    avisos_gerais = [] if not np.isnan(a.nmm_sgb) else [
        "NMM de Salvador no SGB não informado (--nmm-sgb): cotas relativas ao datum de Imbituba (HN); "
        "informe o valor do relatório RMPG (script 14) e rode de novo."]

    import geopandas as gpd
    _, gs = _v2.aoi()
    ba = gpd.read_file(_v2.p("aoi", "ibge_bahia.geojson")).to_crs(_v2.CRS).union_all()
    f_N, f_eta = _v2.p("geoide", "egm08_N_bahia.tif"), _v2.p("geoide", "hgeohnor2020_eta_bahia.tif")
    tem_N, tem_eta = os.path.exists(f_N), os.path.exists(f_eta)
    mar_set = ler_json("mares", "mares_setores.json") or {}
    sal = ler_json("mares", "mares_salvador.json") or {}
    ext = ler_json("mares", "extremos_salvador.json")
    ond = ler_json("ondas", "ondas_setores.json") or {}
    ar6 = ler_json("ar6", "ar6_setores.json") or {}
    resumo = []
    for setor in _v2.SETORES:
        avisos = list(avisos_gerais)
        f_dem = _v2.p("dem", f"dem_{a.dem}_egm08_{setor}.tif")
        if not os.path.exists(f_dem):
            f_dem = _v2.p("dem", f"dem_cop30_egm08_{setor}.tif")
            avisos.append(f"DEM {a.dem} ausente; usado Copernicus GLO-30")
        if not os.path.exists(f_dem):
            _v2.log(f"{setor}: sem DEM — pulado")
            continue
        H, prof = ler(f_dem)
        prof = dict(prof, compress="deflate")
        _, zona = _v2.grade_setor(setor)
        # --- vertical (Eqs. 1–3)
        N = superficie_na_grade(f_N, prof) if tem_N else None
        eta = superficie_na_grade(f_eta, prof) if tem_eta else None
        if N is not None and eta is not None:
            dif = np.nanmean(N - eta)
            if not np.isfinite(dif) or abs(dif) > 3:
                avisos.append(f"η hgeoHNOR2020 incoerente com N EGM08 (dif. média {dif:.2f} m); usado N")
                eta = None
        if N is None:
            avisos.append("grade EGM2008 ausente: HN ≈ H_EGM08")
            z = H - nmm_sgb
        else:
            h = H + N
            z = (h - (eta if eta is not None else N)) - nmm_sgb
            if eta is None:
                avisos.append("hgeoHNOR2020 ausente: HN ≈ H_EGM08 (η = N)")
        # --- máscara do mar
        terra = ~geometry_mask([ba], H.shape, prof["transform"])
        mar_zona = zona & ~terra
        f_gsw = _v2.p("agua", f"gsw_ocorrencia_{setor}.tif")
        agua = (ler(f_gsw)[0] >= 50) if os.path.exists(f_gsw) else np.zeros_like(zona)
        lab, _ = ndimage.label(agua | mar_zona, structure=np.ones((3, 3)))
        ids = np.unique(lab[mar_zona & (lab > 0)])
        sea = np.isin(lab, ids) & (lab > 0)
        z[sea | ~zona] = np.nan
        pasta = os.path.join(a.saida or os.path.join(_v2.BASE, "pacotes"), setor)
        os.makedirs(pasta, exist_ok=True)
        gravar(os.path.join(pasta, "dem.tif"), z, prof)
        gravar(os.path.join(pasta, "sea.tif"), sea.astype("float32"), prof, "uint8", 255)
        lc = None
        for nome, src, dt, nd in [("landcover", ("lulc", f"landcover_{setor}.tif"), "uint8", 0),
                                  ("pop", ("exposicao", f"pop_{setor}.tif"), "float32", -9999.0),
                                  ("buildings", ("exposicao", f"buildings_{setor}.tif"), "float32", -9999.0)]:
            f = _v2.p(*src)
            if os.path.exists(f):
                arr, _ = ler(f)
                gravar(os.path.join(pasta, f"{nome}.tif"), arr, prof, dt, nd)
                if nome == "landcover":
                    lc = np.nan_to_num(arr, nan=0).astype(int)
            else:
                avisos.append(f"{nome} ausente")
        # --- validação do DEM com ICESat-2 (mesmo datum)
        dem_error = dict(PADRAO["dem_error"], corr_length_m=300)
        f_is = _v2.p("icesat2", f"atl08_ground_{setor}.csv")
        stats = None
        if os.path.exists(f_is) and lc is not None:
            pt = pd.read_csv(f_is)
            corr = amostrar(f_eta if eta is not None else f_N, pt.lon, pt.lat) if tem_N else 0.0
            pt["h_ref"] = pt.h_elip - corr - nmm_sgb
            x, y = Transformer.from_crs("EPSG:4326", _v2.CRS, always_xy=True).transform(pt.lon.values, pt.lat.values)
            pt["x"], pt["y"] = x, y
            pt = pt[np.isfinite(pt.h_ref)]
            f_csv = os.path.join(pasta, "validacao_pontos_dem.csv")
            pt[["x", "y", "h_ref", "h_sigma", "data"]].to_csv(f_csv, index=False)
            lc_val = np.where(sea, 33, lc)
            stats, de = validation.dem_vs_points(z, prof, lc_val, f_csv)
            de["by_class"].pop("33", None)
            dem_error = dict(de, corr_length_m=300)
            stats.to_csv(os.path.join(pasta, "validacao_dem_estatisticas.csv"), index=False)
        else:
            avisos.append("sem pontos ICESat-2: erro do DEM com valores padrão")
        # --- parâmetros
        f_tr = mar_set.get(setor, {}).get("fator_transferencia_salvador", 1.0)
        extremes = PADRAO["extremes"] if ext is None else {
            "threshold": round(ext["threshold"] * f_tr, 3), "scale": round(ext["scale"] * f_tr, 4), "shape": ext["shape"],
            "rate": ext["rate"], "scale_se": round(ext["scale_se"] * f_tr, 4), "shape_se": ext["shape_se"],
            "reference": f"Salvador UHSLC 708 × fator {f_tr}"}
        if ext is None:
            avisos.append("extremos ausentes: valores padrão")
        tide = {k: v for k, v in mar_set.get(setor, PADRAO["tide"]).items()
                if k in ("msl", "mhhw", "mhws", "amplification_factor")}
        if setor not in mar_set:
            avisos.append("marés ausentes: valores padrão")
        w = ond.get(setor)
        waves = PADRAO["waves"] if w is None else {k: w[k] for k in ("hs", "tp", "beach_slope", "costa_aberta")}
        r6 = ar6.get(setor)
        if r6 is None:
            avisos.append("AR6 ausente — o modelo não roda sem projeções; rode o script 08")
        params = {
            "sector": setor, "fonte_dados": "fluxo V2 (download direto)", "dem_fonte": os.path.basename(f_dem),
            "datum_vertical": f"NMM local (Salvador) = HN_SGB − {nmm_sgb} m", "avisos": avisos,
            "baseline": {"center_year": int(round(np.mean(sal.get("epoca", [2004, 2024]))))},
            "tide": tide,
            "ar6": {k: r6[k] for k in ("quantiles", "years", "scenarios")} | {"source": r6.get("fonte", "")} if r6 else {},
            "vlm_extra_mm_yr": 0.0, "extremes": extremes, "waves": waves, "dem_error": dem_error, **FIXOS}
        with open(os.path.join(pasta, "params.json"), "w", encoding="utf-8") as fh:
            json.dump(params, fh, indent=1, ensure_ascii=False, default=float)
        ger = stats.iloc[0].to_dict() if stats is not None else {}
        resumo.append({"setor": setor, "celulas_terra": int(np.isfinite(z).sum()), "celulas_mar": int(sea.sum()),
                       "n_icesat2": ger.get("n"), "vies_m": ger.get("vies"), "RMSE_m": ger.get("RMSE"),
                       "NMAD_m": ger.get("NMAD"), "mhws_m": tide.get("mhws"), "avisos": " | ".join(avisos)})
        _v2.log(f"{setor}: pacote ok ({len(avisos)} avisos); ICESat-2 n={ger.get('n')} viés={ger.get('vies')} RMSE={ger.get('RMSE')}")
    pd.DataFrame(resumo).to_csv(os.path.join(a.saida or os.path.join(_v2.BASE, "pacotes"), "resumo_pacotes.csv"),
                                index=False, encoding="utf-8-sig")
    from coastshift import io as csio
    for r in resumo:
        csio.Package(os.path.join(a.saida or os.path.join(_v2.BASE, "pacotes"), r["setor"]))
    _v2.log("pacotes conferidos com coastshift.io.Package:", len(resumo))
