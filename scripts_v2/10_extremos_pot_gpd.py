"""10 — Níveis extremos (POT-GPD) do marégrafo de Salvador (UHSLC 708), com bootstrap e retroteste.
Passos (métodos §5.3): remover a média anual → limiar no percentil 99 → declustering de 72 h → GPD (loc = 0)
→ bootstrap (200) → níveis de retorno → retroteste (ajuste na 1ª metade, teste na 2ª).
Nível total relativo ao NMM. A transferência para os demais setores é feita na montagem dos pacotes (script 20).
Saída: <BASE>/mares/extremos_salvador.json
"""
import numpy as np

import _v2

T = [1, 2, 5, 10, 25, 50, 100]


def picos(x, thr, gap_h=72):
    e = x[x > thr]
    out, last_t, best = [], None, None
    for t, v in e.items():
        if last_t is not None and (t - last_t).total_seconds() / 3600 > gap_h:
            out.append(best)
            best = None
        best = v if best is None or v > best else best
        last_t = t
    if best is not None:
        out.append(best)
    return np.array(out)


def nivel(thr, sc, xi, rate, tr):
    m = rate * np.asarray(tr, float)
    return thr + (sc / xi * (m ** xi - 1) if abs(xi) > 1e-6 else sc * np.log(m))


def ajuste(x):
    anos = x.notna().sum() / 8766.0
    thr = float(np.nanpercentile(x.dropna(), 99))
    pk = picos(x.dropna(), thr)
    xi, sc = _v2.ajustar_gpd(pk - thr)
    return thr, sc, xi, len(pk) / anos, pk, anos


if __name__ == "__main__":
    s = _v2.serie_uhslc(708, ("b",), fast=True)["2004":]
    x = s - s.groupby(s.index.year).transform("mean")
    thr, sc, xi, rate, pk, anos = ajuste(x)
    rng = np.random.default_rng(0)
    bs = np.array([_v2.ajustar_gpd(rng.choice(pk - thr, len(pk), replace=True)) for _ in range(200)])
    rl = nivel(thr, sc, xi, rate, T)
    rl_bs = np.array([nivel(thr, b[1], b[0], rate, T) for b in bs])
    meio = x.index[0] + (x.index[-1] - x.index[0]) / 2
    t1, s1, x1, r1, _, _ = ajuste(x[:meio])
    am2 = x[meio:].groupby(x[meio:].index.year).max().dropna()
    rl1 = nivel(t1, s1, x1, r1, [2])
    out = {"estacao": "Salvador UHSLC 708", "anos": round(float(anos), 1), "threshold": round(thr, 3),
           "scale": round(sc, 4), "shape": round(xi, 4), "rate": round(float(rate), 2),
           "scale_se": round(float(bs[:, 1].std()), 4), "shape_se": round(float(bs[:, 0].std()), 4),
           "n_picos": int(len(pk)),
           "niveis_retorno_m": {str(t): {"estimativa": round(float(v), 3),
                                         "ic90": [round(float(np.percentile(rl_bs[:, i], 5)), 3),
                                                  round(float(np.percentile(rl_bs[:, i], 95)), 3)]}
                                for i, (t, v) in enumerate(zip(T, rl))},
           "retroteste": {"max_anual_2a_metade": [round(float(v), 3) for v in am2.values],
                          "TR2_ajuste_1a_metade": round(float(rl1[0]), 3),
                          "frac_anos_acima_TR2": round(float((am2.values > rl1[0]).mean()), 2),
                          "esperado": 0.5},
           "reference": "nível total rel. NMM anual (sem tendência)"}
    _v2.salvar_json(out, "mares", "extremos_salvador.json")
    _v2.log(f"GPD: limiar {thr:.2f} m, escala {sc:.3f}, forma {xi:.3f}, {rate:.1f} picos/ano; "
            f"TR100 = {rl[-1]:.2f} m; retroteste {out['retroteste']['frac_anos_acima_TR2']:.2f} (esperado 0,5)")
