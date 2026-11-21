"""22 — Mapas finais do Modelo 2 no padrão de periódico Q1 (largura de página dupla, 7,2 in; 600 dpi + PDF).

Layout com posições em polegadas (sem sobreposição): mapas em grade; legenda e créditos em faixa própria abaixo;
escala e norte sobre caixa branca no oceano; lat/lon apenas nas bordas externas; fontes de 8–11 pt.
Figuras: (1) mapa da costa por combinação, com painel lateral (localização, legenda, áreas em ha, créditos);
(2) painéis da costa por horizonte (5 SSPs); (3) painéis por setor (Atual + cenários-chave); (4) áreas (ha).
Uso: python 22_mapas_O2_Q1.py [--amostra S2]   (gera só o painel do setor indicado, para validação)
"""
import argparse
import glob
import os
import re

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from matplotlib import patheffects as pe
from matplotlib.colors import ListedColormap
from matplotlib.patches import FancyArrow, FancyBboxPatch, Patch, Rectangle
from pyproj import Transformer

import _v2

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = os.environ.get("COASTSHIFT_RESULTADOS", os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia"))
CORES = ["#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"]          # ColorBrewer YlOrRd (seguro p/ daltonismo)
ROT = ["Unlikely (0.05–0.33)", "About as likely as not (0.33–0.66)", "Likely (0.66–0.90)", "Very likely (≥ 0.90)"]
SSP_LAB = {"atual": "Present day", "ssp119": "SSP1-1.9", "ssp126": "SSP1-2.6", "ssp245": "SSP2-4.5",
           "ssp370": "SSP3-7.0", "ssp585": "SSP5-8.5"}
LAND, OCEAN, EDGE = "#e7e7e3", "#e8f1f7", "#7a7a7a"
CREDIT = ("CRS: SIRGAS 2000 / UTM 24S (EPSG:31984). Model: CoastShift O2, probabilistic connected static model "
          "(N = {n}; {ref}). Present day: MSL epoch 2004–2024. Data: IPCC AR6; FABDEM V1-2; MapBiomas; "
          "ICESat-2 (SlideRule); IBGE; UHSLC; ERA5.")
W_PAGE = 7.2
REF_TXT = {"MHWS": "mean high water springs (MHWS)", "MHHW": "mean higher high water (MHHW)",
           "NMM": "mean sea level (MSL; permanent inundation)"}


def ref_txt(ref):
    return REF_TXT.get(ref, f"the {ref[2:]}-year return level (episodic)" if str(ref).startswith("TR") else ref)

FS = {"tick": 8, "title": 9.5, "leg": 9, "legt": 9.5, "cred": 7, "sup": 11}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.linewidth": 0.6, "savefig.dpi": 600,
                     "pdf.fonttype": 42, "axes.titlepad": 3})
TR = Transformer.from_crs("EPSG:4326", _v2.CRS, always_xy=True)
INV = Transformer.from_crs(_v2.CRS, "EPSG:4326", always_xy=True)


# ----------------------------------------------------------------------------- dados de base
def bases():
    f = _v2.p("aoi", "ibge_uf.geojson")
    if not os.path.exists(f):
        _v2.salvar_json(_v2.get_json("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR",
                                     {"formato": "application/vnd.geo+json", "qualidade": "minima", "intrarregiao": "UF"}),
                        "aoi", "ibge_uf.geojson")
    uf = gpd.read_file(f).to_crs(_v2.CRS)
    ba = gpd.read_file(_v2.p("aoi", "ibge_bahia.geojson")).to_crs(_v2.CRS)
    _, st = _v2.aoi()
    return uf, ba, st.to_crs(_v2.CRS)


def ler(f, fator, masc0=True):
    with rasterio.open(f) as r:
        a = r.read(1)
        b = r.bounds
    a = np.where(a == 255, 0, a)
    if fator > 1:                                         # agregação por máximo (preserva feições estreitas)
        h, w = (a.shape[0] // fator) * fator, (a.shape[1] // fator) * fator
        a = a[:h, :w].reshape(h // fator, fator, w // fator, fator).max(axis=(1, 3))
        b = rasterio.coords.BoundingBox(b.left, b.top - h * 30.0, b.left + w * 30.0, b.top)
    return (np.ma.masked_equal(a, 0) if masc0 else a), (b.left, b.right, b.bottom, b.top)


def arquivo(setor, cen, ano):
    return os.path.join(OUT, "geotiff", f"classe_{setor}_{cen}_{ano}.tif")


# ----------------------------------------------------------------------------- elementos cartográficos
def desenhar(ax, setores, cen, ano, uf, ba, st, fator, lims):
    ax.set_facecolor(OCEAN)
    uf.plot(ax=ax, fc=LAND, ec="#c4c4c4", lw=0.4, zorder=1)
    ba.boundary.plot(ax=ax, ec=EDGE, lw=0.5, zorder=2)
    for s in setores:
        a_s, e_s = ler(os.path.join(_v2.BASE, "pacotes", s, "sea.tif"), fator)       # baías/estuários = água
        ax.imshow(a_s, extent=e_s, cmap=ListedColormap([OCEAN]), vmin=0.5, vmax=1.5, interpolation="nearest", zorder=2.5)
        a, e = ler(arquivo(s, cen, ano), fator)
        ax.imshow(a, extent=e, cmap=ListedColormap(CORES), vmin=0.5, vmax=4.5, interpolation="nearest", zorder=3)
    st.boundary.plot(ax=ax, ec="#555555", lw=0.45, linestyle="--", zorder=4)
    ax.set_xlim(lims[0], lims[1])
    ax.set_ylim(lims[2], lims[3])
    ax.set_aspect("equal")


def passo_grade(lims):
    span = max(INV.transform(lims[1], lims[2])[0] - INV.transform(lims[0], lims[2])[0],
               INV.transform(lims[0], lims[3])[1] - INV.transform(lims[0], lims[2])[1])
    return next(p for p in (0.1, 0.25, 0.5, 1.0, 2.0) if span / p <= 5)


def graticule(ax, passo, esquerda=True, baixo=True, fs=None, bold=False, passo_y=None):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    lo0, la0 = INV.transform(x0, y0)
    lo1, la1 = INV.transform(x1, y1)
    xt, xl, yt, yl = [], [], [], []
    fmt = (lambda v: f"{abs(v):.0f}°") if passo >= 1 else (lambda v: f"{abs(v):.2f}°".rstrip("0").rstrip(".") + "°"
                                                            if False else f"{abs(v):g}°")
    for lon in np.arange(np.ceil(lo0 / passo) * passo, lo1, passo):
        xs, ys = TR.transform(np.full(60, lon), np.linspace(la0 - 1, la1 + 1, 60))
        ax.plot(xs, ys, lw=0.35, color="#a8a8a8", ls=(0, (3, 3)), zorder=1.6)
        xb = TR.transform(lon, (la0 + la1) / 2)[0]
        if x0 + 0.04 * (x1 - x0) < xb < x1 - 0.04 * (x1 - x0):
            xt.append(xb)
            xl.append(fmt(lon) + ("W" if lon < 0 else "E"))
    py = passo_y or passo
    for lat in np.arange(np.ceil(la0 / py) * py, la1, py):
        xs, ys = TR.transform(np.linspace(lo0 - 1, lo1 + 1, 60), np.full(60, lat))
        ax.plot(xs, ys, lw=0.35, color="#a8a8a8", ls=(0, (3, 3)), zorder=1.6)
        yb = TR.transform((lo0 + lo1) / 2, lat)[1]
        if y0 + 0.03 * (y1 - y0) < yb < y1 - 0.03 * (y1 - y0):
            yt.append(yb)
            yl.append(fmt(lat) + ("S" if lat < 0 else "N"))
    ax.set_xticks(xt, xl if baixo else [""] * len(xt))
    ax.set_yticks(yt, yl if esquerda else [""] * len(yt), rotation=90, va="center")
    ax.tick_params(length=2.5, direction="in", labelsize=fs or FS["tick"], top=True, right=True, pad=2)
    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_fontweight("bold" if bold else "normal")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)


def escala_norte(ax, canto="lr", norte=True, k=1.0, fs=None, fsn=None):
    """Barra de escala e seta de norte, cada uma numa caixa branca dimensionada em polegadas (sem cortes)."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    larg, alt = x1 - x0, y1 - y0
    fw, fh = ax.figure.get_size_inches()
    pos = ax.get_position()
    fx, fy = larg / (pos.width * fw), alt / (pos.height * fh)          # unidades de mapa por polegada
    km = next(v for v in (200, 100, 50, 40, 20, 10, 4, 2, 1) if v * 1000 <= 0.40 * larg)
    L = km * 1000
    bw, bh = L + 0.62 * k * fx, 0.36 * k * fy
    m = 0.06 * k
    bx = x1 - bw - m * fx if canto[1] == "r" else x0 + m * fx
    by = y0 + m * fy
    ax.add_patch(FancyBboxPatch((bx, by), bw, bh, boxstyle=f"round,pad=0,rounding_size={0.03 * fx}", fc="white",
                                ec="#9a9a9a", lw=0.4, alpha=0.93, zorder=8))
    sx, sy, h = bx + 0.12 * k * fx, by + 0.09 * k * fy, 0.06 * k * fy
    for i in range(2):
        ax.add_patch(Rectangle((sx + i * L / 2, sy), L / 2, h, fc="k" if i == 0 else "w", ec="k", lw=0.5, zorder=9))
    marcas = [(0, sx), (km / 2, sx + L / 2), (km, sx + L)] if L / fx >= 1.0 else [(0, sx), (km, sx + L)]
    for v, xx in marcas:
        ax.text(xx, sy + h + 0.03 * k * fy, f"{v:g}" + (" km" if v == km else ""), ha="center", va="bottom",
                fontsize=fs or FS["tick"], zorder=9)
    if norte:
        nw, nh = 0.30 * k * fx, 0.46 * k * fy
        nx0, ny0 = x0 + m * fx, y1 - nh - m * fy              # canto superior esquerdo (continente)
        ax.add_patch(FancyBboxPatch((nx0, ny0), nw, nh, boxstyle=f"round,pad=0,rounding_size={0.03 * fx}", fc="white",
                                    ec="#9a9a9a", lw=0.4, alpha=0.93, zorder=8))
        cx, Ln = nx0 + nw / 2, 0.22 * k * fy
        ax.add_patch(FancyArrow(cx, ny0 + 0.05 * k * fy, 0, Ln, width=0.05 * k * fx, head_width=0.17 * k * fx, head_length=0.10 * k * fy,
                                length_includes_head=True, fc="k", ec="k", zorder=9))
        ax.text(cx, ny0 + 0.29 * k * fy, "N", ha="center", va="bottom", fontsize=fsn or FS["leg"], fontweight="bold", zorder=9)


def legenda_ax(fig, rect, ncol, titulo="Probability of connected inundation (IPCC calibrated likelihood)",
               fs=None, fst=None, loc="center"):
    ax = fig.add_axes(rect)
    ax.axis("off")
    hs = [Patch(fc=c, ec="#555", lw=0.3, label=lab) for c, lab in zip(CORES, ROT)]
    lg = ax.legend(handles=hs, loc=loc, ncol=ncol, title=titulo, title_fontsize=fst or FS["legt"],
                   fontsize=fs or FS["leg"], frameon=False, handlelength=1.7, handleheight=1.1, columnspacing=0.9, handletextpad=0.5,
                   alignment="left")
    lg.get_title().set_fontweight("bold")
    return ax


def credito(fig, y_in, texto, H):
    fig.text(0.5, y_in / H, texto, ha="center", va="top", fontsize=FS["cred"], color="#3c3c3c", wrap=True)


def limites(geo, pad_rel=0.04):
    x0, y0, x1, y1 = geo.total_bounds
    p = pad_rel * max(x1 - x0, y1 - y0)
    return (x0 - p, x1 + p, y0 - p, y1 + p)


def grade(nr, nc, aspect, W=W_PAGE, esq=0.48, dir_=0.12, wgap=0.10, hgap=0.42, topo=0.55, base=1.25, hmax=9.3):
    """Cria figura com nr×nc mapas de razão largura/altura 'aspect'. Retorna fig, eixos, (H, y_base_in)."""
    pw = (W - esq - dir_ - (nc - 1) * wgap) / nc
    ph = pw / aspect
    H = topo + nr * ph + (nr - 1) * hgap + base
    if H > hmax:                                          # reduz a largura dos painéis para caber na página
        ph = (hmax - topo - base - (nr - 1) * hgap) / nr
        pw = ph * aspect
        H = hmax
    tot_w = nc * pw + (nc - 1) * wgap
    x_ini = esq + (W - esq - dir_ - tot_w) / 2
    fig = plt.figure(figsize=(W, H))
    axs = []
    for i in range(nr):
        for j in range(nc):
            l = x_ini + j * (pw + wgap)
            b = H - topo - (i + 1) * ph - i * hgap
            axs.append(fig.add_axes([l / W, b / H, pw / W, ph / H]))
    return fig, axs, H


def salvar(fig, nome):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, "mapas", f"{nome}.{ext}"), dpi=600 if ext == "png" else None)
    plt.close(fig)


def letra(i):
    return f"({chr(97 + i)})"


# ----------------------------------------------------------------------------- figuras
def escala_externa(fig, ax_ref, x_in, y_in, fs=FS["tick"] + 1, lmax=1.05):
    """Barra de escala e norte FORA dos mapas, na faixa inferior, com a escala real do mapa de referência."""
    fw, fh = fig.get_size_inches()
    pos = ax_ref.get_position()
    fx = (ax_ref.get_xlim()[1] - ax_ref.get_xlim()[0]) / (pos.width * fw)      # m por polegada
    km = next(v for v in (200, 100, 50, 40, 20, 10, 5, 2, 1) if v * 1000 / fx <= lmax)
    Lin = km * 1000 / fx
    a = fig.add_axes([(x_in + 0.55) / fw, y_in / fh, Lin / fw, 0.08 / fh])
    a.set_xlim(0, km)
    a.set_ylim(0, 1)
    a.axis("off")
    a.add_patch(Rectangle((0, 0), km / 2, 1, fc="k", ec="k", lw=0.6))
    a.add_patch(Rectangle((km / 2, 0), km / 2, 1, fc="w", ec="k", lw=0.6))
    for v in ((0, km / 2, km) if Lin >= 1.2 else (0, km)):
        a.text(v, 1.6, f"{v:g}" + (" km" if v == km else ""), ha="center", va="bottom", fontsize=fs,
               fontweight="bold")
    n = fig.add_axes([x_in / fw, (y_in - 0.10) / fh, 0.36 / fw, 0.62 / fh])
    n.axis("off")
    n.add_patch(FancyArrow(0.5, 0.0, 0, 0.62, width=0.16, head_width=0.55, head_length=0.28,
                           length_includes_head=True, fc="k", ec="k", transform=n.transAxes))
    n.text(0.5, 0.68, "N", ha="center", va="bottom", fontsize=fs + 1, fontweight="bold", transform=n.transAxes)


FC = {"sup": 17, "sub": 12.5, "pt": 12.5, "tick": 10.5, "leg": 10.5, "legt": 11.5, "esc": 11.5}   # figuras compostas


def faixa_inferior(fig, ax_ref, H, ncol=2):
    """Legenda em uma coluna (símbolo | classe | intervalo de p alinhado à direita); norte e escala à direita."""
    X = lambda v: v / W_PAGE                                          # noqa: E731
    Yb = lambda v: v / H                                              # noqa: E731
    fig.text(X(0.42), Yb(1.52), "Probability of connected inundation (IPCC calibrated likelihood)",
             fontsize=FC["legt"], fontweight="bold", va="top")
    itens = [("Unlikely", "0.05–0.33"), ("About as likely as not", "0.33–0.66"),
             ("Likely", "0.66–0.90"), ("Very likely", "≥ 0.90")]
    for k, (nome, faixa) in enumerate(itens):
        y = 1.12 - 0.27 * k
        fig.add_artist(Rectangle((X(0.42), Yb(y - 0.08)), X(0.32), Yb(0.17), fc=CORES[k], ec="#555", lw=0.5))
        fig.text(X(0.88), Yb(y), nome, fontsize=FC["leg"], va="center")
        fig.text(X(3.55), Yb(y), faixa, fontsize=FC["leg"], va="center", ha="right", color="#333")
    escala_externa(fig, ax_ref, 4.85, 0.62, fs=FC["esc"], lmax=1.05)


def cabecalho(fig, H, titulo, sub):
    fig.text(0.42 / W_PAGE, 1 - 0.10 / H, titulo, fontsize=FC["sup"], fontweight="bold", va="top")
    fig.text(0.42 / W_PAGE, 1 - 0.46 / H, sub, fontsize=FC["sub"], va="top")


def fig_setor(setor, meta, uf, ba, st, n, ref, ano_base):
    s1 = st[st.setor == setor]
    lim = limites(s1)
    asp = (lim[1] - lim[0]) / (lim[3] - lim[2])
    painel = [("atual", ano_base), ("ssp245", 2050), ("ssp585", 2050), ("ssp126", 2100), ("ssp245", 2100), ("ssp585", 2100)]
    painel = [c for c in painel if os.path.exists(arquivo(setor, *c))]
    nr, nc = (1, len(painel)) if asp < 0.55 else (2, int(np.ceil(len(painel) / 2)))
    estreito = nr == 1
    fig, axs, H = grade(nr, nc, asp, esq=0.55, base=1.80, topo=1.62 if estreito else 1.32, hgap=0.78,
                        wgap=0.20 if estreito else 0.12, hmax=9.6)
    pw_in = axs[0].get_position().width * W_PAGE
    span = INV.transform(lim[1], lim[2])[0] - INV.transform(lim[0], lim[2])[0]
    passo = next(p for p in (0.1, 0.25, 0.5, 1.0, 2.0) if span / p <= max(1.0, pw_in / 1.1))
    span_y = INV.transform(lim[0], lim[3])[1] - INV.transform(lim[0], lim[2])[1]
    passo_y = next(p for p in (0.1, 0.25, 0.5, 1.0, 2.0) if span_y / p <= max(1.0, pw_in / asp / 0.75))
    fator = 2 if (lim[1] - lim[0]) > 60000 else 1
    for k, (ax, (cen, ano)) in enumerate(zip(axs, painel)):
        desenhar(ax, [setor], cen, ano, uf, ba, s1, fator, lim)
        graticule(ax, passo, esquerda=(k % nc == 0), baixo=(k // nc == nr - 1), fs=FC["tick"], bold=True,
                  passo_y=passo_y)
        for sp in ax.spines.values():
            sp.set_linewidth(1.0)
        r = meta[(meta.setor == setor) & (meta.cenario == cen) & (meta.ano == ano)].iloc[0]
        tit = "Present day" if cen == "atual" else f"{SSP_LAB[cen]} · {ano}"
        if estreito:                                                  # quadros estreitos: título em 3 linhas
            l1, l2 = ("Present", "day") if cen == "atual" else (SSP_LAB[cen], str(ano))
            ax.set_title(f"{letra(k)} {l1}\n{l2}\n{r.area_esperada_ha:,.0f} ha", fontsize=10, fontweight="bold",
                         loc="left", linespacing=1.1)
        else:
            ax.set_title(f"{letra(k)} {tit}\nE[A] = {r.area_esperada_ha:,.0f} ha", fontsize=FC["pt"],
                         fontweight="bold", loc="left", linespacing=1.15)
    for ax in axs[len(painel):]:
        ax.remove()
    nome = {"S2_Salvador_BTS": "Salvador and Todos os Santos Bay"}.get(setor, " ".join(setor.split("_")[1:]))
    cabecalho(fig, H, f"{setor.split('_')[0]} — {nome}", f"Probability of connected inundation at {ref_txt(ref)}")
    faixa_inferior(fig, axs[0], H)
    salvar(fig, f"Fig_setor_{setor}")


def fig_costa(cen, ano, meta, uf, ba, st, n, ref):
    x0, x1, y0, y1 = limites(st, 0.015)
    W, H = W_PAGE, 9.8
    mh = H - 0.55
    mw = W - 0.62 - 0.22 - 2.75 - 0.08                               # coluna direita com 2,75 in
    asp = mw / mh
    x1 = max(x1, x0 + asp * (y1 - y0))                               # completa com oceano a leste
    yc, hh = (y0 + y1) / 2, (x1 - x0) / asp / 2
    y0, y1 = yc - hh, yc + hh
    lim = (x0, x1, y0, y1)
    fs = {"tick": 11, "lab": 15, "tit": 17, "sub": 13, "sec": 12.5, "leg": 11.5}
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0.62 / W, 0.40 / H, mw / W, mh / H])
    desenhar(ax, list(_v2.SETORES), cen, ano, uf, ba, st, 5, lim)
    graticule(ax, 1.0)
    ax.tick_params(labelsize=fs["tick"], length=4)
    for sp in ax.spines.values():
        sp.set_linewidth(1.2)
    for _, r in st.iterrows():
        c = r.geometry.representative_point()
        ax.text(c.x + 26000, c.y, r.setor.split("_")[0], fontsize=fs["lab"], fontweight="bold", color="#111111",
                path_effects=[pe.withStroke(linewidth=3, foreground="w")], zorder=7)
    if cen == "atual":                                                # Fig. 1: marégrafo e subdomínio do O3
        tr = Transformer.from_crs("EPSG:4326", _v2.CRS, always_xy=True)
        gx, gy = tr.transform(*_v2.SALVADOR)
        f_sub = os.path.join(OUT, "validacao", "_subdominio_salvador", "dem.tif")
        if os.path.exists(f_sub):
            with rasterio.open(f_sub) as r_:
                b_ = r_.bounds
                t2 = Transformer.from_crs(r_.crs, _v2.CRS, always_xy=True)
            xs, ys = t2.transform([b_.left, b_.right, b_.right, b_.left], [b_.bottom, b_.bottom, b_.top, b_.top])
            ax.add_patch(Rectangle((min(xs), min(ys)), max(xs) - min(xs), max(ys) - min(ys), fc="none",
                                   ec="#0057a3", lw=1.6, zorder=8))
        ax.plot(gx, gy, marker="^", ms=9, mfc="#0057a3", mec="w", mew=1.0, zorder=9, ls="none")
        ax.annotate("Salvador\ntide gauge (▲)\nO3 subdomain (□)", xy=(gx, gy), xytext=(gx + 12000, gy - 50000),
                    fontsize=fs["leg"] - 1, color="#0057a3", fontweight="bold", va="top", zorder=9,
                    arrowprops=dict(arrowstyle="-", color="#0057a3", lw=1.0),
                    path_effects=[pe.withStroke(linewidth=3, foreground="w")])
    escala_norte(ax, "lr", k=1.45, fs=12, fsn=14)
    xr_in = 0.62 + mw + 0.22
    wr_in = W - xr_in - 0.08
    X = lambda v: v / W                                               # noqa: E731
    Y = lambda v: 1 - v / H                                           # noqa: E731
    xr, wr = X(xr_in), X(wr_in)
    regua = lambda y: fig.add_artist(plt.Line2D([xr, xr + wr], [Y(y), Y(y)], color="#222", lw=1.0))  # noqa: E731
    tit = "Present day (MSL 2004–2024)" if cen == "atual" else f"{SSP_LAB[cen]}, {ano}"
    fig.text(xr, Y(0.18), "Probability of\nconnected\ninundation —\ncoast of Bahia", fontsize=fs["tit"],
             fontweight="bold", va="top", linespacing=1.05)
    fig.text(xr, Y(1.48), f"{tit}\n{ref}" if len(f"{tit} · {ref}") > 26 else f"{tit} · {ref}", fontsize=fs["sub"], va="top")
    regua(1.95)
    fig.text(xr, Y(2.05), "Location (Brazil)", fontsize=fs["sec"], fontweight="bold", va="top")
    loc = fig.add_axes([X(xr_in), Y(4.62), X(wr_in), 2.30 / H])
    uf.plot(ax=loc, fc=LAND, ec="#9a9a9a", lw=0.35)
    ba.plot(ax=loc, fc="#b8b8b8", ec="#444", lw=0.5)
    st.dissolve().plot(ax=loc, fc="#d7191c", ec="#d7191c", lw=1.3)
    loc.set_facecolor(OCEAN)
    loc.set_xticks([])
    loc.set_yticks([])
    regua(4.78)
    fig.text(xr, Y(4.88), "Inundation probability\n(IPCC calibrated likelihood)", fontsize=fs["sec"],
             fontweight="bold", va="top", linespacing=1.1)
    rotulos = ["Unlikely (0.05–0.33)", "About as likely as not\n(0.33–0.66)", "Likely (0.66–0.90)", "Very likely (≥ 0.90)"]
    y = 5.45
    for cor, lab in zip(CORES, rotulos):
        alto = 0.44 if "\n" in lab else 0.27
        fig.add_artist(Rectangle((xr, Y(y + 0.22)), X(0.42), 0.20 / H, fc=cor, ec="#555", lw=0.5))
        fig.text(X(xr_in + 0.52), Y(y + 0.02), lab, fontsize=fs["leg"], va="top", linespacing=1.05)
        y += alto + 0.06
    regua(y + 0.05)
    t = meta[(meta.setor == "TOTAL_COSTA_BAHIA") & (meta.cenario == cen) & (meta.ano == ano)].iloc[0]
    fig.text(xr, Y(y + 0.17), "Area by class (ha)", fontsize=fs["sec"], fontweight="bold", va="top")
    linhas = [("Unlikely", t.improvavel_ha), ("About as likely as not", t.tao_provavel_quanto_nao_ha),
              ("Likely", t.provavel_ha), ("Very likely", t.muito_provavel_ha), ("Expected area E[A]", t.area_esperada_ha)]
    for i_, (nome, v) in enumerate(linhas):
        yy = y + 0.55 + 0.27 * i_
        fig.text(xr, Y(yy), nome, fontsize=fs["leg"], va="top")
        fig.text(xr + wr, Y(yy), f"{v:,.0f}", fontsize=fs["leg"], va="top", ha="right")
    regua(y + 0.55 + 0.27 * len(linhas) + 0.08)
    salvar(fig, f"Fig_costa_{cen}_{ano}")


def fig_painel_ano(ano, ssps, uf, ba, st, n, ref):
    lim = limites(st, 0.02)
    asp = (lim[1] - lim[0]) / (lim[3] - lim[2])
    fig, axs, H = grade(1, len(ssps), asp, esq=0.55, base=1.80, topo=1.15, wgap=0.10, hmax=9.6)
    for k, (ax, ssp) in enumerate(zip(axs, ssps)):
        desenhar(ax, list(_v2.SETORES), ssp, ano, uf, ba, st, 8, lim)
        graticule(ax, 2.0, esquerda=(k == 0), fs=FC["tick"], bold=True)
        for sp in ax.spines.values():
            sp.set_linewidth(1.0)
        ax.set_title(f"{letra(k)} {SSP_LAB[ssp]}", fontsize=FC["pt"], fontweight="bold", loc="left")
    cabecalho(fig, H, f"Coast of Bahia — {ano}", f"Probability of connected inundation at {ref_txt(ref)}")
    faixa_inferior(fig, axs[0], H)
    salvar(fig, f"Fig_painel_costa_{ano}")


def fig_areas(meta, ssps, anos, ano_base):
    d = meta[meta.setor != "TOTAL_COSTA_BAHIA"]
    cols = ["improvavel_ha", "tao_provavel_quanto_nao_ha", "provavel_ha", "muito_provavel_ha"]
    setores = list(_v2.SETORES)
    fig, axs, H = None, None, None
    fig = plt.figure(figsize=(W_PAGE, 6.6))
    H = 6.6
    larg = (W_PAGE - 0.75 - 0.15) / len(anos)
    axs = [fig.add_axes([(0.75 + i * larg) / W_PAGE, 1.75 / H, (larg - 0.12) / W_PAGE, 4.3 / H]) for i in range(len(anos))]
    grupos = ["atual"] + ssps
    w = 0.8 / len(grupos)
    ymax = 0
    for k, ano in enumerate(anos):
        ax = axs[k]
        x = np.arange(len(setores))
        for j, g in enumerate(grupos):
            dd = d[(d.cenario == g) & (d.ano == (ano_base if g == "atual" else ano))].set_index("setor").reindex(setores)
            bot = np.zeros(len(x))
            xx = x + (j - (len(grupos) - 1) / 2) * w
            for c, cor in zip(cols, CORES):
                ax.bar(xx, dd[c].values / 1000, w * 0.9, bottom=bot, color=cor, ec="#444" if g == "atual" else "w",
                       lw=0.6 if g == "atual" else 0.3, hatch="////" if g == "atual" else None)
                bot += dd[c].values / 1000
            ymax = max(ymax, bot.max())
        ax.set_xticks(x, [s.split("_")[0] for s in setores], fontsize=FS["tick"] + 0.5)
        ax.set_title(f"{letra(k)} {ano}", loc="left", fontsize=FS["title"])
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", lw=0.4, color="#dddddd")
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=FS["tick"])
        if k:
            ax.set_yticklabels([])
    for ax in axs:
        ax.set_ylim(0, ymax * 1.05)
    axs[0].set_ylabel("Area with p ≥ 0.05 (10³ ha)", fontsize=FS["leg"])
    fig.text(0.75 / W_PAGE, 1 - 0.15 / H, "Inundated area by probability class, sector and scenario (MHWS)",
             fontsize=FS["sup"], fontweight="bold", va="top")
    fig.text(0.75 / W_PAGE, 1.40 / H, "Bars within each sector, left to right: hatched = present day; then "
             + ", ".join(SSP_LAB[s] for s in ssps[:2]) + ",\n" + ", ".join(SSP_LAB[s] for s in ssps[2:])
             + ".", fontsize=FS["leg"], va="top", linespacing=1.3)
    legenda_ax(fig, [0.04, 0.25 / H, 0.92, 0.75 / H], ncol=2, titulo="Probability class")
    salvar(fig, "Fig_areas_ha_por_setor")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--amostra", default="")
    ap.add_argument("--so", default="", help="gera só: setores,areas,costa,paineis (separados por vírgula)")
    a = ap.parse_args()
    os.makedirs(os.path.join(OUT, "mapas"), exist_ok=True)
    meta = pd.read_csv(os.path.join(OUT, "tabelas", "areas_por_classe_ha.csv"))
    n, ref = int(meta.N.iloc[0]), meta.ref.iloc[0]
    uf, ba, st = bases()
    combos = sorted({re.search(r"_(ssp\d{3}|atual)_(\d{4})\.tif$", f).groups()
                     for f in glob.glob(os.path.join(OUT, "geotiff", "classe_*.tif"))})
    combos = [(c, int(y)) for c, y in combos]
    ssps = sorted({c for c, _ in combos if c != "atual"})
    anos = sorted({y for c, y in combos if c != "atual"})
    ano_base = next((y for c, y in combos if c == "atual"), None)
    if a.amostra:
        setor = [s for s in _v2.SETORES if s.startswith(a.amostra)][0]
        fig_setor(setor, meta, uf, ba, st, n, ref, ano_base)
        fig_costa("ssp585", 2100, meta, uf, ba, st, n, ref)
        _v2.log(f"amostras geradas: Fig_setor_{setor} e Fig_costa_ssp585_2100")
        raise SystemExit
    so = set(a.so.split(",")) if a.so else {"setores", "areas", "costa", "paineis"}
    if not a.so:
        for f in glob.glob(os.path.join(OUT, "mapas", "*")):
            os.remove(f)
    if "atual" in so and ano_base:                                    # só a Fig. 1 (linha de base)
        fig_costa("atual", ano_base, meta, uf, ba, st, n, ref)
    if "costa" in so:
        for cen, ano in combos:
            fig_costa(cen, ano, meta, uf, ba, st, n, ref)
    if "paineis" in so:
        for ano in anos:
            fig_painel_ano(ano, ssps, uf, ba, st, n, ref)
    if "setores" in so:
        for setor in _v2.SETORES:
            fig_setor(setor, meta, uf, ba, st, n, ref, ano_base)
    if "areas" in so:
        fig_areas(meta, ssps, anos, ano_base)
    _v2.log(f"mapas gerados em {os.path.join(OUT, 'mapas')}")
