"""26 — Produtos complementares do Modelo 2 (após os scripts 21 e 24).

(a) Tabela por município (malha IBGE): área esperada E[A] (ha), área com p ≥ 0,5, população e edificações esperadas.
(b) Inundação adicional: células com p ≥ 0,5 já hoje / novas até 2050 / novas até 2100 (SSP2-4.5 e SSP5-8.5).
(c) Exposição por setor (população, edificações, mangue) com intervalos p05–p95.
(d) Incerteza: erro-padrão de Monte Carlo (SSP5-8.5 2100) e concordância FABDEM × Copernicus (p ≥ 0,5).
Figuras (600 dpi + PDF) em <resultados>/graficos; tabelas em <resultados>/tabelas.
"""
import glob
import importlib.util
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import ListedColormap
from rasterio.features import rasterize

import _v2

spec = importlib.util.spec_from_file_location("m22", os.path.join(os.path.dirname(__file__), "22_mapas_O2_Q1.py"))
m22 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m22)
plt = m22.plt
OUT = m22.OUT
GR, TB = os.path.join(OUT, "graficos"), os.path.join(OUT, "tabelas")
SET = list(_v2.SETORES)
ROT_SET = {s: s.split("_")[0] for s in SET}


def prob(setor, tag):
    with rasterio.open(os.path.join(OUT, "geotiff", f"prob_{setor}_{tag}.tif")) as r:
        a = r.read(1)
        return np.where(a < 0, np.nan, a), r.profile


def pacote(setor, nome):
    with rasterio.open(os.path.join(_v2.BASE, "pacotes", setor, f"{nome}.tif")) as r:
        a = r.read(1).astype("float32")
        return np.where(a == r.nodata, np.nan, a) if r.nodata is not None else a


def salvar(fig, nome):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(GR, f"{nome}.{ext}"), dpi=600 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)


def municipios():
    f = _v2.p("aoi", "ibge_municipios_ba.geojson")
    if not os.path.exists(f):
        _v2.salvar_json(_v2.get_json("https://servicodados.ibge.gov.br/api/v3/malhas/estados/29",
                                     {"formato": "application/vnd.geo+json", "qualidade": "intermediaria",
                                      "intrarregiao": "municipio"}), "aoi", "ibge_municipios_ba.geojson")
    g = gpd.read_file(f).to_crs(_v2.CRS)
    nomes = {str(m["id"]): m["nome"] for m in _v2.get_json("https://servicodados.ibge.gov.br/api/v1/localidades/estados/29/municipios")}
    g["codigo"] = g["codarea"].astype(str)
    g["municipio"] = g.codigo.map(nomes)
    return g


if __name__ == "__main__":
    os.makedirs(GR, exist_ok=True)
    tags = {"atual": "atual_2014", "ssp245_2050": "ssp245_2050", "ssp585_2050": "ssp585_2050",
            "ssp245_2100": "ssp245_2100", "ssp585_2100": "ssp585_2100"}
    # (a) municípios ---------------------------------------------------------------------------------------
    mun = municipios()
    linhas = []
    for s in SET:
        p0, prof = prob(s, "atual_2014")
        cod = rasterize([(geo, int(c)) for geo, c in zip(mun.geometry, mun.codigo)], out_shape=p0.shape,
                        transform=prof["transform"], fill=0, dtype="int32")
        pop, bld = np.nan_to_num(pacote(s, "pop")), np.nan_to_num(pacote(s, "buildings"))
        cel = 30 * 30 / 1e4
        for nome, tag in tags.items():
            p = np.nan_to_num(prob(s, tag)[0])
            df = pd.DataFrame({"cod": cod.ravel(), "p": p.ravel(), "pop": pop.ravel(), "bld": bld.ravel()})
            df = df[(df.cod > 0) & (df.p > 0)]
            df["p50"] = df.p >= 0.5
            g = df.groupby("cod").apply(lambda x: pd.Series({"E_A_ha": x.p.sum() * cel, "area_p50_ha": x.p50.sum() * cel,
                                                            "pop_esperada": (x.p * x["pop"]).sum(),
                                                            "edif_esperadas": (x.p * x.bld).sum()}))
            for c, r in g.iterrows():
                linhas.append({"codigo": str(c), "setor": s, "cenario": nome, **r.to_dict()})
    t = pd.DataFrame(linhas).groupby(["codigo", "cenario"], as_index=False)[["E_A_ha", "area_p50_ha", "pop_esperada",
                                                                            "edif_esperadas"]].sum()
    t["municipio"] = t.codigo.map(dict(zip(mun.codigo, mun.municipio)))
    piv = t.pivot_table(index=["codigo", "municipio"], columns="cenario", values=["E_A_ha", "pop_esperada"]).round(1)
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    piv = piv.reset_index().sort_values("E_A_ha_ssp585_2100", ascending=False)
    piv.to_csv(os.path.join(TB, "municipios_O2.csv"), index=False, encoding="utf-8-sig")
    top = piv.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.2, 5.6))
    y = np.arange(len(top))
    ax.barh(y + 0.27, top.E_A_ha_atual / 1000, 0.26, color="#bdbdbd", ec="#555", lw=0.4, label="Present day")
    ax.barh(y, top.E_A_ha_ssp245_2100 / 1000, 0.26, color="#fd8d3c", label="SSP2-4.5 · 2100")
    ax.barh(y - 0.27, top.E_A_ha_ssp585_2100 / 1000, 0.26, color="#bd0026", label="SSP5-8.5 · 2100")
    ax.set_yticks(y, top.municipio, fontsize=10)
    ax.set_xlabel("Expected inundated area E[A] (10³ ha)", fontsize=11)
    ax.legend(frameon=False, fontsize=10, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", lw=0.4, color="#ddd")
    ax.set_axisbelow(True)
    ax.set_title("Municipalities with the largest expected inundated area (MHWS)", fontsize=12, fontweight="bold", loc="left")
    salvar(fig, "Fig_municipios_top15")
    _v2.log("municípios: ok")
    # (b) inundação adicional --------------------------------------------------------------------------------
    uf, ba, st = m22.bases()
    cores_ad = ["#9ecae1", "#fd8d3c", "#bd0026"]
    rot_ad = ["Already inundated today (p ≥ 0.5)", "Newly inundated by 2050", "Newly inundated by 2100"]
    lim = m22.limites(st, 0.02)
    asp = (lim[1] - lim[0]) / (lim[3] - lim[2])
    fig, axs, H = m22.grade(1, 2, asp, esq=0.55, base=1.8, topo=1.15, wgap=0.35, hmax=9.6)
    areas = []
    for k, (ax, ssp) in enumerate(zip(axs, ["ssp245", "ssp585"])):
        ax.set_facecolor(m22.OCEAN)
        uf.plot(ax=ax, fc=m22.LAND, ec="#c4c4c4", lw=0.4, zorder=1)
        for s in SET:
            p0, prof = prob(s, "atual_2014")
            p50, p100 = prob(s, f"{ssp}_2050")[0], prob(s, f"{ssp}_2100")[0]
            c = np.zeros(p0.shape, "uint8")
            c[np.nan_to_num(p100) >= 0.5] = 3
            c[np.nan_to_num(p50) >= 0.5] = 2
            c[np.nan_to_num(p0) >= 0.5] = 1
            areas += [{"setor": s, "cenario": ssp, "categoria": rot_ad[i], "area_ha": float((c == i + 1).sum() * 0.09)}
                      for i in range(3)]
            f = 6
            h_, w_ = (c.shape[0] // f) * f, (c.shape[1] // f) * f
            cc = c[:h_, :w_].reshape(h_ // f, f, w_ // f, f)
            cc = np.where((cc == 1).any(axis=(1, 3)), 1, np.where((cc == 2).any(axis=(1, 3)), 2, cc.max(axis=(1, 3))))
            t_ = prof["transform"]
            ext = (t_.c, t_.c + w_ * 30, t_.f - h_ * 30, t_.f)
            ax.imshow(np.ma.masked_equal(cc, 0), extent=ext, cmap=ListedColormap(cores_ad), vmin=0.5, vmax=3.5,
                      interpolation="nearest", zorder=3)
        st.boundary.plot(ax=ax, ec="#555", lw=0.45, linestyle="--", zorder=4)
        ax.set_xlim(lim[0], lim[1])
        ax.set_ylim(lim[2], lim[3])
        m22.graticule(ax, 1.0, esquerda=(k == 0), fs=10.5, bold=True)
        ax.set_title(f"({'ab'[k]}) {m22.SSP_LAB[ssp]}", fontsize=12.5, fontweight="bold", loc="left")
    m22.cabecalho(fig, H, "Additional inundation due to sea-level rise — coast of Bahia",
                  "Cells with p ≥ 0.5 at mean high water springs (MHWS): present day and newly inundated cells")
    X, Yb = (lambda v: v / m22.W_PAGE), (lambda v: v / H)
    for i, (cor, lab) in enumerate(zip(cores_ad, rot_ad)):
        fig.add_artist(m22.Rectangle((X(0.42), Yb(1.30 - 0.32 * i - 0.08)), X(0.32), Yb(0.17), fc=cor, ec="#555", lw=0.5))
        fig.text(X(0.88), Yb(1.30 - 0.32 * i), lab, fontsize=11, va="center")
    m22.escala_externa(fig, axs[0], 4.85, 0.62, fs=11.5, lmax=1.05)
    salvar(fig, "Fig_inundacao_adicional")
    pd.DataFrame(areas).pivot_table(index=["cenario", "setor"], columns="categoria", values="area_ha").round(1).to_csv(
        os.path.join(TB, "inundacao_adicional_ha.csv"), encoding="utf-8-sig")
    _v2.log("inundação adicional: ok")
    # (c) exposição ------------------------------------------------------------------------------------------
    e = pd.read_csv(os.path.join(TB, "exposicao_O2.csv"))
    sel = [("atual", 2014, "Present day", "#bdbdbd"), ("ssp245", 2100, "SSP2-4.5 · 2100", "#fd8d3c"),
           ("ssp585", 2100, "SSP5-8.5 · 2100", "#bd0026")]
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 3.9))
    for ax, (var, tit, esc) in zip(axs, [("populacao", "(a) Population (10³)", 1e3), ("edificacoes", "(b) Buildings (10³)", 1e3),
                                         ("mangue_ha", "(c) Mangrove (10³ ha)", 1e3)]):
        x = np.arange(len(SET))
        for j, (cen, ano, lab, cor) in enumerate(sel):
            d = e[(e.cenario == cen) & (e.ano == ano)].set_index("setor").reindex(SET)
            m_, lo, hi = d[f"{var}_media"] / esc, d[f"{var}_p05"] / esc, d[f"{var}_p95"] / esc
            ax.bar(x + (j - 1) * 0.27, m_, 0.26, color=cor, ec="#555" if cen == "atual" else "none", lw=0.4, label=lab)
            ax.errorbar(x + (j - 1) * 0.27, m_, yerr=[m_ - lo, hi - m_], fmt="none", ecolor="#222", lw=0.7, capsize=1.5)
        ax.set_xticks(x, [ROT_SET[s] for s in SET], fontsize=9)
        ax.set_title(tit, fontsize=10.5, fontweight="bold", loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=9)
        ax.grid(axis="y", lw=0.4, color="#ddd")
        ax.set_axisbelow(True)
    axs[0].legend(frameon=False, fontsize=9, loc="upper left")
    fig.suptitle("Expected exposure at MHWS with 90% Monte Carlo intervals", fontsize=12, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout()
    salvar(fig, "Fig_exposicao_setores")
    # (d) incerteza: erro-padrão e concordância entre DEMs --------------------------------------------------
    fig, axs, H = m22.grade(1, 2, asp, esq=0.55, base=1.8, topo=1.15, wgap=0.35, hmax=9.6)
    conc = []
    for k, ax in enumerate(axs):
        ax.set_facecolor(m22.OCEAN)
        uf.plot(ax=ax, fc=m22.LAND, ec="#c4c4c4", lw=0.4, zorder=1)
        for s in SET:
            p, prof = prob(s, "ssp585_2100")
            t_ = prof["transform"]
            if k == 0:
                v = np.sqrt(np.nan_to_num(p) * (1 - np.nan_to_num(p)) / 500)
                v = np.where(np.nan_to_num(p) > 0.01, v, np.nan)
                im = ax.imshow(v[::4, ::4], extent=(t_.c, t_.c + p.shape[1] * 30, t_.f - p.shape[0] * 30, t_.f),
                               cmap="viridis", vmin=0, vmax=0.023, interpolation="nearest", zorder=3)
            else:
                fc = os.path.join(OUT, "sensibilidade", f"prob_cop30_{s}_ssp585_2100.tif")
                if not os.path.exists(fc):
                    continue
                with rasterio.open(fc) as r:
                    pc = r.read(1)
                a, b = np.nan_to_num(p) >= 0.5, (pc >= 0.5) & (pc >= 0)
                c = np.where(a & b, 1, np.where(a & ~b, 2, np.where(~a & b, 3, 0))).astype("uint8")
                conc.append({"setor": s, "ambos_ha": (c == 1).sum() * 0.09, "so_FABDEM_ha": (c == 2).sum() * 0.09,
                             "so_Copernicus_ha": (c == 3).sum() * 0.09,
                             "Jaccard": (c == 1).sum() / max((c > 0).sum(), 1)})
                f = 6
                h_, w_ = (c.shape[0] // f) * f, (c.shape[1] // f) * f
                cc = c[:h_, :w_].reshape(h_ // f, f, w_ // f, f).max(axis=(1, 3))
                ax.imshow(np.ma.masked_equal(cc, 0), extent=(t_.c, t_.c + w_ * 30, t_.f - h_ * 30, t_.f),
                          cmap=ListedColormap(["#5e3c99", "#e66101", "#4dac26"]), vmin=0.5, vmax=3.5,
                          interpolation="nearest", zorder=3)
        st.boundary.plot(ax=ax, ec="#555", lw=0.45, linestyle="--", zorder=4)
        ax.set_xlim(lim[0], lim[1])
        ax.set_ylim(lim[2], lim[3])
        m22.graticule(ax, 1.0, esquerda=(k == 0), fs=10.5, bold=True)
        ax.set_title(["(a) Monte Carlo standard error", "(b) DEM agreement (p ≥ 0.5)"][k], fontsize=12, fontweight="bold",
                     loc="left")
    m22.cabecalho(fig, H, "Uncertainty diagnostics — SSP5-8.5, 2100", "Standard error of p̂ (N = 500) and FABDEM × Copernicus agreement")
    cax = fig.add_axes([0.42 / m22.W_PAGE, 1.15 / H, 2.6 / m22.W_PAGE, 0.14 / H])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
    cb.set_label("se(p̂)", fontsize=10.5)
    cb.ax.tick_params(labelsize=9.5)
    for i, (cor, lab) in enumerate(zip(["#5e3c99", "#e66101", "#4dac26"], ["Both DEMs", "FABDEM only", "Copernicus only"])):
        fig.add_artist(m22.Rectangle((3.75 / m22.W_PAGE, (1.35 - 0.3 * i - 0.08) / H), 0.3 / m22.W_PAGE, 0.16 / H,
                                     fc=cor, ec="#555", lw=0.5))
        fig.text(4.15 / m22.W_PAGE, (1.35 - 0.3 * i) / H, lab, fontsize=11, va="center")
    salvar(fig, "Fig_incerteza")
    if conc:
        pd.DataFrame(conc).round(3).to_csv(os.path.join(TB, "concordancia_DEMs.csv"), index=False, encoding="utf-8-sig")
    _v2.log("produtos complementares: ok")
