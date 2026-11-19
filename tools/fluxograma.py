"""Fluxograma detalhado do processamento (fluxo V2 + Modelo 2), em inglês e português, PNG 600 dpi + PDF/SVG.
Uso: python tools/fluxograma.py <pasta_saida>
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

T = {
    "en": {
        "A": "A · Open-data acquisition (scripts 01–14; no accounts, no GEE tasks)",
        "B": "B · Pre-processing and calibration",
        "C": "C · Sector input packages (script 20)",
        "D": "D · Model O2 — Monte Carlo, N = 500 (script 21)",
        "E": "E · Products (scripts 21–22, 26–27)",
        "F": "F · Validation, sensitivity and structural check (scripts 23–25b, 24, 28)",
        "a": ["Coastal zone & sectors\nIBGE meshes", "Terrain\nFABDEM V1-2 · Copernicus GLO-30",
              "Land cover\nMapBiomas (API) · JRC GSW", "Exposure\nGHS-POP 2025 · MS Buildings",
              "Sea-level projections\nIPCC AR6 (HTTP range)", "Tide gauge\nUHSLC 708 · IBGE RMPG",
              "Waves\nERA5 (Open-Meteo)", "Reference heights\nICESat-2 ATL08 (SlideRule)",
              "Geoid & normal heights\nEGM2008 · hgeoHNOR2020"],
        "b": ["Vertical datum chain\nh = H + N;  $H_N$ = h − η\nz = $H_N$ − MSL (Eqs 1–4)",
              "Tidal datums & transfer\nMHWS, MHHW\nratio $f_s$ (Eqs 7–9)", "Extremes POT–GPD\nbootstrap · retro-test (Eq 10)",
              "Wave set-up\nStockdon (Eq 11)", "DEM error by land cover\nbias $b_c$, $s_c$ from ICESat-2 (Eq 13)",
              "Sea seed mask\nmarine buffer ∪ connected water", "Exposure grids\npopulation · buildings (30 m)"],
        "c": "6 sectors · EPSG:31984 · 30 m · dem/landcover/sea/pop/buildings + params.json",
        "d": ["Draw $u_k$ ~ U(0,1)\n$\\Delta RSL(t;u_k)$ (Eqs 5–6)", "Reference level $L_k$\nMHWS / MSL / $z_T$ + set-up (Eq 12)",
              "Correlated DEM error\n$\\varepsilon_k$ = $G_\\ell * w$ (Eq 14)", "$z_k = z - b_c - s_c\\,\\varepsilon_k$\n(Eq 13)",
              "Connected inundation\nfor every SSP × year (Eqs 15–16)", "Accumulate\n$\\hat p$, se($\\hat p$), exposure (Eqs 17–18)"],
        "e": ["Probability GeoTIFFs\n16 combinations", "IPCC likelihood classes\nareas (ha) by sector & coast",
              "Maps (600 dpi)\ncoast · sectors · panels", "Exposure, municipalities,\nadditional inundation, uncertainty"],
        "f": ["DEM hold-out (30% tracks)\n+ semivariogram ℓ", "Tidal inundation vs\nSentinel-2 high/low-tide pairs",
              "Sensitivity: DEM, connectivity,\nℓ, VLM, tide amplification", "Convergence N/2 vs N",
              "O1 × O2 × O3 (hydrodynamic)\nSalvador sub-domain"],
    },
    "pt": {
        "A": "A · Aquisição de dados abertos (scripts 01–14; sem contas e sem tarefas no GEE)",
        "B": "B · Pré-processamento e calibração",
        "C": "C · Pacotes de entrada por setor (script 20)",
        "D": "D · Modelo O2 — Monte Carlo, N = 500 (script 21)",
        "E": "E · Produtos (scripts 21–22, 26–27)",
        "F": "F · Validação, sensibilidade e verificação estrutural (scripts 23–25b, 24, 28)",
        "a": ["Zona costeira e setores\nmalhas do IBGE", "Relevo\nFABDEM V1-2 · Copernicus GLO-30",
              "Cobertura da terra\nMapBiomas (API) · JRC GSW", "Exposição\nGHS-POP 2025 · MS Buildings",
              "Projeções do nível do mar\nIPCC AR6 (HTTP range)", "Marégrafo\nUHSLC 708 · RMPG/IBGE",
              "Ondas\nERA5 (Open-Meteo)", "Alturas de referência\nICESat-2 ATL08 (SlideRule)",
              "Geoide e altitude normal\nEGM2008 · hgeoHNOR2020"],
        "b": ["Cadeia vertical\nh = H + N;  $H_N$ = h − η\nz = $H_N$ − NMM (Eqs 1–4)",
              "Níveis de maré e transferência\nMHWS, MHHW\nrazão $f_s$ (Eqs 7–9)", "Extremos POT–GPD\nbootstrap · retroteste (Eq 10)",
              "Setup de ondas\nStockdon (Eq 11)", "Erro do DEM por cobertura\nviés $b_c$, $s_c$ do ICESat-2 (Eq 13)",
              "Máscara do mar\nfaixa marinha ∪ água conectada", "Grades de exposição\npopulação · edificações (30 m)"],
        "c": "6 setores · EPSG:31984 · 30 m · dem/landcover/sea/pop/buildings + params.json",
        "d": ["Sorteio $u_k$ ~ U(0,1)\n$\\Delta RSL(t;u_k)$ (Eqs 5–6)", "Nível de referência $L_k$\nMHWS / NMM / $z_T$ + setup (Eq 12)",
              "Erro do DEM correlacionado\n$\\varepsilon_k$ = $G_\\ell * w$ (Eq 14)", "$z_k = z - b_c - s_c\\,\\varepsilon_k$\n(Eq 13)",
              "Inundação conectada\npara cada SSP × ano (Eqs 15–16)", "Acumulação\n$\\hat p$, se($\\hat p$), exposição (Eqs 17–18)"],
        "e": ["GeoTIFFs de probabilidade\n16 combinações", "Classes IPCC de probabilidade\náreas (ha) por setor e costa",
              "Mapas (600 dpi)\ncosta · setores · painéis", "Exposição, municípios,\ninundação adicional, incerteza"],
        "f": ["Retenção do DEM (30% passagens)\n+ variograma ℓ", "Inundação pela maré ×\npares Sentinel-2 preamar/baixa-mar",
              "Sensibilidade: DEM, conectividade,\nℓ, VLM, amplificação da maré", "Convergência N/2 × N",
              "O1 × O2 × O3 (hidrodinâmico)\nsubdomínio de Salvador"],
    },
}
COR = {"A": "#e8f1f8", "B": "#fff4e0", "C": "#eeeeee", "D": "#fde8e4", "E": "#e6f4ea", "F": "#efe9f7"}
BORDA = {"A": "#3b6f9e", "B": "#d08c1a", "C": "#666666", "D": "#bd0026", "E": "#2e8b57", "F": "#6a4c9c"}


def caixa(ax, x, y, w, h, txt, cor, borda, fs=7.2, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.008", fc=cor, ec=borda, lw=0.9))
    ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal",
            linespacing=1.15)


def seta(ax, p0, p1, cor="#333"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=9, lw=1.0, color=cor))


def grupo(ax, y, h, chave, t):
    ax.add_patch(FancyBboxPatch((0.01, y), 0.98, h, boxstyle="round,pad=0.004,rounding_size=0.012", fc=COR[chave],
                                ec=BORDA[chave], lw=1.2))
    ax.text(0.025, y + h - 0.012, t[chave], fontsize=8.6, fontweight="bold", color=BORDA[chave], va="top")


def desenhar(lang, out):
    t = T[lang]
    fig = plt.figure(figsize=(7.2, 9.6))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    # A
    grupo(ax, 0.775, 0.215, "A", t)
    w, h = 0.30, 0.044
    for i, s in enumerate(t["a"]):
        r, c = divmod(i, 3)
        caixa(ax, 0.035 + c * 0.32, 0.930 - r * 0.052 - h, w, h, s, "white", BORDA["A"])
    # B
    grupo(ax, 0.575, 0.185, "B", t)
    for i, s in enumerate(t["b"]):
        r, c = divmod(i, 4)
        caixa(ax, 0.030 + c * 0.2375, 0.660 - r * 0.075, 0.225, 0.066, s, "white", BORDA["B"], fs=6.6)
    seta(ax, (0.5, 0.775), (0.5, 0.760))
    # C
    grupo(ax, 0.505, 0.055, "C", t)
    ax.text(0.5, 0.519, t["c"], ha="center", va="center", fontsize=7.4)
    seta(ax, (0.5, 0.575), (0.5, 0.560))
    # D (2 linhas × 3)
    grupo(ax, 0.29, 0.20, "D", t)
    pos = [(0.04, 0.385), (0.36, 0.385), (0.68, 0.385), (0.68, 0.300), (0.36, 0.300), (0.04, 0.300)]
    for i, ((x, y), s) in enumerate(zip(pos, t["d"])):
        caixa(ax, x, y, 0.28, 0.068, s, "white", BORDA["D"], fs=6.8)
    for a_, b_ in [((0.32, 0.419), (0.36, 0.419)), ((0.64, 0.419), (0.68, 0.419)), ((0.82, 0.385), (0.82, 0.368)),
                   ((0.68, 0.334), (0.64, 0.334)), ((0.36, 0.334), (0.32, 0.334))]:
        seta(ax, a_, b_, BORDA["D"])
    ax.annotate("", xy=(0.18, 0.453), xytext=(0.04, 0.334),
                arrowprops=dict(arrowstyle="-|>", color=BORDA["D"], lw=0.9, ls="--", connectionstyle="arc3,rad=-0.6"))
    ax.text(0.018, 0.40, "k = 1…N", rotation=90, fontsize=7, color=BORDA["D"], va="center")
    seta(ax, (0.5, 0.505), (0.5, 0.490))
    # E
    grupo(ax, 0.165, 0.11, "E", t)
    for i, s in enumerate(t["e"]):
        caixa(ax, 0.030 + i * 0.2375, 0.172, 0.225, 0.062, s, "white", BORDA["E"], fs=6.8)
    seta(ax, (0.5, 0.29), (0.5, 0.275))
    # F (2 linhas)
    grupo(ax, 0.003, 0.157, "F", t)
    pf = [(0.03, 0.068), (0.35, 0.068), (0.67, 0.068), (0.19, 0.010), (0.51, 0.010)]
    for (x, y), s in zip(pf, t["f"]):
        caixa(ax, x, y, 0.30, 0.052, s, "white", BORDA["F"], fs=6.8)
    seta(ax, (0.5, 0.165), (0.5, 0.155))
    for ext in ("png", "pdf", "svg"):
        fig.savefig(os.path.join(out, f"Fig_fluxograma_{lang}.{ext}"), dpi=600 if ext == "png" else None)
    plt.close(fig)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    for lang in ("en", "pt"):
        desenhar(lang, out)
    print("ok", out)
