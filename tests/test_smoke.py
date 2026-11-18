"""Teste rápido dos cinco modelos e da validação com dados sintéticos: python tests/test_smoke.py"""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from coastshift import demo, io, models, validation

d = demo.make_demo(os.path.join(tempfile.gettempdir(), "coastshift_demo"), n=120)
pkg = io.Package(d)
base = {"ssps": ["ssp245", "ssp585"], "years": [2050, 2100], "ref": "MHWS", "quantile": 0.5}
opts = {"O1": base, "O2": {**base, "n": 40}, "O3": {**base, "hours": 6, "coarsen": 2},
        "O4": base, "O5": {**base, "ssps": ["ssp245"], "years": [2100], "hours": 6, "coarsen": 2, "library": 4, "n": 60}}
for m, o in opts.items():
    t = time.time()
    r = models.RUNNERS[m](pkg, o)
    print(m, f"{time.time()-t:.1f}s", len(r.layers), "camadas |", r.table[-1])
    if m == "O5":
        print("   emulador:", r.meta["validacao_emulador"])
stats, err = validation.dem_vs_points(pkg.dem, pkg.profile, pkg.layers["landcover"], os.path.join(d, "validacao_pontos_dem.csv"))
print(stats.head(3).to_string(index=False)); print("dem_error:", err)
obs = validation.read_mask_aligned(os.path.join(d, "observado_inundacao.tif"), pkg.profile)
r1 = models.run_o1(pkg, {"ssps": ["ssp245"], "years": [2020], "ref": "MHWS"})
print("CSI O1 vs observado:", validation.flood_skill(r1.layers["inundado_ssp245_2020"], obs, ~pkg.sea))
print("OK")
