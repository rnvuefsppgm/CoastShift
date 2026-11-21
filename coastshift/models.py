"""Os cinco modelos da revisão (O1–O5). Cada função recebe um Package e um dicionário
de opções e devolve Result(layers, table, meta). Equações: docs/01_Metodos_Opcao2_Bahia.md."""
from dataclasses import dataclass, field

import os

import numpy as np
from scipy import ndimage

from . import core

MODELS = {
    "O1": "O1 – Bathtub conectado (estático)",
    "O2": "O2 – Estático probabilístico (Monte Carlo)",
    "O3": "O3 – Hidrodinâmica reduzida 2D (inercial)",
    "O4": "O4 – Linha de costa + habitats + inundação",
    "O5": "O5 – Integrado probabilístico (emulador + EAD)",
}


@dataclass
class Result:
    layers: dict = field(default_factory=dict)
    table: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def _noop(frac, msg=""):
    pass


def _exposure(pkg, weight):
    """Totais esperados sob um mapa de pesos (máscara 0/1 ou probabilidade)."""
    a = pkg.cell ** 2 / 1e4
    lc = pkg.layers["landcover"]
    mang = np.isin(lc, pkg.params.get("habitat", {}).get("mangrove_classes", [5]))
    w = np.nan_to_num(weight)
    return {
        "area_ha": float(w.sum() * a),
        "populacao": float((w * np.nan_to_num(pkg.layers["pop"])).sum()),
        "edificacoes": float((w * np.nan_to_num(pkg.layers["buildings"])).sum()),
        "mangue_ha": float((w * mang).sum() * a),
    }


def _dem_corrected(pkg):
    bias, _ = core.dem_error_maps(pkg.layers["landcover"], pkg.params.get("dem_error", {}))
    return pkg.dem - bias


# ======================================================================= O1
def run_o1(pkg, opt, progress=_noop):
    p = pkg.params
    z = _dem_corrected(pkg) if opt.get("correct_bias", True) else pkg.dem
    res = Result(meta={"modelo": "O1", **opt})
    for ssp in opt["ssps"]:
        for yr in opt["years"]:
            d = core.delta_rsl(p, ssp, yr, opt.get("quantile", 0.5))
            base = core.sea_level_event(p, opt.get("ref", "MHWS"), opt.get("tr", 0),
                                        with_setup=opt.get("setup", False), amp=opt.get("amp", 1.0))
            eta = base + d
            wet = core.connected_flood(z, eta, pkg.sea, opt.get("conn", 8))
            depth = np.where(wet, eta - z, np.nan)
            key = f"{ssp}_{yr}"
            res.layers[f"inundado_{key}"] = wet.astype("float32")
            res.layers[f"profundidade_{key}"] = depth.astype("float32")
            if opt.get("compare_unconnected", True):
                unc = (z <= eta) & ~pkg.sea
                res.layers[f"nao_conectado_extra_{key}"] = (unc & ~wet).astype("float32")
            res.table.append({"cenario": ssp, "ano": yr, "dRSL_m": round(float(d), 3),
                              "cota_agua_m": round(float(eta), 3), **_exposure(pkg, wet)})
            progress(len(res.table) / (len(opt["ssps"]) * len(opt["years"])), key)
    return res


# ======================================================================= O2
def o2_realizacoes(pkg, opt, n, seed, progress=_noop):
    """Bloco de n realizações do O2 (Eqs. 4–14c). Em cada realização sorteiam-se u_k (AR6, comonotônico), o evento
    de referência e o campo de erro do DEM uma única vez; o bathtub conectado é avaliado para cada SSP × ano.
    Retorna contagens (uint16) só nas células válidas e as exposições de cada realização."""
    p = pkg.params
    rng = np.random.default_rng(seed)
    bias, sd = core.dem_error_maps(pkg.layers["landcover"], p.get("dem_error", {}))
    corr = float(os.environ.get("COASTSHIFT_ELL") or p.get("dem_error", {}).get("corr_length_m", 300.0)) / pkg.cell  # ℓ (m)
    jobs = [tuple(j) for j in opt["jobs"]] if opt.get("jobs") else [(s, y) for s in opt["ssps"] for y in opt["years"]]
    valid = np.isfinite(pkg.dem)
    vidx = np.flatnonzero(valid)
    count = {jb: np.zeros(vidx.size, "uint16") for jb in jobs}
    totals = {jb: [] for jb in jobs}
    a_ha = pkg.cell ** 2 / 1e4
    pop = np.nan_to_num(pkg.layers["pop"]).ravel()
    bld = np.nan_to_num(pkg.layers["buildings"]).ravel()
    mang = np.isin(pkg.layers["landcover"], p.get("habitat", {}).get("mangrove_classes", [5])).ravel()
    # Incerteza do nível de referência (opcional, COASTSHIFT_MC_NIVEL=1): NMM local ~ N(0, σ_NMM) e fator de transferência
    # da maré f_s × N(1, σ_fs) por realização. Gerador separado, para manter pareadas as demais variáveis aleatórias.
    inc = p.get("incerteza_nivel", {}) if os.environ.get("COASTSHIFT_MC_NIVEL") == "1" else {}
    rng_n = np.random.default_rng([int(seed), 99])
    for k in range(n):
        u = rng.uniform()
        d_nmm, m_fs = (rng_n.normal(0.0, inc.get("nmm_sd_m", 0.0)), rng_n.normal(1.0, inc.get("fs_sd_rel", 0.0))) if inc else (0.0, 1.0)
        base = core.sea_level_event(p, opt.get("ref", "MHWS"), opt.get("tr", 0), rng=rng,
                                    with_setup=opt.get("setup", False), amp=opt.get("amp", 1.0) * m_fs) + d_nmm
        eps = core.correlated_field(pkg.dem.shape, corr, rng)
        fc = float(p.get("dem_error", {}).get("frac_correlated", 1.0))     # parte correlacionada da variância (pepita = 1 − fc)
        if fc < 1.0:
            eps = np.sqrt(fc) * eps + np.sqrt(1.0 - fc) * rng.standard_normal(pkg.dem.shape).astype("float32")
        z = pkg.dem - bias - sd * float(p.get("dem_error", {}).get("sd_scale", 1.0)) * eps   # Eq. 11
        for jb in jobs:
            wet = core.connected_flood(z, base + core.delta_rsl(p, jb[0], jb[1], u), pkg.sea,
                                       opt.get("conn", 8)).ravel()        # Eqs. 13–14
            count[jb] += wet[vidx]
            idx = np.flatnonzero(wet)
            totals[jb].append({"area_ha": idx.size * a_ha, "populacao": float(pop[idx].sum()),
                               "edificacoes": float(bld[idx].sum()), "mangue_ha": float(mang[idx].sum() * a_ha)})
        if k % 5 == 0:
            progress(k / n, f"realização {k}/{n}")
    return count, totals


def o2_resultado(pkg, opt, count, totals, n):
    """Monta camadas (probabilidade, erro-padrão) e a tabela de exposição a partir das contagens."""
    res = Result(meta={"modelo": "O2", **opt})
    p, a_ha = pkg.params, pkg.cell ** 2 / 1e4
    vidx = np.flatnonzero(np.isfinite(pkg.dem))
    for (ssp, yr), c in count.items():
        prob = np.full(pkg.dem.size, np.nan, "float32")
        prob[vidx] = c / n
        prob = prob.reshape(pkg.dem.shape)
        prob[pkg.sea] = 0.0
        key = f"{ssp}_{yr}"
        res.layers[f"probabilidade_{key}"] = prob
        res.layers[f"erro_padrao_MC_{key}"] = np.sqrt(prob * (1 - prob) / n).astype("float32")
        row = {"cenario": ssp, "ano": yr, "N": n, "dRSL_p50_m": round(float(core.delta_rsl(p, ssp, yr, 0.5)), 3)}
        for var in ("area_ha", "populacao", "edificacoes", "mangue_ha"):
            v = np.array([t[var] for t in totals[(ssp, yr)]])
            row[f"{var}_media"] = round(float(v.mean()), 1)
            row[f"{var}_p05"] = round(float(np.percentile(v, 5)), 1)
            row[f"{var}_p95"] = round(float(np.percentile(v, 95)), 1)
        row["area_ha_p>=0.5"] = round(float((np.nan_to_num(prob) >= 0.5).sum() * a_ha), 1)
        res.table.append(row)
    return res


def run_o2(pkg, opt, progress=_noop):
    """O2 – estático probabilístico (Monte Carlo)."""
    n = int(opt.get("n", 200))
    count, totals = o2_realizacoes(pkg, opt, n, opt.get("seed", 42), progress)
    res = o2_resultado(pkg, opt, count, totals, n)
    progress(1.0, "O2 concluído")
    return res


# ======================================================================= O3
def inertial_solver(z, sea, cell, manning, level_fn, t_end, rain_mmh=0.0, alpha=0.7,
                    hmin=1e-3, wet_thr=0.05, progress=_noop):
    """Solver 2D inercial local (Bates et al., 2010; Eqs. 15–16) em grade regular."""
    z = np.where(sea & ~np.isfinite(z), -10.0, z)          # mar sem cota -> leito a -10 m
    z = np.where(np.isfinite(z), z, 1e4).astype("float64")  # terra sem dado -> parede
    zmin_land = z[~sea].min() if (~sea).any() else 0.0
    ny, nx = z.shape
    h = np.zeros_like(z)
    qx, qy = np.zeros((ny, nx + 1)), np.zeros((ny + 1, nx))
    n2 = np.asarray(manning, float) ** 2
    n2x = 0.5 * (n2[:, :-1] + n2[:, 1:]) if n2.ndim else n2
    n2y = 0.5 * (n2[:-1, :] + n2[1:, :]) if n2.ndim else n2
    seax = sea[:, :-1] & sea[:, 1:]
    seay = sea[:-1, :] & sea[1:, :]
    hmax = np.zeros_like(z)
    t_arr = np.full(z.shape, np.nan)
    dur = np.zeros_like(z)
    rain = rain_mmh / 1000.0 / 3600.0
    t, last = 0.0, -1
    while t < t_end:
        lvl = level_fn(t)
        h[sea] = np.maximum(lvl - z[sea], 0.0)
        eta = z + h
        land_h = h[~sea].max() if (~sea).any() else 0.0
        dt = min(alpha * cell / np.sqrt(G_ * max(land_h, float(h.max()), lvl - zmin_land, 0.05)), 60.0)  # CFL em todo o domínio
        # faces x
        hf = np.maximum(np.maximum(eta[:, :-1], eta[:, 1:]) - np.maximum(z[:, :-1], z[:, 1:]), 0.0)
        s = (eta[:, 1:] - eta[:, :-1]) / cell
        q = qx[:, 1:-1]
        qn = (q - G_ * hf * dt * s) / (1 + G_ * dt * n2x * np.abs(q) / np.maximum(hf, hmin) ** (7 / 3))
        qn[(hf < hmin) | seax] = 0.0
        qx[:, 1:-1] = qn
        # faces y
        hf = np.maximum(np.maximum(eta[:-1, :], eta[1:, :]) - np.maximum(z[:-1, :], z[1:, :]), 0.0)
        s = (eta[1:, :] - eta[:-1, :]) / cell
        q = qy[1:-1, :]
        qn = (q - G_ * hf * dt * s) / (1 + G_ * dt * n2y * np.abs(q) / np.maximum(hf, hmin) ** (7 / 3))
        qn[(hf < hmin) | seay] = 0.0
        qy[1:-1, :] = qn
        dh = dt * ((qx[:, :-1] - qx[:, 1:]) + (qy[:-1, :] - qy[1:, :])) / cell + rain * dt
        h = np.maximum(h + dh, 0.0)
        land = ~sea
        hmax[land] = np.maximum(hmax[land], h[land])
        newly = land & (h > wet_thr) & np.isnan(t_arr)
        t_arr[newly] = t / 3600.0
        dur[land & (h > wet_thr)] += dt / 3600.0
        t += dt
        pct = int(100 * t / t_end)
        if pct != last:
            last = pct
            progress(min(t / t_end, 1.0), f"t = {t / 3600:.1f} h")
    hmax[sea] = np.nan
    return hmax, t_arr, dur


G_ = core.G


def _manning_map(pkg):
    m = pkg.params.get("manning", {"default": 0.04})
    arr = np.full(pkg.dem.shape, m.get("default", 0.04), "float64")
    for cls, v in m.get("by_class", {}).items():
        arr[pkg.layers["landcover"] == float(cls)] = v
    return arr


def _coarsen(arr, f, how="mean"):
    if f <= 1:
        return arr
    ny, nx = (arr.shape[0] // f) * f, (arr.shape[1] // f) * f
    a = arr[:ny, :nx].reshape(ny // f, f, nx // f, f)
    if how == "max":
        return np.nanmax(a, axis=(1, 3))
    if how == "sum":
        return np.nansum(a, axis=(1, 3))
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(a, axis=(1, 3))


def _refine(arr, f, shape):
    if f <= 1:
        return arr
    out = np.kron(arr, np.ones((f, f)))
    full = np.full(shape, np.nan, "float32")
    full[:out.shape[0], :out.shape[1]] = out
    return full


def hydrograph(params, peak_total, hours, amp=1.0):
    """Nível no contorno: NMM futuro + maré M2 + pulso meteorológico (Eq. 17)."""
    t = params["tide"]
    msl = t.get("msl", 0.0)
    a_tide = (t["mhws"] - msl) * amp
    surge = max(peak_total - (msl + a_tide), 0.0)
    base = peak_total - a_tide - surge  # = NMM futuro
    tp, Tm2, tau = hours / 2 * 3600, 12.42 * 3600, 6 * 3600

    def f(ts):
        return base + a_tide * np.cos(2 * np.pi * (ts - tp) / Tm2) + surge * np.exp(-((ts - tp) / tau) ** 2)
    return f


def run_o3_single(pkg, peak_total, opt, progress=_noop):
    f = int(opt.get("coarsen", 2))
    z = _coarsen(_dem_corrected(pkg), f)
    sea = _coarsen(pkg.sea.astype(float), f) > 0.5
    man = _coarsen(_manning_map(pkg), f)
    fn = hydrograph(pkg.params, peak_total, opt.get("hours", 13.0), opt.get("amp", 1.0))
    hmax, tarr, dur = inertial_solver(z, sea, pkg.cell * f, man, fn, opt.get("hours", 13.0) * 3600,
                                      opt.get("rain_mmh", 0.0), progress=progress)
    shp = pkg.dem.shape
    return _refine(hmax, f, shp), _refine(tarr, f, shp), _refine(dur, f, shp)


def run_o3(pkg, opt, progress=_noop):
    p = pkg.params
    res = Result(meta={"modelo": "O3", **opt})
    jobs = [(s, y) for s in opt["ssps"] for y in opt["years"]]
    for j, (ssp, yr) in enumerate(jobs):
        d = core.delta_rsl(p, ssp, yr, opt.get("quantile", 0.5))
        peak = core.sea_level_event(p, opt.get("ref", "MHWS"), opt.get("tr", 0),
                                    with_setup=opt.get("setup", False)) + d
        hmax, tarr, dur = run_o3_single(
            pkg, peak, opt, lambda fr, m: progress((j + fr) / len(jobs), f"{ssp} {yr} {m}"))
        key = f"{ssp}_{yr}"
        wet = np.nan_to_num(hmax) > opt.get("wet_thr", 0.05)
        res.layers[f"prof_max_{key}"] = np.where(wet, hmax, np.nan).astype("float32")
        res.layers[f"chegada_h_{key}"] = tarr.astype("float32")
        res.layers[f"duracao_h_{key}"] = np.where(wet, dur, np.nan).astype("float32")
        res.layers[f"inundado_{key}"] = wet.astype("float32")
        res.table.append({"cenario": ssp, "ano": yr, "pico_contorno_m": round(float(peak), 3),
                          "prof_max_m": round(float(np.nanmax(np.where(wet, hmax, np.nan))) if wet.any() else 0.0, 2),
                          **_exposure(pkg, wet)})
    return res


# ======================================================================= O4
def bruun_retreat(drsl, sh):
    """Recuo de Bruun R = ΔRSL·L*/(h*+B) (Eqs. 18–20)."""
    he, te = sh.get("he_m", 2.5), sh.get("te_s", 10.0)
    hstar = 2.28 * he - 68.5 * he ** 2 / (core.G * te ** 2)       # Hallermeier (1981)
    A = 0.21 * sh.get("d50_mm", 0.3) ** 0.48                        # Dean (1991)
    Lstar = (hstar / A) ** 1.5
    return drsl * Lstar / (hstar + sh.get("berm_m", 2.0)), hstar, Lstar


def run_o4(pkg, opt, progress=_noop):
    p = pkg.params
    hab, sh = p.get("habitat", {}), p.get("shoreline", {})
    lc = pkg.layers["landcover"]
    z0 = _dem_corrected(pkg)
    msl, mhws = p["tide"].get("msl", 0.0), p["tide"]["mhws"]
    amp = opt.get("amp", p["tide"].get("amplification_factor", 1.0))
    t0 = p.get("baseline", {}).get("center_year", 2014.0)
    res = Result(meta={"modelo": "O4", **opt})
    sandy = np.isin(lc, sh.get("sandy_classes", [23]))
    barrier = np.isin(lc, hab.get("barrier_classes", [24]))
    dist = ndimage.distance_transform_edt(~pkg.sea) * pkg.cell  # distância ao mar (m)
    jobs = [(s, y) for s in opt["ssps"] for y in opt["years"]]
    for j, (ssp, yr) in enumerate(jobs):
        q = opt.get("quantile", 0.5)
        d = float(core.delta_rsl(p, ssp, yr, q))
        rate = (d - float(core.delta_rsl(p, ssp, yr - 10, q))) / 10 * 1000  # mm/ano na década final
        R, hstar, Lstar = bruun_retreat(d, sh)
        eroded = sandy & ~pkg.sea & (dist - 0.5 * pkg.cell <= R)  # distância da borda da célula à linha d'água
        # habitat: elevação relativa futura (Eq. 21)
        acc = hab.get("accretion_mm_yr", 3.0) / 1000 * (yr - t0)
        zf = z0 + np.where(np.isin(lc, hab.get("mangrove_classes", [5]) + hab.get("apicum_classes", [32])), acc, 0) - d
        mhws_a = msl + (mhws - msl) * amp
        cls = np.full(lc.shape, 0, "float32")  # 0 terra firme
        cls[(zf >= msl + hab.get("mangrove_min", 0.0)) & (zf <= mhws_a + hab.get("mangrove_max_above_mhws", 0.0))] = 2  # mangue potencial
        cls[(zf > mhws_a) & (zf <= mhws_a + hab.get("apicum_band_m", 0.3))] = 3              # apicum potencial
        cls[zf < msl + hab.get("mangrove_min", 0.0)] = 1                                      # submerso/intermareal baixo
        drown = rate > hab.get("max_rsl_rate_mm_yr", 7.0)
        if drown:
            cls[cls == 2] = 1  # limiar de sobrevivência (Saintilan et al., 2020)
        cls[barrier & (cls >= 2)] = 4  # migração bloqueada por ocupação urbana
        cls[pkg.sea] = np.nan
        cls[eroded] = 5
        wet = core.connected_flood(z0, mhws_a + d, pkg.sea, opt.get("conn", 8))
        key = f"{ssp}_{yr}"
        res.layers[f"habitat_{key}"] = cls
        res.layers[f"erosao_{key}"] = eroded.astype("float32")
        res.layers[f"inundado_MHWS_{key}"] = wet.astype("float32")
        a = pkg.cell ** 2 / 1e4
        mang_now = np.isin(lc, hab.get("mangrove_classes", [5])).sum() * a
        res.table.append({"cenario": ssp, "ano": yr, "dRSL_m": round(d, 3), "taxa_mm_ano": round(rate, 1),
                          "recuo_Bruun_m": round(R, 1), "h*_m": round(hstar, 2), "L*_m": round(Lstar, 1),
                          "mangue_atual_ha": round(float(mang_now), 1),
                          "mangue_potencial_ha": round(float((cls == 2).sum() * a), 1),
                          "migracao_bloqueada_ha": round(float((cls == 4).sum() * a), 1),
                          "erosao_ha": round(float(eroded.sum() * a), 1),
                          "afogamento_mangue": bool(drown), **_exposure(pkg, wet)})
        progress((j + 1) / len(jobs), key)
    res.meta["legenda_habitat"] = {0: "terra firme", 1: "submerso/intermareal baixo", 2: "mangue potencial",
                                   3: "apicum potencial", 4: "migração bloqueada (urbano)", 5: "erodido"}
    return res


# ======================================================================= O5
def damage_fraction(depth, dmg):
    return np.interp(np.nan_to_num(depth), dmg["curve_depth"], dmg["curve_frac"], left=0.0)


def run_o5(pkg, opt, progress=_noop):
    """Biblioteca de simulações O3 → emulador por interpolação → Monte Carlo anual → EAD (Eqs. 22–24)."""
    p = pkg.params
    e, dmg = p["extremes"], p["damage"]
    rng = np.random.default_rng(opt.get("seed", 7))
    res = Result(meta={"modelo": "O5", **opt})
    dmax = max(float(core.delta_rsl(p, s, max(opt["years"]), 0.95)) for s in opt["ssps"])
    lo = e["threshold"]
    hi = core.gpd_return_level(e["threshold"], e["scale"], e["shape"], e["rate"], 500) + dmax + 0.2
    K = int(opt.get("library", 5))
    levels = np.linspace(lo, hi, K)
    lib = []
    for i, L in enumerate(levels):
        hmax, _, _ = run_o3_single(pkg, float(L), opt,
                                   lambda fr, m, i=i: progress(0.6 * (i + fr) / (K + 1), f"biblioteca {i + 1}/{K} {m}"))
        lib.append(np.nan_to_num(hmax))
    lib = np.stack(lib)
    lib = np.maximum.accumulate(lib, axis=0)  # monotonicidade física

    def emulate(L):
        L = float(np.clip(L, levels[0], levels[-1]))
        k = min(int(np.searchsorted(levels, L)), K - 1)
        k = max(k, 1)
        w = (L - levels[k - 1]) / (levels[k] - levels[k - 1])
        return (1 - w) * lib[k - 1] + w * lib[k]

    # validação do emulador com um nível fora da biblioteca
    Lv = 0.5 * (levels[K // 2 - 1] + levels[K // 2])
    hv, _, _ = run_o3_single(pkg, float(Lv), opt, lambda fr, m: progress(0.6 + 0.15 * fr, f"validação emulador {m}"))
    hv, he = np.nan_to_num(hv), emulate(Lv)
    a, b = hv > 0.05, he > 0.05
    tp, fp, fn = (a & b).sum(), (~a & b).sum(), (a & ~b).sum()
    res.meta["validacao_emulador"] = {"nivel_m": round(float(Lv), 3),
                                      "RMSE_prof_m": round(float(np.sqrt(np.mean((hv - he)[a | b] ** 2))) if (a | b).any() else 0.0, 3),
                                      "CSI": round(float(tp / max(tp + fp + fn, 1)), 3)}
    value = np.nan_to_num(pkg.layers["buildings"]) * dmg.get("value_per_building", 1.0)
    pop = np.nan_to_num(pkg.layers["pop"])
    n = int(opt.get("n", 300))
    jobs = [(s, y) for s in opt["ssps"] for y in opt["years"]]
    for j, (ssp, yr) in enumerate(jobs):
        u = rng.uniform(size=n)
        drs = np.array([core.delta_rsl(p, ssp, yr, ui) for ui in u])
        amax = core.gpd_annual_max_sample(e["threshold"], e["scale"], e["shape"], e["rate"], rng, n)
        ead_map = np.zeros(pkg.dem.shape)
        aep_map = np.zeros(pkg.dem.shape)
        losses, people = [], []
        for k in range(n):
            dep = emulate(amax[k] + drs[k])
            loss = value * damage_fraction(dep, dmg)
            ead_map += loss
            aep_map += dep > dmg.get("people_depth_threshold", 0.15)
            losses.append(loss.sum())
            people.append((pop * (dep > dmg.get("people_depth_threshold", 0.15))).sum())
        key = f"{ssp}_{yr}"
        res.layers[f"EAD_{key}"] = (ead_map / n).astype("float32")
        res.layers[f"prob_anual_inund_{key}"] = (aep_map / n).astype("float32")
        losses, people = np.array(losses), np.array(people)
        res.table.append({"cenario": ssp, "ano": yr, "N_anos_amostrados": n,
                          "EAD": round(float(losses.mean()), 0),
                          "perda_p95": round(float(np.percentile(losses, 95)), 0),
                          "pessoas_atingidas_ano_media": round(float(people.mean()), 1),
                          "pessoas_p95": round(float(np.percentile(people, 95)), 1)})
        progress(0.75 + 0.25 * (j + 1) / len(jobs), key)
    return res


RUNNERS = {"O1": run_o1, "O2": run_o2, "O3": run_o3, "O4": run_o4, "O5": run_o5}
