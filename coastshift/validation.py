"""Métricas de validação (Eqs. 25–31 do documento de métodos)."""
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol


def dem_vs_points(dem, profile, landcover, csv_path, xcol="x", ycol="y", hcol="h_ref"):
    """Compara o DEM com pontos de referência (ICESat-2, GNSS, marcos). CSV no CRS do DEM.
    Retorna estatísticas gerais e por classe, e o dicionário dem_error para o params.json."""
    df = pd.read_csv(csv_path)
    r, c = rowcol(profile["transform"], df[xcol].values, df[ycol].values)
    r, c = np.asarray(r), np.asarray(c)
    ok = (r >= 0) & (r < dem.shape[0]) & (c >= 0) & (c < dem.shape[1])
    df = df[ok].copy()
    df["dem"] = dem[r[ok], c[ok]]
    df["classe"] = landcover[r[ok], c[ok]].astype(int)
    df = df[np.isfinite(df["dem"]) & np.isfinite(df[hcol])]
    df["erro"] = df["dem"] - df[hcol]

    def stats(e):
        e = np.asarray(e)
        med = np.median(e)
        return {"n": int(e.size), "vies": round(float(e.mean()), 3), "MAE": round(float(np.abs(e).mean()), 3),
                "RMSE": round(float(np.sqrt((e ** 2).mean())), 3),
                "NMAD": round(float(1.4826 * np.median(np.abs(e - med))), 3),
                "LE90": round(float(np.percentile(np.abs(e), 90)), 3), "dp": round(float(e.std(ddof=1)) if e.size > 1 else 0.0, 3)}

    rows = [{"classe": "todas", **stats(df["erro"])}]
    dem_error = {"default": {"bias": rows[0]["vies"], "sd": rows[0]["dp"]}, "by_class": {}}
    for cls, g in df.groupby("classe"):
        s = stats(g["erro"])
        rows.append({"classe": int(cls), **s})
        if s["n"] >= 30:
            dem_error["by_class"][str(int(cls))] = {"bias": s["vies"], "sd": s["dp"]}
    return pd.DataFrame(rows), dem_error


def flood_skill(pred, obs, mask=None):
    """Tabela de contingência: CSI, taxa de acerto, falso alarme, viés e F1."""
    p, o = np.nan_to_num(pred) > 0.5, np.nan_to_num(obs) > 0.5
    if mask is not None:
        p, o = p[mask], o[mask]
    tp, fp, fn = int((p & o).sum()), int((p & ~o).sum()), int((~p & o).sum())
    return {"TP": tp, "FP": fp, "FN": fn,
            "CSI": round(tp / max(tp + fp + fn, 1), 3), "HR": round(tp / max(tp + fn, 1), 3),
            "FAR": round(fp / max(tp + fp, 1), 3), "vies_area": round((tp + fp) / max(tp + fn, 1), 3),
            "F1": round(2 * tp / max(2 * tp + fp + fn, 1), 3)}


def brier(prob, obs, mask=None, bins=10):
    p, o = np.nan_to_num(prob).ravel(), (np.nan_to_num(obs) > 0.5).ravel().astype(float)
    if mask is not None:
        p, o = p[mask.ravel()], o[mask.ravel()]
    bs = float(np.mean((p - o) ** 2))
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    rel = [{"faixa": f"{edges[i]:.1f}-{edges[i + 1]:.1f}", "n": int((idx == i).sum()),
            "prob_media": round(float(p[idx == i].mean()), 3) if (idx == i).any() else None,
            "freq_obs": round(float(o[idx == i].mean()), 3) if (idx == i).any() else None} for i in range(bins)]
    return round(bs, 4), pd.DataFrame(rel)


def series_skill(csv_path, obs="obs", mod="mod"):
    """Validação de séries (maré, nível): viés, RMSE, correlação, Nash-Sutcliffe."""
    df = pd.read_csv(csv_path).dropna(subset=[obs, mod])
    o, m = df[obs].values, df[mod].values
    return {"n": len(o), "vies": round(float((m - o).mean()), 4), "RMSE": round(float(np.sqrt(((m - o) ** 2).mean())), 4),
            "r": round(float(np.corrcoef(o, m)[0, 1]), 4),
            "NSE": round(float(1 - ((m - o) ** 2).sum() / ((o - o.mean()) ** 2).sum()), 4)}


def return_level_coverage(annual_max_test, levels_by_T):
    """Retroteste: excedências observadas vs esperadas para cada TR no período de teste."""
    x = np.asarray(annual_max_test)
    return [{"TR_anos": T, "nivel_m": round(L, 3), "excedencias_obs": int((x > L).sum()),
             "esperadas": round(len(x) / T, 2)} for T, L in levels_by_T.items()]


def read_mask_aligned(path, profile):
    with rasterio.open(path) as src:
        if src.shape != (profile["height"], profile["width"]):
            raise ValueError("Máscara observada não está na mesma grade do DEM (use o script 10 para alinhar).")
        return src.read(1).astype("float32")
