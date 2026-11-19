"""23 — Validação independente do erro do DEM e estimativa do comprimento de correlação ℓ (métodos §4.4 e §4.8).

1) Retenção espacial por passagem: 30 % das passagens ICESat-2 (agrupadas por data) ficam fora da calibração.
   Calibra viés b_c e desvio s_c por classe MapBiomas nos 70 % e avalia, nos 30 %, o erro bruto (z − h) e o
   corrigido (z − b_c − h): viés, NMAD, RMSE, LE90.
2) Variograma dos resíduos corrigidos ao longo do traço (pares da mesma passagem, até 3 km) e ajuste do modelo
   gaussiano γ(h) = c0 + c[1 − exp(−h²/(4ℓ²))], coerente com o campo gerado por filtro gaussiano de escala ℓ (Eq. 14).
Saídas: <resultados_O2_Bahia>/validacao/{dem_retencao_por_classe.csv, variograma.csv, resumo_dem.json, Fig_variograma.*}
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from rasterio.transform import rowcol
from scipy.optimize import curve_fit

import _v2

sys.path.insert(0, _v2.REPO)
from coastshift import io as csio  # noqa: E402

OUT = os.path.join(os.environ.get("COASTSHIFT_RESULTADOS", os.path.join(os.path.dirname(_v2.REPO), "resultados_O2_Bahia")),
                   "validacao")


def est(e):
    e = np.asarray(e)
    m = np.median(e)
    return {"n": int(e.size), "vies": float(e.mean()), "NMAD": float(1.4826 * np.median(np.abs(e - m))),
            "RMSE": float(np.sqrt((e ** 2).mean())), "LE90": float(np.percentile(np.abs(e), 90))}


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(1)
    pts = []
    for setor in _v2.SETORES:
        pk = csio.Package(os.path.join(_v2.BASE, "pacotes", setor))
        d = pd.read_csv(os.path.join(pk.folder, "validacao_pontos_dem.csv"))
        r, c = rowcol(pk.profile["transform"], d.x.values, d.y.values)
        r, c = np.asarray(r), np.asarray(c)
        ok = (r >= 0) & (r < pk.dem.shape[0]) & (c >= 0) & (c < pk.dem.shape[1])
        d, r, c = d[ok].copy(), r[ok], c[ok]
        d["z"] = pk.dem[r, c]
        d["classe"] = pk.layers["landcover"][r, c]
        d["mar"] = pk.sea[r, c]
        d["setor"] = setor
        d = d[np.isfinite(d.z) & ~d.mar & (d.classe != 33) & np.isfinite(d.classe)]
        d["passagem"] = setor + "_" + d.data.str[:10]
        pts.append(d)
    d = pd.concat(pts, ignore_index=True)
    d["classe"] = d.classe.astype(int)
    d["e"] = d.z - d.h_ref
    passagens = d.passagem.unique()
    teste = set(rng.choice(passagens, int(0.3 * len(passagens)), replace=False))
    d["teste"] = d.passagem.isin(teste)
    cal = d[~d.teste]
    b = cal.groupby("classe").e.agg(["mean", "count"])
    b_geral = cal.e.mean()
    d["b"] = d.classe.map(lambda k: b.loc[k, "mean"] if k in b.index and b.loc[k, "count"] >= 30 else b_geral)
    d["e_corr"] = d.e - d.b
    te = d[d.teste]
    linhas = [{"classe": "todas", **{f"bruto_{k}": v for k, v in est(te.e).items()},
               **{f"corrigido_{k}": v for k, v in est(te.e_corr).items() if k != "n"}}]
    for k, g in te.groupby("classe"):
        if len(g) >= 30:
            linhas.append({"classe": int(k), **{f"bruto_{a}": v for a, v in est(g.e).items()},
                           **{f"corrigido_{a}": v for a, v in est(g.e_corr).items() if a != "n"}})
    tab = pd.DataFrame(linhas).sort_values("bruto_n", ascending=False)
    tab.round(3).to_csv(os.path.join(OUT, "dem_retencao_por_classe.csv"), index=False, encoding="utf-8-sig")
    # variograma ao longo do traço (resíduos corrigidos, conjunto de calibração)
    cal = d[~d.teste]
    lags = np.arange(0, 3001, 60)
    soma, cont = np.zeros(len(lags) - 1), np.zeros(len(lags) - 1)
    amostra = rng.choice(cal.passagem.unique(), min(400, cal.passagem.nunique()), replace=False)
    for pid in amostra:
        g = cal[cal.passagem == pid].sort_values("y")
        if len(g) < 20:
            continue
        x, y, v = g.x.values, g.y.values, g.e_corr.values
        for k in range(1, min(160, len(g))):
            h = np.hypot(x[k:] - x[:-k], y[k:] - y[:-k])
            sv = 0.5 * (v[k:] - v[:-k]) ** 2
            i = np.digitize(h, lags) - 1
            ok = (i >= 0) & (i < len(soma))
            np.add.at(soma, i[ok], sv[ok])
            np.add.at(cont, i[ok], 1)
    hc = 0.5 * (lags[1:] + lags[:-1])
    gam = np.where(cont > 50, soma / np.maximum(cont, 1), np.nan)
    ok = np.isfinite(gam)
    f = lambda h, c0, c, ell: c0 + c * (1 - np.exp(-h ** 2 / (4 * ell ** 2)))  # noqa: E731
    (c0, c, ell), _ = curve_fit(f, hc[ok], gam[ok], p0=[gam[ok][0] * 0.5, np.nanmax(gam) * 0.5, 300],
                                bounds=([0, 0, 30], [np.inf, np.inf, 3000]))
    pd.DataFrame({"lag_m": hc, "semivariancia_m2": gam, "pares": cont, "modelo": f(hc, c0, c, ell)}).to_csv(
        os.path.join(OUT, "variograma.csv"), index=False)
    resumo = {"pontos": int(len(d)), "passagens": int(len(passagens)), "passagens_teste": len(teste),
              "teste_bruto": est(te.e), "teste_corrigido": est(te.e_corr),
              "variograma": {"pepita_m2": round(float(c0), 3), "patamar_parcial_m2": round(float(c), 3),
                             "ell_m": round(float(ell), 1), "fracao_correlacionada": round(float(c / (c0 + c)), 3)}}
    json.dump(resumo, open(os.path.join(OUT, "resumo_dem.json"), "w", encoding="utf-8"), indent=1)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4.8, 3.4))
    ax.plot(hc, gam, "o", ms=3.5, color="#3b6f9e", label="Empirical (along-track pairs)")
    ax.plot(hc, f(hc, c0, c, ell), "-", color="#bd0026", lw=1.6, label=f"Gaussian model, ℓ = {ell:.0f} m")
    ax.set_xlabel("Lag (m)", fontsize=10)
    ax.set_ylabel("Semivariance (m²)", fontsize=10)
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Semivariogram of class-corrected FABDEM residuals", fontsize=10, loc="left", fontweight="bold")
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"Fig_variograma_DEM.{ext}"), dpi=600, bbox_inches="tight")
    _v2.log(f"DEM: teste bruto viés {resumo['teste_bruto']['vies']:.2f} m → corrigido {resumo['teste_corrigido']['vies']:.2f} m; ℓ = {ell:.0f} m")
