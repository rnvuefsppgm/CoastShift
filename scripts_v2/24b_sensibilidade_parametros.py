"""24b — Sensibilidade paramétrica do Modelo 2 com N = 500 e sementes pareadas (base: ℓ = 662 m).

Um fator por vez; combinações Atual, SSP2-4.5 2100 e SSP5-8.5 2100; mesmas sementes da base, de modo que as diferenças
refletem só o fator alterado. ℓ é tratado à parte, com rodadas completas (script 30).
  correl_64      só 64 % da variância do erro do DEM é correlacionada (pepita = 36 %, semivariograma do script 23)
  sd_0.75/1.25   desvio-padrão do erro do DEM por classe × 0,75 e × 1,25 (incerteza da calibração ICESat-2)
  nmm_+0.09/-0.09  NMM local ± 0,090 m (1 σ da cadeia vertical): o terreno acima do NMM desce/sobe 0,09 m
  fs_0.9/1.1     fator de transferência da maré × 0,9 e × 1,1 em todos os setores
  dem_cop30, conectividade_4, vlm_menos1/mais1  repetidos com N = 500 para uma tabela única
Saídas: resultados_O2_Bahia/sensibilidade_parametros/{sensibilidade_parametros.csv, resumo_costa.csv, Fig_sensibilidade_parametros.png|pdf}
"""
import importlib.util
import os
from concurrent.futures import ProcessPoolExecutor

import matplotlib
import numpy as np
import pandas as pd

import _v2

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

spec = importlib.util.spec_from_file_location("s24", os.path.join(os.path.dirname(os.path.abspath(__file__)), "24_sensibilidade_convergencia.py"))
s24 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s24)
models = s24.models

OUT = os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia", "sensibilidade_parametros")
VAR = {"base": {}, "correl_64": {"fc": 0.64}, "sd_0.75": {"sds": 0.75}, "sd_1.25": {"sds": 1.25},
       "nmm_+0.09": {"dz": -0.09}, "nmm_-0.09": {"dz": 0.09}, "fs_0.9": {"amp": 0.9}, "fs_1.1": {"amp": 1.1},
       "dem_cop30": {"pacotes": "pacotes_cop30"}, "conectividade_4": {"conn": 4}, "vlm_menos1": {"vlm": -1.0}, "vlm_mais1": {"vlm": 1.0}, "convergencia_N250": {}}
ROT = {"correl_64": "Nugget 36 % (64 % correlated)", "sd_0.75": "DEM error s.d. × 0.75", "sd_1.25": "DEM error s.d. × 1.25",
       "nmm_+0.09": "Local MSL + 0.09 m", "nmm_-0.09": "Local MSL − 0.09 m", "fs_0.9": "Tidal transfer × 0.9", "fs_1.1": "Tidal transfer × 1.1",
       "dem_cop30": "Copernicus GLO-30", "conectividade_4": "4-connectivity", "vlm_menos1": "VLM −1 mm/yr", "vlm_mais1": "VLM +1 mm/yr"}


def tarefa(var, setor, jobs, n, seed):
    v = VAR[var]
    s24.VAR[var] = {k: v[k] for k in ("pacotes", "conn", "vlm", "amp") if k in v}       # reaproveita a montagem do script 24
    orig = models.o2_realizacoes

    def o2(pkg, opt, n_, seed_):
        de = pkg.params["dem_error"]
        de["corr_length_m"] = 662.0
        if "fc" in v:
            de["frac_correlated"] = v["fc"]
        if "sds" in v:
            de["sd_scale"] = v["sds"]
        if "dz" in v:
            pkg.layers["dem"] = (pkg.dem + v["dz"]).astype("float32")
        return orig(pkg, opt, n_, seed_)
    models.o2_realizacoes = o2
    try:
        return s24.tarefa(var, setor, jobs, n, seed)[:3]
    finally:
        models.o2_realizacoes = orig


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--proc", type=int, default=12)
    ap.add_argument("--todos", action="store_true", help="todos os SSP × 2030/2050/2100/2150 + Atual (saída em sensibilidade_parametros_todos/)")
    a = ap.parse_args()
    if a.todos:
        OUT = OUT + "_todos"
    os.environ.pop("COASTSHIFT_ELL", None)
    os.makedirs(OUT, exist_ok=True)
    jobs = ([(s_, y) for s_ in ("ssp119", "ssp126", "ssp245", "ssp370", "ssp585") for y in (2030, 2050, 2100, 2150)] + [("ssp245", 2014)]
            if a.todos else [("ssp245", 2014), ("ssp245", 2100), ("ssp585", 2100)])
    tarefas = [(var, s, jobs, 250 if var.startswith("conv") else a.n, (9100 + i) if var.startswith("conv") else (7000 + 10 * i))
               for var in VAR for i, s in enumerate(_v2.SETORES)]   # convergência: N = 250 com sementes independentes
    linhas = []
    with ProcessPoolExecutor(a.proc) as ex:
        for var, setor, res in ex.map(tarefa, *zip(*tarefas)):
            for (ssp, ano), r in res.items():
                linhas.append({"variante": var, "setor": setor, "cenario": "atual" if ano == 2014 else ssp, "ano": ano, **r})
            _v2.log(f"sensibilidade 24b: {var} {setor} ok")
    d = pd.DataFrame(linhas)
    tot = d.groupby(["variante", "cenario", "ano"], as_index=False)[["E_A_ha", "pop"]].sum().assign(setor="TOTAL_COSTA_BAHIA")
    d = pd.concat([d, tot], ignore_index=True)
    base = d[d.variante == "base"].set_index(["setor", "cenario", "ano"])["E_A_ha"]
    d["dif_vs_base_%"] = d.apply(lambda r: 100 * (r.E_A_ha / base.get((r.setor, r.cenario, r.ano), np.nan) - 1), axis=1)
    d.round(2).to_csv(os.path.join(OUT, "sensibilidade_parametros.csv"), index=False, encoding="utf-8-sig")
    t = d[d.setor == "TOTAL_COSTA_BAHIA"].pivot_table(index="variante", columns=["cenario", "ano"], values="dif_vs_base_%").round(2)
    t.to_csv(os.path.join(OUT, "resumo_costa.csv"), encoding="utf-8-sig")
    # tornado (costa, SSP5-8.5 2100 e Atual)
    tt = t.drop(index=[i for i in ("base", "convergencia_N250") if i in t.index])
    tt = tt.reindex(tt.abs().max(axis=1).sort_values().index)
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    y = np.arange(len(tt))
    for k, (col, rot, cor) in enumerate([(("atual", 2014), "Present day", "#4d4d4d"), (("ssp585", 2100), "SSP5-8.5 2100", "#d7191c")]):
        ax.barh(y + (k - 0.5) * 0.38, tt[col], 0.36, color=cor, label=rot)
    ax.set_yticks(y, [ROT.get(i, i) for i in tt.index], fontsize=8)
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_xlabel("Change in coast-wide expected inundated area (%)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"Fig_sensibilidade_parametros.{ext}"), dpi=600)
    _v2.log(f"sensibilidade 24b concluída -> {OUT}")
