# %% [markdown]
# # 06 — Níveis de referência de maré por setor (NMM, MHHW, MHWS)
# Fontes:
# - Marégrafo de Salvador — RMPG/IBGE (baixe a série no portal do IBGE para `mares/`, CSV/TXT com data-hora e nível em m).
# - Tábuas de Marés e catálogo de estações da DHN/CHM (https://www.marinha.mil.br/chm/tabuas-de-mare) e FEMAR
#   para Aratu, Madre de Deus, Ilhéus, Porto Seguro etc. → preencha `mares/estacoes_dhn.csv` (modelo gerado abaixo).
# Equações (doc. de métodos, Eq. 7): MHWS ≈ NMM + A(M2) + A(S2); MHHW = média das preamares mais altas diárias.

# %%
import json
import os
import sys

import numpy as np
import pandas as pd

if "google.colab" in sys.modules:
    sys.path.insert(0, "/content/CoastShift/scripts")
from _comum import load_config, path

cfg = load_config()
SERIE = path("mares", "salvador_rmpg.csv")      # colunas: datahora, nivel_m  (ajuste abaixo se necessário)
DHN = path("mares", "estacoes_dhn.csv")

# %% 1) Modelo de tabela DHN (preencha com Z0 e níveis sobre o NR das Tábuas/FEMAR)
if not os.path.exists(DHN):
    pd.DataFrame({
        "setor": list(cfg["setores"]),
        "estacao": ["(preencher) ex.: Porto de Salvador"] * len(cfg["setores"]),
        "z0_m_sobre_NR": [np.nan] * len(cfg["setores"]),
        "mhws_m_sobre_NR": [np.nan] * len(cfg["setores"]),
        "mhhw_m_sobre_NR": [np.nan] * len(cfg["setores"]),
        "fonte": ["DHN Tábuas de Marés <ano> / FEMAR"] * len(cfg["setores"]),
    }).to_csv(DHN, index=False)
    print("Modelo criado:", DHN, "— preencha e rode novamente.")

# %% 2) Série de Salvador: NMM da época, análise harmônica (UTide), MHHW observado
res = {}
if os.path.exists(SERIE):
    s = pd.read_csv(SERIE, sep=None, engine="python")
    s.columns = ["datahora", "nivel_m"] + list(s.columns[2:])
    s["datahora"] = pd.to_datetime(s["datahora"], dayfirst=True, errors="coerce")
    s = s.dropna(subset=["datahora", "nivel_m"]).set_index("datahora").sort_index()
    ep = cfg["epoca_nmm_local"]
    s = s.loc[f"{ep['inicio']}-01-01":f"{ep['fim']}-12-31", "nivel_m"].resample("1h").mean().dropna()
    nmm = float(s.mean())
    import utide
    t = s.index.to_pydatetime()
    coef = utide.solve(t, s.values - nmm, lat=-12.97, method="ols", conf_int="none", verbose=False)
    amp = dict(zip(coef["name"], coef["A"]))
    mhhw = float(s.resample("1D").max().mean() - nmm)
    res["S2_Salvador_BTS"] = {"msl": 0.0, "mhws": round(float(amp.get("M2", 0) + amp.get("S2", 0)), 3),
                             "mhhw": round(mhhw, 3), "nmm_serie_m": round(nmm, 3),
                             "constituintes": {k: round(float(v), 3) for k, v in amp.items() if k in ("M2", "S2", "N2", "K1", "O1", "M4")},
                             "fonte": "RMPG/IBGE Salvador, UTide"}
    print("Salvador:", res["S2_Salvador_BTS"])
else:
    print("Série de Salvador não encontrada em", SERIE)

# %% 3) Demais setores pela tabela DHN (níveis relativos ao NMM = nível sobre NR − Z0)
d = pd.read_csv(DHN)
for _, r in d.dropna(subset=["z0_m_sobre_NR", "mhws_m_sobre_NR"]).iterrows():
    if r["setor"] in res:
        res[r["setor"]]["mhws_dhn"] = round(r["mhws_m_sobre_NR"] - r["z0_m_sobre_NR"], 3)
        continue
    res[r["setor"]] = {"msl": 0.0, "mhws": round(r["mhws_m_sobre_NR"] - r["z0_m_sobre_NR"], 3),
                       "mhhw": round((r["mhhw_m_sobre_NR"] if pd.notna(r["mhhw_m_sobre_NR"]) else r["mhws_m_sobre_NR"]) - r["z0_m_sobre_NR"], 3),
                       "fonte": f"{r['estacao']} – {r['fonte']}"}
faltam = [k for k in cfg["setores"] if k not in res]
if faltam:
    print("ATENÇÃO: sem nível de maré para", faltam, "— preencha estacoes_dhn.csv")
for sd, s in cfg["subdominios"].items():
    if s["setor"] in res:
        res[sd] = res[s["setor"]]
with open(path("mares", "mares_setores.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, indent=1, ensure_ascii=False)
print("salvo mares_setores.json")
