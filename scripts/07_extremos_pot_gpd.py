# %% [markdown]
# # 07 — Níveis extremos por POT-GPD (marégrafo de Salvador) + retroteste
# Eqs. 8–9 do documento de métodos. Série horária do script 06 (nível total = maré + meteorológica).
# Passos: remover NMM anual (tendência) → limiar no percentil 99 → declustering (72 h) → ajuste GPD (loc = 0)
# → incerteza por bootstrap → níveis de retorno → retroteste (ajusta na 1ª metade, testa na 2ª).
# Transferência para setores sem marégrafo: escala pela razão de MHWS (hipótese simplificadora; conferir com
# CoDEC/GTSM — Muis et al., 2020 — quando possível).

# %%
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

if "google.colab" in sys.modules:
    sys.path.insert(0, "/content/CoastShift/scripts")
from _comum import load_config, path

cfg = load_config()
P_LIM, DECL_H, NBOOT = 0.99, 72, 300

s = pd.read_csv(path("mares", "salvador_rmpg.csv"), sep=None, engine="python")
s.columns = ["datahora", "nivel_m"] + list(s.columns[2:])
s["datahora"] = pd.to_datetime(s["datahora"], dayfirst=True, errors="coerce")
s = s.dropna(subset=["datahora", "nivel_m"]).set_index("datahora")["nivel_m"].sort_index().resample("1h").mean().dropna()
s = s - s.groupby(s.index.year).transform("mean")   # nível relativo ao NMM de cada ano (remove tendência/variação interanual)
anos = (s.index[-1] - s.index[0]).days / 365.25


def picos(x, thr):
    exc = x[x > thr]
    out, last = [], None
    for t, v in exc.items():
        if last is None or (t - last[0]).total_seconds() > DECL_H * 3600:
            out.append([t, v])
        elif v > out[-1][1]:
            out[-1] = [t, v]
        last = (t, v)
    return pd.Series([v for _, v in out], index=[t for t, _ in out])


def ajuste(x):
    thr = float(x.quantile(P_LIM))
    pk = picos(x, thr)
    xi, _, sc = stats.genpareto.fit(pk.values - thr, floc=0)
    rate = len(pk) / ((x.index[-1] - x.index[0]).days / 365.25)
    return thr, sc, xi, rate, pk


def nivel_retorno(thr, sc, xi, rate, T):
    m = rate * T
    return thr + sc * np.log(m) if abs(xi) < 1e-6 else thr + sc / xi * (m ** xi - 1)


# %% Ajuste completo + bootstrap
thr, sc, xi, rate, pk = ajuste(s)
rng = np.random.default_rng(0)
bs = []
for _ in range(NBOOT):
    amostra = rng.choice(pk.values - thr, len(pk), replace=True)
    b = stats.genpareto.fit(amostra, floc=0)
    bs.append((b[2], b[0]))
bs = np.array(bs)
TRs = [1, 2, 5, 10, 50, 100]
rl = {T: round(float(nivel_retorno(thr, sc, xi, rate, T)), 3) for T in TRs}
print(f"limiar={thr:.3f} m  σ={sc:.3f}±{bs[:, 0].std():.3f}  ξ={xi:.3f}±{bs[:, 1].std():.3f}  λ={rate:.2f}/ano  ({anos:.1f} anos)")
print("Níveis de retorno (m rel. NMM):", rl)

# %% Retroteste: ajuste na 1ª metade, verificação dos máximos anuais da 2ª metade
meio = s.index[0] + (s.index[-1] - s.index[0]) / 2
t1, s1, x1, r1, _ = ajuste(s[:meio])
maxs2 = s[meio:].resample("YE").max().dropna()
retro = [{"TR": T, "nivel": round(float(nivel_retorno(t1, s1, x1, r1, T)), 3),
          "excedencias_obs": int((maxs2 > nivel_retorno(t1, s1, x1, r1, T)).sum()),
          "esperadas": round(len(maxs2) / T, 2)} for T in [1, 2, 5, 10]]
print(pd.DataFrame(retro).to_string(index=False))

# %% Transferência por razão de MHWS e gravação
mares = json.load(open(path("mares", "mares_setores.json"), encoding="utf-8"))
ref = mares.get("S2_Salvador_BTS", {}).get("mhws")
out = {}
for nome in list(cfg["setores"]) + list(cfg["subdominios"]):
    base = nome if nome in cfg["setores"] else cfg["subdominios"][nome]["setor"]
    k = (mares.get(base, {}).get("mhws", ref) / ref) if ref else 1.0
    out[nome] = {"threshold": round(thr * k, 3), "scale": round(sc * k, 4), "shape": round(xi, 4), "rate": round(rate, 3),
                 "scale_se": round(float(bs[:, 0].std() * k), 4), "shape_se": round(float(bs[:, 1].std()), 4),
                 "reference": "nível total rel. NMM", "return_levels_m": {str(T): round(v * k, 3) for T, v in rl.items()},
                 "fonte": "POT-GPD RMPG Salvador" + ("" if base == "S2_Salvador_BTS" else f" × razão MHWS {k:.2f} (hipótese)"),
                 "retroteste": retro}
with open(path("mares", "extremos_setores.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print("salvo extremos_setores.json")
