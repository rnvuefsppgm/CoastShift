"""27 — Gráficos de síntese (600 dpi + PDF) a partir das saídas dos scripts 21, 23, 24, 25b e 28.

Fig_validacao_DEM · Fig_validacao_mare · Fig_sensibilidade · Fig_convergencia · Fig_niveis_referencia ·
Fig_trajetoria_area. Salva em <resultados>/graficos e consolida tabelas-resumo em <resultados>/tabelas/sintese.xlsx.
"""
import json
import os

import numpy as np
import pandas as pd

import _v2

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RES = os.environ.get("COASTSHIFT_RESULTADOS", os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia"))
GR, VAL, TB = (os.path.join(RES, d) for d in ("graficos", "validacao", "tabelas"))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "pdf.fonttype": 42})
COR = {"atual": "#9e9e9e", "ssp119": "#1a9850", "ssp126": "#66bd63", "ssp245": "#fdae61", "ssp370": "#f46d43",
       "ssp585": "#a50026"}
LAB = {"atual": "Present day", "ssp119": "SSP1-1.9", "ssp126": "SSP1-2.6", "ssp245": "SSP2-4.5", "ssp370": "SSP3-7.0",
       "ssp585": "SSP5-8.5"}
NOME_CL = {15: "Pasture", 50: "Herb. restinga", 3: "Forest", 21: "Agric. mosaic", 11: "Wetland", 24: "Urban",
           9: "Forest plant.", 5: "Mangrove", 23: "Beach/dune", 49: "Wooded restinga", 25: "Other non-veg.", 41: "Crops",
           29: "Rock outcrop", 32: "Salt flat", 31: "Aquaculture", 12: "Grassland", 48: "Perennial crops", 4: "Savanna"}
resumo = {}


def salvar(fig, nome):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(GR, f"{nome}.{ext}"), dpi=600 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)


def titulo(ax, t):
    ax.set_title(t, fontsize=11, fontweight="bold", loc="left")


if __name__ == "__main__":
    os.makedirs(GR, exist_ok=True)
    # 1) DEM: retenção por classe + variograma ---------------------------------------------------------------
    f = os.path.join(VAL, "dem_retencao_por_classe.csv")
    if os.path.exists(f):
        d = pd.read_csv(f)
        d = d[d.classe != "todas"].copy()
        d["classe"] = d.classe.astype(int)
        d = d.sort_values("bruto_n", ascending=False).head(10)
        v = pd.read_csv(os.path.join(VAL, "variograma.csv"))
        rd = json.load(open(os.path.join(VAL, "resumo_dem.json")))
        fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 3.6), gridspec_kw={"width_ratios": [1.35, 1]})
        y = np.arange(len(d))
        a.barh(y + 0.2, d.bruto_vies, 0.38, color="#bdbdbd", label="Raw (z − h)")
        a.barh(y - 0.2, d.corrigido_vies, 0.38, color="#2c7bb6", label="Class-corrected")
        a.set_yticks(y, [NOME_CL.get(c, str(c)) for c in d.classe], fontsize=9)
        a.invert_yaxis()
        a.axvline(0, color="k", lw=0.6)
        a.set_xlabel("Bias on hold-out ICESat-2 tracks (m)")
        a.legend(frameon=False, fontsize=8.5, loc="lower right")
        titulo(a, "(a) FABDEM bias by land cover")
        b.plot(v.lag_m, v.semivariancia_m2, "o", ms=3, color="#3b6f9e", label="Empirical")
        b.plot(v.lag_m, v.modelo, "-", color="#bd0026", lw=1.5, label=f"Gaussian, ℓ = {rd['variograma']['ell_m']:.0f} m")
        b.set_xlabel("Lag (m)")
        b.set_ylabel("Semivariance (m²)")
        b.legend(frameon=False, fontsize=8.5, loc="lower right")
        titulo(b, "(b) Residual semivariogram")
        fig.tight_layout()
        salvar(fig, "Fig_validacao_DEM")
        resumo["DEM"] = rd
    # 2) validação da maré (pares preamar/baixa-mar) ---------------------------------------------------------
    pref = "s1_intermare" if os.path.exists(os.path.join(VAL, "s1_intermare_metricas.csv")) else "intermare"
    f = os.path.join(VAL, f"{pref}_metricas.csv")
    if os.path.exists(f):
        m = pd.read_csv(f)
        c = pd.read_csv(os.path.join(VAL, f"{pref}_confiabilidade.csv"))
        fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 3.6), gridspec_kw={"width_ratios": [1.4, 1]})
        mm = m[m.setor != "TOTAL"]
        x = np.arange(len(mm) + 1)
        nomes = [s.split("_")[0] for s in mm.setor] + ["All"]
        for k, (col, lab, cor) in enumerate([("CSI", "CSI", "#2c7bb6"), ("sem_mangue_CSI", "CSI excl. mangrove", "#abd9e9"),
                                            ("HR", "Hit rate", "#1a9641"), ("FAR", "False alarm ratio", "#d7191c")]):
            a.bar(x + (k - 1.5) * 0.2, m[col].values, 0.19, color=cor, label=lab)
        a.set_xticks(x, nomes)
        a.set_ylim(0, 1)
        a.legend(frameon=False, fontsize=8, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.1))
        titulo(a, "(a) Tidal-inundation skill, Sentinel-1 (p ≥ 0.5)" if pref.startswith("s1") else "(a) Tidal-inundation skill (p ≥ 0.5)")
        g = c.groupby("faixa_p").apply(lambda z: pd.Series({"p": np.average(z.p_media, weights=z.n),
                                                            "o": np.average(z.freq_obs, weights=z.n), "n": z.n.sum()}))
        b.plot([0, 1], [0, 1], "--", color="#888", lw=0.8)
        b.scatter(g.p, g.o, s=12 + 60 * g.n / g.n.max(), color="#2c7bb6", zorder=3)
        b.plot(g.p, g.o, color="#2c7bb6", lw=1)
        b.set_xlabel("Forecast probability")
        b.set_ylabel("Observed frequency")
        b.set_xlim(0, 1)
        b.set_ylim(0, 1)
        tot = m[m.setor == "TOTAL"].iloc[0]
        titulo(b, f"(b) Reliability (Brier = {tot.Brier:.3f})")
        fig.tight_layout()
        salvar(fig, "Fig_validacao_mare")
        resumo["mare"] = tot.to_dict()
    # 3) sensibilidade (tornado) e convergência --------------------------------------------------------------
    f = os.path.join(RES, "sensibilidade", "sensibilidade.csv")
    if os.path.exists(f):
        s = pd.read_csv(f)
        amp = s.variante.str.startswith("amp")                   # amplificação só altera o S2: comparar no S2
        s = pd.concat([s[(s.setor == "TOTAL_COSTA_BAHIA") & ~amp & (s.variante != "base")],
                       s[(s.setor == "S2_Salvador_BTS") & amp]], ignore_index=True)
        rot = {"dem_cop30": "DEM: Copernicus GLO-30", "conectividade_4": "4-connectivity", "ell_150m": "ℓ = 150 m",
               "ell_600m": "ℓ = 600 m", "vlm_menos1": "VLM −1 mm/yr", "vlm_mais1": "VLM +1 mm/yr",
               "amp_0.9_S2": "Tide amplification 0.9 (S2 only)", "amp_1.1_S2": "Tide amplification 1.1 (S2 only)"}
        fig, ax = plt.subplots(figsize=(7.2, 3.8))
        ordem = s[(s.cenario == "ssp585")].set_index("variante")["dif_vs_base_%"].abs().sort_values().index
        y = np.arange(len(ordem))
        for k, (cen, cor) in enumerate([("atual", COR["atual"]), ("ssp245", COR["ssp245"]), ("ssp585", COR["ssp585"])]):
            vv = s[s.cenario == cen].set_index("variante").reindex(ordem)["dif_vs_base_%"]
            ax.barh(y + (k - 1) * 0.26, vv, 0.25, color=cor, label=LAB[cen] + ("" if cen == "atual" else " · 2100"))
        ax.set_yticks(y, [rot.get(v, v) for v in ordem], fontsize=9.5)
        ax.axvline(0, color="k", lw=0.6)
        ax.set_xlabel("Change in expected inundated area E[A] vs. baseline (%)")
        ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3)
        titulo(ax, "Sensitivity of the coast-wide expected inundated area (N = 100, paired seeds)")
        fig.tight_layout()
        salvar(fig, "Fig_sensibilidade")
        cv = pd.read_csv(os.path.join(RES, "sensibilidade", "convergencia.csv"))
        fig, ax = plt.subplots(figsize=(7.2, 2.8))
        cvv = cv.pivot_table(index="setor", columns="cenario", values="dif_%")
        cvv = cvv.reindex(list(_v2.SETORES) + ["TOTAL_COSTA_BAHIA"])
        x = np.arange(len(cvv))
        for k, cen in enumerate(cvv.columns):
            ax.bar(x + (k - 0.5) * 0.38, cvv[cen], 0.36, color=COR.get(cen, "#555"), label=LAB.get(cen, cen))
        ax.axhspan(-1, 1, color="#e0f3db", zorder=0)
        ax.set_xticks(x, [i.split("_")[0] if i.startswith("S") else "Coast" for i in cvv.index])
        ax.set_ylabel("E[A]: N = 250 vs N = 500 (%)")
        ax.legend(frameon=False, fontsize=9)
        titulo(ax, "Monte Carlo convergence (shaded band = ±1 %)")
        fig.tight_layout()
        salvar(fig, "Fig_convergencia")
        resumo["convergencia_max_abs_%"] = float(cv["dif_%"].abs().max())
    # 4) níveis de referência (permanente, recorrente, episódico) -------------------------------------------
    niveis = [("episodico_NMM", "MSL"), (None, "MHWS"), ("episodico_TR10", "10-yr"), ("episodico_TR100", "100-yr")]
    reg = []
    for pasta, lab in niveis:
        fa = os.path.join(RES, pasta, "tabelas", "areas_por_classe_ha.csv") if pasta else os.path.join(TB, "areas_por_classe_ha.csv")
        if os.path.exists(fa):
            a_ = pd.read_csv(fa)
            a_ = a_[a_.setor == "TOTAL_COSTA_BAHIA"]
            for _, r in a_.iterrows():
                reg.append({"nivel": lab, "cenario": r.cenario, "ano": int(r.ano), "E_A_ha": r.area_esperada_ha})
    if reg:
        r = pd.DataFrame(reg)
        combos = [("atual", 2014), ("ssp245", 2050), ("ssp585", 2050), ("ssp245", 2100), ("ssp585", 2100)]
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        labs = [l for _, l in niveis if l in set(r.nivel)]
        x = np.arange(len(labs))
        for k, (cen, ano) in enumerate(combos):
            vv = [r[(r.nivel == l) & (r.cenario == cen) & (r.ano == ano)].E_A_ha.sum() / 1000 for l in labs]
            ax.bar(x + (k - 2) * 0.16, vv, 0.15, color=COR[cen], alpha=1 if ano != 2050 else 0.55,
                   label=LAB[cen] + ("" if cen == "atual" else f" · {ano}"))
        ax.set_xticks(x, ["MSL\n(permanent)" if l == "MSL" else "MHWS\n(recurrent)" if l == "MHWS" else f"{l} return level\n(episodic)"
                          for l in labs])
        ax.set_ylabel("Expected inundated area (10³ ha)")
        ax.legend(frameon=False, fontsize=8.5, ncol=2)
        titulo(ax, "Coast-wide expected inundation by reference water level")
        fig.tight_layout()
        salvar(fig, "Fig_niveis_referencia")
        r.round(1).to_csv(os.path.join(TB, "sintese_niveis_referencia.csv"), index=False, encoding="utf-8-sig")
    # 5) trajetória da área esperada até 2150 ---------------------------------------------------------------
    a_ = pd.read_csv(os.path.join(TB, "areas_por_classe_ha.csv"))
    f150 = os.path.join(RES, "horizonte_2150", "tabelas", "areas_por_classe_ha.csv")
    if os.path.exists(f150):
        a_ = pd.concat([a_, pd.read_csv(f150)], ignore_index=True)
    a_ = a_[a_.setor == "TOTAL_COSTA_BAHIA"]
    atual = a_[a_.cenario == "atual"].area_esperada_ha.iloc[0]
    e = pd.read_csv(os.path.join(TB, "exposicao_O2.csv"))
    e = e[e.setor == "TOTAL_COSTA_BAHIA"]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for ssp in ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"]:
        z = a_[a_.cenario == ssp].sort_values("ano")
        anos = [2014] + list(z.ano)
        vals = [atual] + list(z.area_esperada_ha)
        ax.plot(anos, np.array(vals) / 1000, "-o", ms=3.5, color=COR[ssp], label=LAB[ssp], lw=1.6)
        ez = e[e.cenario == ssp].sort_values("ano")
        if len(ez):
            ax.fill_between(ez.ano, ez.area_ha_p05 / 1000, ez.area_ha_p95 / 1000, color=COR[ssp], alpha=0.08)
    ax.axhline(atual / 1000, color=COR["atual"], ls="--", lw=1, label="Present day")
    ax.set_xlabel("Year")
    ax.set_ylabel("Expected inundated area (10³ ha)")
    ax.legend(frameon=False, fontsize=9, ncol=3)
    titulo(ax, "Coast-wide expected inundated area at MHWS (shading: 90% interval, 2030–2100)")
    fig.tight_layout()
    salvar(fig, "Fig_trajetoria_area")
    json.dump(resumo, open(os.path.join(TB, "sintese_validacao.json"), "w", encoding="utf-8"), indent=1, default=float)
    _v2.log("gráficos de síntese: ok")
