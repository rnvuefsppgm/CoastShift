"""21 — Execução automática do Modelo 2 (O2) em todos os setores da costa da Bahia, em paralelo, com
reclassificação da probabilidade e cálculo de áreas (ha) por setor e para toda a costa.

Combinações: 5 SSPs × anos (padrão 2030, 2050, 2100) + linha de base ATUAL (ΔRSL = 0 na época do NMM local,
2004–2024, ano central do params.json; independe do SSP). Em cada realização o campo de erro do DEM e o
evento de referência são sorteados uma vez e usados em todas as combinações (coastshift.models.o2_realizacoes).
Paralelismo: setores × blocos de realizações (sementes distintas e registradas) em processos independentes.

Classes (linguagem calibrada do IPCC aplicada à probabilidade condicional p̂):
  0 = não inundável (p < 0,05) · 1 = improvável (0,05–0,33) · 2 = tão provável quanto não (0,33–0,66)
  3 = provável (0,66–0,90) · 4 = muito provável (≥ 0,90)

Uso: python 21_rodar_O2_resultados.py [--n 500] [--ssps ssp119,ssp126,ssp245,ssp370,ssp585]
                                      [--anos 2030,2050,2100] [--ref MHWS] [--sem-atual] [--proc 10] [--bloco 50]
Saídas: <Ana_Model>/resultados_O2_Bahia/{geotiff, tabelas}; mapas pelo script 22.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
import rasterio

import _v2

sys.path.insert(0, _v2.REPO)
from coastshift import io as csio, models  # noqa: E402

OUT = os.environ.get("COASTSHIFT_RESULTADOS", os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia"))
LIM = [0.05, 0.33, 0.66, 0.90]
CLASSES = ["nao_inundavel", "improvavel", "tao_provavel_quanto_nao", "provavel", "muito_provavel"]


def reclass(p):
    c = np.digitize(np.nan_to_num(p, nan=0.0), LIM).astype("uint8")
    return np.where(np.isnan(p), 255, c).astype("uint8")


def opcoes(pkg, a, jobs):
    return {"ssps": [], "years": [], "jobs": jobs, "ref": a.ref, "tr": a.tr, "conn": 8,
            "setup": bool(pkg.params["waves"].get("costa_aberta"))}


def bloco(setor, jobs, a, n, seed):
    pkg = csio.Package(os.path.join(_v2.BASE, "pacotes", setor))
    return setor, models.o2_realizacoes(pkg, opcoes(pkg, a, jobs), n, seed)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--ssps", default="ssp119,ssp126,ssp245,ssp370,ssp585")
    ap.add_argument("--anos", default="2030,2050,2100")
    ap.add_argument("--ref", default="MHWS", help="NMM | MHHW | MHWS")
    ap.add_argument("--tr", type=float, default=0, help="tempo de retorno (anos) do nível extremo; 0 = maré")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--sem-atual", action="store_true", help="não calcula a linha de base atual")
    ap.add_argument("--proc", type=int, default=10)
    ap.add_argument("--bloco", type=int, default=50)
    a = ap.parse_args()
    for d in ("geotiff", "tabelas", "mapas"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    with open(os.path.join(_v2.BASE, "pacotes", list(_v2.SETORES)[0], "params.json"), encoding="utf-8") as fh:
        t0 = int(json.load(fh)["baseline"]["center_year"])
    jobs = [(s, int(y)) for s in a.ssps.split(",") for y in a.anos.split(",")]
    if not a.sem_atual:
        jobs.append(("ssp245", t0))                      # ΔRSL(t0) = 0 → linha de base (rotulada "atual")
    rotulo = {jb: ("atual" if jb[1] == t0 else jb[0]) for jb in jobs}
    nb = int(np.ceil(a.n / a.bloco))
    tarefas = [(setor, jobs, a, min(a.bloco, a.n - b * a.bloco), a.seed + 1000 * i + b)
               for i, setor in enumerate(_v2.SETORES) for b in range(nb)]
    _v2.log(f"O2 Bahia: {len(jobs)} combinações × N={a.n} × 6 setores; {len(tarefas)} blocos em {a.proc} processos")
    t_ini = time.time()
    acc = {s: (None, None) for s in _v2.SETORES}
    with ProcessPoolExecutor(a.proc) as ex:
        futs = [ex.submit(bloco, *t) for t in tarefas]
        for k, fu in enumerate(as_completed(futs), 1):
            setor, (cnt, tot) = fu.result()
            c0, t0_ = acc[setor]
            if c0 is None:
                acc[setor] = (cnt, tot)
            else:
                for jb in cnt:
                    c0[jb] += cnt[jb]
                    t0_[jb] += tot[jb]
            _v2.log(f"bloco {k}/{len(tarefas)} ({setor}) — {(time.time() - t_ini) / 60:.1f} min")
    exp_rows, cls_rows = [], []
    for setor in _v2.SETORES:
        pkg = csio.Package(os.path.join(_v2.BASE, "pacotes", setor))
        cnt, tot = acc[setor]
        opt = opcoes(pkg, a, jobs)
        res = models.o2_resultado(pkg, opt, cnt, tot, a.n)
        cell_ha = pkg.cell ** 2 / 1e4
        terra = np.isfinite(pkg.dem)
        area_terra = float(terra.sum() * cell_ha)
        for row in res.table:
            jb = (row["cenario"], int(row["ano"]))
            exp_rows.append({"setor": setor, "area_terrestre_ha": round(area_terra, 1), "setup": opt["setup"],
                             **row, "cenario": rotulo[jb]})
        for ssp, ano in jobs:
            p = res.layers[f"probabilidade_{ssp}_{ano}"].copy()
            p[~terra] = np.nan                                         # mar e fora da zona: sem classe
            cls = reclass(p)
            tag = f"{rotulo[(ssp, ano)]}_{ano}"
            pf = dict(pkg.profile, compress="deflate", count=1)
            with rasterio.open(os.path.join(OUT, "geotiff", f"prob_{setor}_{tag}.tif"), "w",
                               **dict(pf, dtype="float32", nodata=-9999.0)) as w:
                w.write(np.where(np.isnan(p), -9999.0, p).astype("float32"), 1)
            with rasterio.open(os.path.join(OUT, "geotiff", f"classe_{setor}_{tag}.tif"), "w",
                               **dict(pf, dtype="uint8", nodata=255)) as w:
                w.write(cls, 1)
            row = {"setor": setor, "cenario": rotulo[(ssp, ano)], "ano": ano,
                   "ref": f"TR{a.tr:g}" if a.tr else a.ref, "N": a.n}
            for i, nome in enumerate(CLASSES):
                row[f"{nome}_ha"] = round(float((cls == i).sum() * cell_ha), 1)
            row["area_esperada_ha"] = round(float(np.nansum(p) * cell_ha), 1)
            row["area_p_ge_0.5_ha"] = round(float((np.nan_to_num(p) >= 0.5).sum() * cell_ha), 1)
            row["area_terrestre_ha"] = round(area_terra, 1)
            cls_rows.append(row)
        _v2.log(f"{setor}: GeoTIFFs e áreas gravados")
    cls, exp = pd.DataFrame(cls_rows), pd.DataFrame(exp_rows)
    num_c = [c for c in cls.columns if c.endswith("_ha")]
    tot_c = cls.groupby(["cenario", "ano", "ref", "N"], as_index=False)[num_c].sum()
    tot_c.insert(0, "setor", "TOTAL_COSTA_BAHIA")
    cls = pd.concat([cls, tot_c], ignore_index=True)
    num_e = [c for c in exp.columns if c.endswith(("_media", "_p05", "_p95")) or c in ("area_terrestre_ha", "area_ha_p>=0.5")]
    tot_e = exp.groupby(["cenario", "ano", "N"], as_index=False)[num_e].sum()
    tot_e["dRSL_p50_m"] = exp.groupby(["cenario", "ano"])["dRSL_p50_m"].mean().values
    tot_e.insert(0, "setor", "TOTAL_COSTA_BAHIA")
    exp = pd.concat([exp, tot_e], ignore_index=True)
    cls.to_csv(os.path.join(OUT, "tabelas", "areas_por_classe_ha.csv"), index=False, encoding="utf-8-sig")
    exp.to_csv(os.path.join(OUT, "tabelas", "exposicao_O2.csv"), index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(os.path.join(OUT, "tabelas", "resultados_O2_Bahia.xlsx")) as xw:
        cls.to_excel(xw, sheet_name="areas_classes_ha", index=False)
        exp.to_excel(xw, sheet_name="exposicao", index=False)
        pd.DataFrame({"classe": range(5), "nome": CLASSES,
                      "intervalo_p": ["<0.05", "0.05-0.33", "0.33-0.66", "0.66-0.90", ">=0.90"]}).to_excel(
            xw, sheet_name="legenda", index=False)
    json.dump({"opcoes": {k: v for k, v in vars(a).items()}, "combinacoes": [list(j) for j in jobs], "ano_base": t0,
               "minutos": round((time.time() - t_ini) / 60, 1), "limiares": LIM,
               "nota_total": "TOTAL = soma dos setores; p05/p95 somados são limites conservadores"},
              open(os.path.join(OUT, "tabelas", "metadados_execucao.json"), "w", encoding="utf-8"), indent=1)
    _v2.log(f"O2 Bahia concluído em {(time.time() - t_ini) / 60:.1f} min -> {OUT}")
