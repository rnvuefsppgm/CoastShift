"""24 — Análise de sensibilidade e convergência do Modelo 2 (métodos §4.7).

Variantes (uma de cada vez, demais parâmetros fixos), combinações Atual, SSP2-4.5 2100 e SSP5-8.5 2100, N = 100:
  base · DEM Copernicus GLO-30 · conectividade 4 · ℓ = 150 m · ℓ = 600 m · VLM −1 e +1 mm/ano ·
  amplificação da maré 0,9 e 1,1 (somente S2 Salvador/BTS).
Convergência: N = 250 com sementes independentes × resultado principal (N = 500, script 21); critério < 1 %.
Também grava a probabilidade SSP5-8.5 2100 com o DEM Copernicus (concordância entre DEMs, script 27).
Pré-requisito do DEM Copernicus: python 20_montar_pacotes_O2.py --dem cop30 --saida <BASE>/pacotes_cop30
Saídas: <resultados_O2_Bahia>/sensibilidade/{sensibilidade.csv, convergencia.csv, prob_cop30_*.tif}
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import rasterio
import rasterio.enums

import _v2

sys.path.insert(0, _v2.REPO)
from coastshift import io as csio, models  # noqa: E402

OUT = os.path.join(os.environ.get("COASTSHIFT_RESULTADOS", os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia")))
SENS = os.path.join(OUT, "sensibilidade")
VAR = {"base": {}, "dem_cop30": {"pacotes": "pacotes_cop30"}, "conectividade_4": {"conn": 4},
       "ell_150m": {"ell": 150}, "ell_300m": {"ell": 300}, "ell_600m": {"ell": 600}, "vlm_menos1": {"vlm": -1.0}, "vlm_mais1": {"vlm": 1.0},
       "amp_0.9_S2": {"amp": 0.9, "so": "S2_Salvador_BTS"}, "amp_1.1_S2": {"amp": 1.1, "so": "S2_Salvador_BTS"}}


def tarefa(var, setor, jobs, n, seed):
    v = VAR.get(var, {})
    pkg = csio.Package(os.path.join(_v2.BASE, "pacotes", setor))
    if "pacotes" in v:                                   # DEM alternativo reamostrado na grade do pacote principal
        alt = os.path.join(_v2.BASE, v["pacotes"], setor)
        dem = csio.align_to(os.path.join(alt, "dem.tif"), pkg.profile, rasterio.enums.Resampling.bilinear)
        pkg.layers["dem"] = np.where(np.isfinite(pkg.dem), dem, np.nan).astype("float32")
        with open(os.path.join(alt, "params.json"), encoding="utf-8") as fh:
            pkg.params["dem_error"] = json.load(fh)["dem_error"]
    if "ell" in v:
        pkg.params["dem_error"]["corr_length_m"] = v["ell"]
    if "vlm" in v:
        pkg.params["vlm_extra_mm_yr"] = v["vlm"]
    opt = {"jobs": jobs, "ref": "MHWS", "tr": 0, "conn": v.get("conn", 8), "amp": v.get("amp", 1.0),
           "setup": bool(pkg.params["waves"].get("costa_aberta"))}
    cnt, tot = models.o2_realizacoes(pkg, opt, n, seed)
    a_ha = pkg.cell ** 2 / 1e4
    res = {}
    for jb in jobs:
        res[jb] = {"E_A_ha": float(np.mean([t["area_ha"] for t in tot[jb]])),
                   "pop": float(np.mean([t["populacao"] for t in tot[jb]]))}
    salvar = None
    if var == "dem_cop30":
        vidx = np.flatnonzero(np.isfinite(pkg.dem))
        p = np.full(pkg.dem.size, np.nan, "float32")
        p[vidx] = cnt[("ssp585", 2100)] / n
        salvar = (p.reshape(pkg.dem.shape), pkg.profile)
    return var, setor, res, salvar


if __name__ == "__main__":
    os.makedirs(SENS, exist_ok=True)
    with open(os.path.join(_v2.BASE, "pacotes", list(_v2.SETORES)[0], "params.json"), encoding="utf-8") as fh:
        t0 = int(json.load(fh)["baseline"]["center_year"])
    jobs = [("ssp245", t0), ("ssp245", 2100), ("ssp585", 2100)]
    tarefas = []
    for var, v in VAR.items():
        for i, s in enumerate(_v2.SETORES):
            if v.get("so") and s != v["so"]:
                continue
            tarefas.append((var, s, jobs, 100, 7000 + 10 * i))          # mesma semente → comparação pareada
    jobs_c = [("ssp245", t0), ("ssp585", 2100)]
    for i, s in enumerate(_v2.SETORES):
        tarefas.append(("convergencia_N250", s, jobs_c, 250, 9100 + i))
    _v2.log(f"sensibilidade: {len(tarefas)} tarefas")
    linhas, conv = [], []
    with ProcessPoolExecutor(10) as ex:
        for var, setor, res, salvar in ex.map(tarefa, *zip(*tarefas)):
            for (ssp, ano), r in res.items():
                cen = "atual" if ano == t0 else ssp
                (conv if var.startswith("convergencia") else linhas).append(
                    {"variante": var, "setor": setor, "cenario": cen, "ano": ano, **r})
            if salvar is not None:
                p, prof = salvar
                with rasterio.open(os.path.join(SENS, f"prob_cop30_{setor}_ssp585_2100.tif"), "w",
                                   **dict(prof, dtype="float32", nodata=-9999.0, compress="deflate")) as w:
                    w.write(np.where(np.isnan(p), -9999.0, p).astype("float32"), 1)
            _v2.log(f"sensibilidade: {var} {setor} ok")
    d = pd.DataFrame(linhas)
    tot = d.groupby(["variante", "cenario", "ano"], as_index=False)[["E_A_ha", "pop"]].sum()
    tot["setor"] = "TOTAL_COSTA_BAHIA"
    d = pd.concat([d, tot], ignore_index=True)
    base = d[d.variante == "base"].set_index(["setor", "cenario", "ano"])["E_A_ha"]
    d["dif_vs_base_%"] = d.apply(lambda r: 100 * (r.E_A_ha / base.get((r.setor, r.cenario, r.ano), np.nan) - 1), axis=1)
    d.round(2).to_csv(os.path.join(SENS, "sensibilidade.csv"), index=False, encoding="utf-8-sig")
    principal = pd.read_csv(os.path.join(OUT, "tabelas", "exposicao_O2.csv"))
    c = pd.DataFrame(conv)
    ct = c.groupby(["cenario", "ano"], as_index=False)["E_A_ha"].sum()
    ct["setor"] = "TOTAL_COSTA_BAHIA"
    c = pd.concat([c, ct], ignore_index=True)
    c["E_A_N500_ha"] = c.apply(lambda r: principal[(principal.setor == r.setor) & (principal.cenario == r.cenario)
                                                   & (principal.ano == r.ano)].area_ha_media.iloc[0], axis=1)
    c["dif_%"] = 100 * (c.E_A_ha / c.E_A_N500_ha - 1)
    c.round(3).to_csv(os.path.join(SENS, "convergencia.csv"), index=False, encoding="utf-8-sig")
    _v2.log("sensibilidade e convergência concluídas")
