"""25d — Aliasing de maré: nível do mar em Salvador nos instantes de aquisição do Sentinel-1 e do Sentinel-2 × MHWS.

Busca no STAC do Planetary Computer todas as aquisições sobre a zona costeira (Sentinel-2 L2A 2019–2025; Sentinel-1
RTC 2017–2025), interpola o nível horário de Salvador (UHSLC 708, rel. NMM 2004–2024) em cada instante e compara com a
distribuição de todas as horas e com a hora UTC das preamares acima da MHWS. Gera a Fig. 8 em quatro painéis:
(a) distribuição do nível; (b) hora UTC das preamares > MHWS × horários de passagem; (c) métricas do Sentinel-1 por
setor; (d) confiabilidade. Saídas: validacao/aliasing_mare_aquisicoes.csv, validacao/aliasing_mare_resumo.json,
graficos/Fig_validacao_mare_aliasing.{png,pdf}.
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
GR, VAL = os.path.join(RES, "graficos"), os.path.join(RES, "validacao")
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
T0, T1 = "2017-01-01", "2025-12-31"


def aquisicoes(cat, colecao, datas, bbox):
    its = cat.search(collections=[colecao], bbox=list(bbox), datetime=datas).items()
    rows = []
    for i in its:
        pr = i.properties
        rows.append({"id": i.id, "t": pd.Timestamp(i.datetime).tz_convert(None),
                     "orbita": pr.get("sat:relative_orbit", pr.get("sat:relative_orbit_number")),
                     "nuvens": pr.get("eo:cloud_cover", np.nan)})
    d = pd.DataFrame(rows)
    d["t_min"] = d.t.dt.round("min")
    return d.drop_duplicates("t_min").reset_index(drop=True)      # uma linha por aquisição (vários tiles = mesma passagem)


if __name__ == "__main__":
    import planetary_computer
    import pystac_client
    os.makedirs(GR, exist_ok=True)
    sal = json.load(open(_v2.p("mares", "mares_salvador.json"), encoding="utf-8"))
    mhws, mhhw = sal["mhws_m"], sal["mhhw_m"]
    sv = (_v2.serie_uhslc(708, ("b",), fast=True) - sal["nmm_zero_estacao_m"]).dropna()
    bbox = _v2.aoi_bounds_ll()
    cat = pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)
    s2 = aquisicoes(cat, "sentinel-2-l2a", "2019-01-01/2025-12-31", bbox); s2["sensor"] = "Sentinel-2"
    s1 = aquisicoes(cat, "sentinel-1-rtc", f"{T0}/{T1}", bbox); s1["sensor"] = "Sentinel-1"
    aq = pd.concat([s2, s1], ignore_index=True)
    ts = sv.index.values.astype("datetime64[s]").astype("int64")
    aq["nivel_salvador_m"] = np.interp(aq.t.values.astype("datetime64[s]").astype("int64"), ts, sv.values,
                                       left=np.nan, right=np.nan)
    aq["hora_utc"] = aq.t.dt.hour + aq.t.dt.minute / 60
    aq = aq.dropna(subset=["nivel_salvador_m"])
    aq.drop(columns="t_min").to_csv(os.path.join(VAL, "aliasing_mare_aquisicoes.csv"), index=False)

    # todas as horas e preamares (máximos locais em janela de ±3 h) no mesmo período
    h = sv[T0:T1]
    pre = h[(h == h.rolling(7, center=True).max()) & (h > 0)]
    pre_alta = pre[pre > mhws]
    res = {"periodo_horas": [T0, T1], "mhws_m": mhws, "mhhw_m": mhhw, "n_horas": int(h.size),
           "frac_horas_acima_mhws": round(float((h > mhws).mean()), 4), "n_preamares": int(pre.size),
           "n_preamares_acima_mhws": int(pre_alta.size),
           "preamares_acima_mhws_por_janela_utc": {f"{x}-{y}h": int(((pre_alta.index.hour >= x) & (pre_alta.index.hour < y)).sum())
                                                  for x, y in ((4, 11), (11, 16), (16, 24), (0, 4))},
           "hora_utc_preamares_acima_mhws_p10_p50_p90": [round(float(x), 2) for x in np.percentile(pre_alta.index.hour + 0.0, [10, 50, 90])]}
    for s, d in aq.groupby("sensor"):
        res[s] = {"n_aquisicoes": int(len(d)), "nivel_max_m": round(float(d.nivel_salvador_m.max()), 3),
                  "nivel_p50_m": round(float(d.nivel_salvador_m.median()), 3),
                  "frac_acima_mhws": round(float((d.nivel_salvador_m > mhws).mean()), 4),
                  "n_acima_mhws": int((d.nivel_salvador_m > mhws).sum()),
                  "hora_utc_p05_p50_p95": [round(float(x), 2) for x in np.percentile(d.hora_utc, [5, 50, 95])]}
        if s == "Sentinel-2":
            dd = d[d.nuvens < 10]
            res[s]["nuvens_lt10"] = {"n_aquisicoes": int(len(dd)), "nivel_max_m": round(float(dd.nivel_salvador_m.max()), 3)}
    json.dump(res, open(os.path.join(VAL, "aliasing_mare_resumo.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    _v2.log(json.dumps(res, ensure_ascii=False))

    # ---------------------------------------------------------------- figura (4 painéis)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "pdf.fonttype": 42})
    fig, ax = plt.subplots(2, 2, figsize=(7.2, 7.4))
    a, b, c, d = ax.ravel()
    bins = np.arange(-1.6, 1.95, 0.1)
    a.hist(h.values, bins=bins, density=True, color="#d9d9d9", label=f"All hours ({res['frac_horas_acima_mhws'] * 100:.1f} % > MHWS)")
    for s, cor in (("Sentinel-2", "#2c7bb6"), ("Sentinel-1", "#e66101")):
        v = aq[aq.sensor == s].nivel_salvador_m
        a.hist(v, bins=bins, density=True, histtype="step", lw=1.6, color=cor,
               label=f"{s} (n = {len(v)}; {res[s]['frac_acima_mhws'] * 100:.1f} % > MHWS)")
    for x, lab in ((0, "MSL"), (mhhw, "MHHW"), (mhws, "MHWS")):
        a.axvline(x, color="k", lw=0.7, ls=":" if lab != "MHWS" else "-")
        a.text(x, a.get_ylim()[1] * 0.98, lab, rotation=90, va="top", ha="right", fontsize=7)
    a.set_xlabel("Sea level at Salvador at acquisition time (m above MSL)")
    a.set_ylabel("Density")
    a.legend(frameon=False, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
    a.set_title("(a) Tide level sampled by each sensor", fontsize=9.5, fontweight="bold", loc="left")

    b.hist(pre_alta.index.hour, bins=np.arange(0, 25, 1), color="#bdbdbd", label=f"High waters > MHWS (n = {pre_alta.size})")
    for s, cor in (("Sentinel-2", "#2c7bb6"), ("Sentinel-1", "#e66101")):
        lo, mid, hi = res[s]["hora_utc_p05_p50_p95"]
        b.axvspan(lo, max(hi, lo + 0.15), color=cor, alpha=0.35, label=f"{s} overpass ({mid:.1f} h UTC)")
    b.set_xlim(0, 24); b.set_xticks(range(0, 25, 3))
    b.set_xlabel("Hour of day (UTC)"); b.set_ylabel("Count")
    b.legend(frameon=False, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
    b.set_title("(b) Timing of high waters above MHWS", fontsize=9.5, fontweight="bold", loc="left")

    tipo = "multipares" if os.path.exists(os.path.join(VAL, "s1_multipares_metricas.csv")) else "intermare"  # 25d (vários pares)
    m = pd.read_csv(os.path.join(VAL, f"s1_{tipo}_metricas.csv"), encoding="utf-8-sig")
    cf = pd.read_csv(os.path.join(VAL, f"s1_{tipo}_confiabilidade.csv"), encoding="utf-8-sig")
    mm = m[m.setor != "TOTAL"]
    x = np.arange(len(mm) + 1)
    nomes = [s.split("_")[0] for s in mm.setor] + ["All"]
    for k, (col, lab, cor) in enumerate([("CSI", "CSI", "#2c7bb6"), ("sem_mangue_CSI", "CSI excl. mangrove", "#abd9e9"),
                                        ("HR", "Hit rate", "#1a9641"), ("FAR", "False alarm ratio", "#d7191c")]):
        c.bar(x + (k - 1.5) * 0.2, m[col].values, 0.19, color=cor, label=lab)
    c.set_xticks(x, nomes); c.set_ylim(0, 1)
    c.legend(frameon=False, fontsize=6.5, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    c.set_title("(c) Sentinel-1 skill (p ≥ 0.5)", fontsize=9.5, fontweight="bold", loc="left")
    g = cf.groupby("faixa_p").apply(lambda z: pd.Series({"p": np.average(z.p_media, weights=z.n),
                                                        "o": np.average(z.freq_obs, weights=z.n), "n": z.n.sum()}))
    d.plot([0, 1], [0, 1], "--", color="#888", lw=0.8)
    d.scatter(g.p, g.o, s=10 + 50 * g.n / g.n.max(), color="#2c7bb6", zorder=3)
    d.plot(g.p, g.o, color="#2c7bb6", lw=1)
    d.set_xlim(0, 1); d.set_ylim(0, 1)
    d.set_xlabel("Forecast probability"); d.set_ylabel("Observed frequency")
    tot = m[m.setor == "TOTAL"].iloc[0]
    d.set_title(f"(d) Reliability (Brier = {tot.Brier:.3f})", fontsize=9.5, fontweight="bold", loc="left")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(GR, f"Fig_validacao_mare_aliasing.{ext}"), dpi=600 if ext == "png" else None,
                    bbox_inches="tight")
    print(json.dumps(res, ensure_ascii=False, indent=1))
