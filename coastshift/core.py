"""Funções físicas e estatísticas compartilhadas (equações em docs/01_Metodos_Opcao2_Bahia.md)."""
import numpy as np
from scipy import ndimage

G = 9.81
AR6_BASE_CENTER = 2005.0  # centro do período de referência AR6 (1995–2014)


# ---------------------------------------------------------------- projeções AR6
def rsl_ar6(ar6, ssp, year, u):
    """ΔRSL (m) rel. 1995–2014 para o quantil u (0–1) por interpolação na função quantil (Eq. 5)."""
    q = np.asarray(ar6["quantiles"], float)
    years = np.asarray(ar6["years"], float)
    vals = np.asarray(ar6["scenarios"][ssp], float)  # [ano, quantil]
    yrs = np.concatenate([[AR6_BASE_CENTER], years])
    vals = np.vstack([np.zeros(len(q)), vals])
    u = np.atleast_1d(u)
    out = np.empty(u.shape)
    for i, ui in enumerate(u):
        col = np.array([np.interp(ui, q, row) for row in vals])
        out[i] = np.interp(year, yrs, col)
    return out if out.size > 1 else float(out[0])


def delta_rsl(params, ssp, year, u):
    """ΔRSL relativo à época do NMM local + VLM residual (Eqs. 4–6)."""
    ar6 = params["ar6"]
    t0 = params.get("baseline", {}).get("center_year", 2014.0)
    d = np.asarray(rsl_ar6(ar6, ssp, year, u)) - np.asarray(rsl_ar6(ar6, ssp, t0, u))
    vlm = params.get("vlm_extra_mm_yr", 0.0)
    return d - vlm * (year - t0) / 1000.0


# ---------------------------------------------------------------- extremos
def gpd_return_level(thr, scale, shape, rate, T):
    """Nível de retorno POT-GPD (Eq. 8). rate = excedências/ano; T em anos."""
    m = rate * np.asarray(T, float)
    if abs(shape) < 1e-6:
        return thr + scale * np.log(m)
    return thr + scale / shape * (m ** shape - 1.0)


def gpd_annual_max_sample(thr, scale, shape, rate, rng, n):
    """Amostra de máximos anuais pela distribuição Poisson-GPD (Eq. 9)."""
    p = rng.uniform(1e-6, 1 - 1e-6, n)
    lam = -np.log(p) / rate  # F(x) = exp(-rate * (1+ξ(x-u)/σ)^(-1/ξ))
    if abs(shape) < 1e-6:
        x = thr - scale * np.log(lam)
    else:
        x = thr + scale / shape * (lam ** (-shape) - 1.0)
    return np.maximum(x, thr - 0.5)  # anos sem excedência: nível abaixo do limiar


# ---------------------------------------------------------------- ondas
def stockdon_setup(hs, tp, beta):
    """Setup médio de Stockdon et al. (2006): <η> = 0.35 β (H0 L0)^0.5 (Eq. 10)."""
    L0 = G * tp ** 2 / (2 * np.pi)
    return 0.35 * beta * np.sqrt(hs * L0)


# ---------------------------------------------------------------- erro do DEM
def correlated_field(shape, corr_cells, rng):
    """Campo gaussiano de média 0 e variância 1 com correlação espacial (Eq. 12)."""
    f = rng.standard_normal(shape).astype("float32")
    if corr_cells > 0.5:
        f = ndimage.gaussian_filter(f, sigma=corr_cells, mode="reflect")
        s = f.std()
        f = f / s if s > 0 else f
    return f


def dem_error_maps(landcover, dem_error):
    """Mapas de viés e desvio-padrão do DEM por classe de cobertura (Eq. 11)."""
    d = dem_error.get("default", {"bias": 0.0, "sd": 1.0})
    bias = np.full(landcover.shape, d["bias"], "float32")
    sd = np.full(landcover.shape, d["sd"], "float32")
    for cls, v in dem_error.get("by_class", {}).items():
        m = landcover == float(cls)
        bias[m], sd[m] = v["bias"], v["sd"]
    return bias, sd


# ---------------------------------------------------------------- conectividade
def connected_flood(z, level, sea, conn=8):
    """Bathtub conectado (Eqs. 13–14): células z ≤ η ligadas às sementes marinhas."""
    wet = (z <= level) | sea
    wet &= np.isfinite(z) | sea
    st = np.ones((3, 3), bool) if conn == 8 else ndimage.generate_binary_structure(2, 1)
    lab, _ = ndimage.label(wet, structure=st)
    ids = np.unique(lab[sea & (lab > 0)])
    ids = ids[ids > 0]
    return np.isin(lab, ids) & ~sea


def water_reference(params, kind):
    t = params["tide"]
    return {"NMM": t.get("msl", 0.0), "MHHW": t.get("mhhw", t["mhws"]), "MHWS": t["mhws"]}[kind]


def sea_level_event(params, ref_kind, tr_years, u_gpd=None, rng=None, with_setup=False, amp=1.0):
    """Cota d'água de referência (sem ΔRSL) para o tipo de nível escolhido (Eq. 7)."""
    msl = params["tide"].get("msl", 0.0)
    if tr_years and tr_years > 0:
        e = params["extremes"]
        sc, sh = e["scale"], e["shape"]
        if rng is not None:
            sc = max(1e-3, rng.normal(sc, e.get("scale_se", 0.0)))
            sh = rng.normal(sh, e.get("shape_se", 0.0))
        lvl = gpd_return_level(e["threshold"], sc, sh, e["rate"], tr_years)
    else:
        lvl = water_reference(params, ref_kind)
    lvl = msl + (lvl - msl) * amp
    if with_setup:
        w = params.get("waves", {})
        lvl += stockdon_setup(w.get("hs", 0), w.get("tp", 0), w.get("beach_slope", 0))
    return float(lvl)
