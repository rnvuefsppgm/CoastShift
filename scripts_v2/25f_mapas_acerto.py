"""25f — Mapas de acerto, falso alarme e omissão da inundação pela maré (Sentinel-1, vários pares por setor).

Refaz, com as mesmas funções e a mesma semente do script 25d (etapa `avaliar`), a previsão p_maré = p(alta) − p(baixa)
de cada par e a água de maré observada; classifica cada célula por par (previsão = p_maré ≥ 0,5) e compõe os pares:
  1 = acerto (VP em algum par), 3 = omissão (FN em algum par e nenhum VP), 2 = falso alarme (só FP); 0 = sem evento.
Verificação: a soma de VP, FP e FN por par tem de igualar `validacao/s1_multipares_metricas.csv` (mesma rodada).
Saídas em <COASTSHIFT_RESULTADOS>/validacao/: s1_acerto_<setor>.tif, s1_acerto_contagens.csv;
s1_acerto_mangue.csv; graficos/Fig_validacao_s1_acerto.{png,pdf} (6 painéis, contorno do mangue; exibição agregada,
contagens na resolução nativa).
Uso: python 25f_mapas_acerto.py [--proc 3] [--so-figura]
"""
import argparse
import importlib.util
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import rasterio

import _v2


def _mod(nome, arq):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(os.path.dirname(os.path.abspath(__file__)), arq))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


v25d = _mod("v25d", "25d_validacao_multipares.py")
RES = v25d.v25.RES
VAL, GR = os.path.join(RES, "validacao"), os.path.join(RES, "graficos")
CORES = {1: "#1a9641", 2: "#d7191c", 3: "#2c7bb6"}
NOMES = {1: "Hit", 2: "False alarm", 3: "Miss"}


def setor_mapa(setor):
    pares = pd.read_csv(os.path.join(v25d.VALSAT, "pares.csv"))
    pares = pares[(pares.setor == setor) & (pares.sensor == "s1")]
    pk = v25d.csio.Package(os.path.join(_v2.BASE, "pacotes", setor))
    niveis = sorted({(r.nivel_alta_m, int(r.dia_alta[:4])) for r in pares.itertuples()}
                    | {(r.nivel_baixa_m, int(r.dia_baixa[:4])) for r in pares.itertuples()})
    P = v25d.p_niveis(pk, niveis)                                   # mesma semente e N do 25d
    terra = np.isfinite(pk.dem) & ~pk.sea
    with rasterio.open(_v2.p("agua", f"gsw_ocorrencia_{setor}.tif")) as g:
        perm = g.read(1) >= 50
    vp, fn, fp = (np.zeros(pk.dem.shape, bool) for _ in range(3))
    linhas = []
    for r in pares.itertuples():
        w_a, ok_a = v25d._ler("s1", setor, r.dia_alta)
        w_b, ok_b = v25d._ler("s1", setor, r.dia_baixa)
        msk = terra & ~perm & ok_a & ok_b
        obs = w_a & ~w_b & msk
        p = np.clip(P[(r.nivel_alta_m, int(r.dia_alta[:4]))] - P[(r.nivel_baixa_m, int(r.dia_baixa[:4]))], 0, 1)
        pr = (p >= 0.5) & msk
        tp_, fp_, fn_ = pr & obs, pr & ~obs, ~pr & obs
        vp |= tp_; fp |= fp_; fn |= fn_
        linhas.append({"setor": setor, "par": r.par, "TP": int(tp_.sum()), "FP": int(fp_.sum()), "FN": int(fn_.sum())})
    cat = np.zeros(pk.dem.shape, "uint8")
    cat[fp] = 2
    cat[fn] = 3
    cat[vp] = 1
    prof = dict(pk.profile, dtype="uint8", count=1, nodata=0, compress="deflate")
    with rasterio.open(os.path.join(VAL, f"s1_acerto_{setor}.tif"), "w", **prof) as d:
        d.write(cat, 1)
    _v2.log(f"mapa de acerto {setor}: {len(pares)} pares")
    return linhas


def agrega_exib(cat, k):
    """Agrega em blocos k×k para exibição, por presença com prioridade acerto > omissão > falso alarme
    (os acertos, raros, ficam visíveis; as contagens da figura são as da resolução nativa)."""
    h, w = (cat.shape[0] // k) * k, (cat.shape[1] // k) * k
    b = cat[:h, :w].reshape(h // k, k, w // k, k)
    out = np.zeros((h // k, w // k), "uint8")
    for c in (2, 3, 1):
        out[(b == c).any(axis=(1, 3))] = c
    return out


def figura(cont):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    met = pd.read_csv(os.path.join(VAL, "s1_multipares_metricas.csv"), encoding="utf-8-sig")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})
    fig, axs = plt.subplots(2, 3, figsize=(7.2, 7.6))
    cmap = ListedColormap(["#ffffff00", CORES[1], CORES[2], CORES[3]])
    mang_fp = []
    for ax, setor in zip(axs.flat, _v2.SETORES):
        f = os.path.join(VAL, f"s1_acerto_{setor}.tif")
        with rasterio.open(f) as r:
            cat = r.read(1)
        pk = v25d.csio.Package(os.path.join(_v2.BASE, "pacotes", setor))
        k = max(1, int(np.ceil(max(cat.shape) / 1200)))
        terra = agrega_exib((np.isfinite(pk.dem) & ~pk.sea).astype("uint8"), k) > 0
        ax.imshow(np.where(terra, 1, np.nan), cmap=ListedColormap(["#e7e7e3"]), interpolation="nearest")
        ax.imshow(np.ma.masked_equal(agrega_exib(cat, k), 0), cmap=cmap, vmin=0, vmax=3, interpolation="nearest")
        mang = pk.layers["landcover"] == 5                            # mangue (MapBiomas 5): contorno
        ax.contour(agrega_exib(mang.astype("uint8"), k) > 0, levels=[0.5], colors="#333333", linewidths=0.25)
        n_fp = int((cat == 2).sum())
        mang_fp.append({"setor": setor, "FP_celulas": n_fp, "FP_no_mangue_%": round(100 * int(((cat == 2) & mang).sum()) / max(n_fp, 1), 1),
                        "acerto_no_mangue_%": round(100 * int(((cat == 1) & mang).sum()) / max(int((cat == 1).sum()), 1), 1)})
        ax.set_facecolor("#e8f1f7")
        ax.set_xticks([]); ax.set_yticks([])
        m = met[met.setor == setor].iloc[0]
        ax.set_title(f"{setor.split('_')[0]}\nCSI {m.CSI:.3f} · HR {m.HR:.2f} · FAR {m.FAR:.2f}", fontsize=7,
                     fontweight="bold", loc="left")
        c = cont[cont.setor == setor][["TP", "FP", "FN"]].sum()
        ax.text(0.02, 0.02, f"VP {c.TP:,}\nFP {c.FP:,}\nFN {c.FN:,}", transform=ax.transAxes, fontsize=6.5, va="bottom",
                bbox=dict(fc="w", ec="#999", lw=0.4, alpha=0.85))
    pd.DataFrame(mang_fp).to_csv(os.path.join(VAL, "s1_acerto_mangue.csv"), index=False, encoding="utf-8-sig")
    from matplotlib.lines import Line2D
    fig.legend(handles=[Patch(color=CORES[i], label=NOMES[i]) for i in (1, 2, 3)] + [Line2D([], [], color="#333333", lw=0.8, label="Mangrove (MapBiomas)")], loc="lower center", ncol=4,
               frameon=False, fontsize=8)
    fig.suptitle("Sentinel-1 tidal-inundation check: hits, false alarms and misses (3 pairs per sector; p ≥ 0.5)",
                 fontsize=9, fontweight="bold")
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    os.makedirs(GR, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(GR, f"Fig_validacao_s1_acerto.{ext}"), dpi=600 if ext == "png" else None)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--proc", type=int, default=3)
    ap.add_argument("--so-figura", action="store_true")
    a = ap.parse_args()
    fc = os.path.join(VAL, "s1_acerto_contagens.csv")
    if not a.so_figura:
        with ProcessPoolExecutor(a.proc) as ex:
            res = list(ex.map(setor_mapa, list(_v2.SETORES)))
        cont = pd.DataFrame([x for r in res for x in r])
        cont.to_csv(fc, index=False, encoding="utf-8-sig")
        pp = pd.read_csv(os.path.join(VAL, "s1_multipares_por_par.csv"), encoding="utf-8-sig")
        chk = cont.merge(pp[["setor", "par", "TP", "FP", "FN"]], on=["setor", "par"], suffixes=("", "_25d"))
        dif = int(sum((chk[c] - chk[c + "_25d"]).abs().sum() for c in ("TP", "FP", "FN")))
        _v2.log(f"verificação contra o 25d: {len(chk)} pares, diferença total {dif} células")
    figura(pd.read_csv(fc, encoding="utf-8-sig"))
    _v2.log("Fig_validacao_s1_acerto gravada")
