"""30 — Sensibilidade ao comprimento de correlação do erro do DEM (ℓ) a partir das rodadas completas.

Sequência geométrica ℓ̂ × 2^k (k = −2…+1: 166, 331, 662 e 1.324 m) centrada no valor estimado
pelo semivariograma (662 m, rodada principal). Todas as rodadas usam N = 500 e as mesmas sementes, de modo que as
diferenças refletem só ℓ. Reúne também a validação por vários pares Sentinel-1/2 (script 25d) e a da zona entremarés
(script 31) por ℓ.

Saídas: resultados_O2_Bahia/sensibilidade_ell/{sensibilidade_ell.csv, resumo_costa.csv, validacao_por_ell.csv,
        Fig_sensibilidade_ell.png|pdf}
"""
import glob
import os

import matplotlib
import numpy as np
import pandas as pd

import _v2

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

R = os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia")
OUT = os.path.join(R, "sensibilidade_ell")
BASE = 662

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    partes = []
    for d in sorted(glob.glob(os.path.join(R, "ell_*m"))):
        fa, fx = os.path.join(d, "tabelas", "areas_por_classe_ha.csv"), os.path.join(d, "tabelas", "exposicao_O2.csv")
        if not (os.path.exists(fa) and os.path.exists(fx)):
            continue
        a, x = pd.read_csv(fa), pd.read_csv(fx)
        x["setor"] = x.setor.replace({s: "TOTAL_COSTA_BAHIA" for s in x.setor.unique() if "TOTAL" in s})
        m = a[["setor", "cenario", "ano", "area_esperada_ha", "area_p_ge_0.5_ha"]].merge(
            x[["setor", "cenario", "ano", "area_ha_p05", "area_ha_p95", "populacao_media"]], on=["setor", "cenario", "ano"], how="left")
        m.insert(0, "ell_m", int(os.path.basename(d)[4:-1]))
        partes.append(m)
    t = pd.concat(partes, ignore_index=True)
    b = t[t.ell_m == BASE].set_index(["setor", "cenario", "ano"])
    for c in ("area_esperada_ha", "area_p_ge_0.5_ha", "populacao_media"):
        t[f"dif_{c}_%"] = 100 * (t.set_index(["setor", "cenario", "ano"])[c].values
                                 / b.reindex(t.set_index(["setor", "cenario", "ano"]).index)[c].values - 1)
    t.round(2).to_csv(os.path.join(OUT, "sensibilidade_ell.csv"), index=False, encoding="utf-8-sig")
    tc = t[t.setor == "TOTAL_COSTA_BAHIA"]
    tc.pivot_table(index=["cenario", "ano"], columns="ell_m", values="dif_area_esperada_ha_%").round(1).to_csv(
        os.path.join(OUT, "resumo_costa.csv"), encoding="utf-8-sig")
    # validação por ℓ
    vs = [pd.read_csv(f) for f in glob.glob(os.path.join(R, "validacao_satelite", "resumo_ell_*.csv"))]
    vs = pd.concat(vs, ignore_index=True) if vs else pd.DataFrame()
    fe = os.path.join(R, "validacao_entremares", "entremares_por_ell.csv")
    ve = pd.read_csv(fe) if os.path.exists(fe) else pd.DataFrame()
    if len(vs):
        vs.round(4).to_csv(os.path.join(OUT, "validacao_por_ell.csv"), index=False, encoding="utf-8-sig")
    # figura
    fig, ax = plt.subplots(1, 3, figsize=(10.5, 3.4))
    for (cen, ano), rot, cor in [(("atual", 2014), "Present day", "#4d4d4d"), (("ssp245", 2100), "SSP2-4.5 2100", "#2c7bb6"),
                                 (("ssp585", 2100), "SSP5-8.5 2100", "#d7191c")]:
        s = tc[(tc.cenario == cen) & (tc.ano == ano)].sort_values("ell_m")
        ax[0].fill_between(s.ell_m, s.area_ha_p05 / 1e3, s.area_ha_p95 / 1e3, color=cor, alpha=0.12, lw=0)
        ax[0].plot(s.ell_m, s.area_esperada_ha / 1e3, "o-", color=cor, ms=4, label=rot)
    ax[0].set_ylabel("Expected inundated area (10³ ha)")
    ax[0].set_title("(a) Coast-wide E[A] vs ℓ", loc="left", fontsize=10, fontweight="bold")
    if len(vs):
        for sen, mk in (("s1", "o"), ("s2", "s")):
            s = vs[vs.sensor == sen].sort_values("ell_m")
            ax[1].plot(s.ell_m, s.CSI, mk + "-", color="#2c7bb6", ms=4, label=f"CSI {sen.upper()}")
            ax[1].plot(s.ell_m, s.HR, mk + "--", color="#1a9641", ms=4, label=f"Hit rate {sen.upper()}")
        ax[1].set_ylim(0, 1)
    ax[1].set_title("(b) Tidal validation (multi-pair)", loc="left", fontsize=10, fontweight="bold")
    if len(ve):
        e = ve[ve.setor == "TOTAL_COSTA_BAHIA"]
        for hab, cor in (("Mangue (MapBiomas)", "#1b7837"), ("Mangue (GMW 2020)", "#7fbf7b"), ("Apicum (MapBiomas)", "#bf812d")):
            s = e[e.habitat == hab].sort_values("ell_m")
            ax[2].plot(s.ell_m, s["frac_p_ge_0.5"], "o-", color=cor, ms=4, label=hab)
        ax[2].set_ylim(0, 1)
    ax[2].set_title("(c) Intertidal habitats with p ≥ 0.5", loc="left", fontsize=10, fontweight="bold")
    for a_ in ax:
        a_.set_xscale("log", base=2)
        a_.set_xticks([166, 331, 662, 1324], ["166", "331", "662", "1324"])
        a_.axvline(BASE, color="#888", lw=0.8, ls=":")
        a_.set_xlabel("ℓ (m); dotted: estimated 662 m")
        a_.spines[["top", "right"]].set_visible(False)
        a_.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"Fig_sensibilidade_ell.{ext}"), dpi=600)
    _v2.log(f"sensibilidade a ℓ: {sorted(t.ell_m.unique())} -> {OUT}")
