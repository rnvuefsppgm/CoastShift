# %% [markdown]
# # 02 — Zona costeira da Bahia e setores S1–S6 (Google Earth Engine)
# Zona costeira = Bahia (FAO GAUL nível 1) ∩ distância ao oceano ≤ D km ∩ (cota ≤ Hmax ou água).
# O oceano vem da banda WBM (Water Body Mask = 1) do Copernicus DEM GLO-30.
# Saídas (Drive): `zona_costeira_<setor>.geojson` (e asset opcional). Fontes: FAO GAUL 2015; Copernicus DEM GLO-30.

# %%
import sys
if "google.colab" in sys.modules:
    sys.path.insert(0, "/content/CoastShift/scripts")
from _comum import load_config, init_ee

cfg = load_config()
ee = init_ee(cfg)
zc = cfg["zona_costeira"]

bahia = (ee.FeatureCollection("FAO/GAUL/2015/level1")
         .filter(ee.Filter.eq("ADM0_NAME", "Brazil")).filter(ee.Filter.eq("ADM1_NAME", "Bahia"))
         .geometry())
cop = ee.ImageCollection("COPERNICUS/DEM/GLO30")
dem = cop.select("DEM").mosaic().setDefaultProjection("EPSG:4326", None, 30)
wbm = cop.select("WBM").mosaic().setDefaultProjection("EPSG:4326", None, 30)
ocean = wbm.eq(1)

# distância ao oceano (m) — calculada a 90 m para reduzir custo
dist = (ocean.selfMask().fastDistanceTransform(512).sqrt()
        .multiply(ee.Image.pixelArea().sqrt()).reproject("EPSG:31984", None, 90))
zona = (dist.lte(zc["dist_max_km"] * 1000)
        .And(dem.lte(zc["cota_max_m"]).Or(wbm.gt(0)))
        .clip(bahia.buffer(3000)))

# %% Vetorizar por setor e exportar
tasks = []
anteriores = ee.Geometry.MultiPolygon([])
for nome in ["S2_Salvador_BTS", "S1_Litoral_Norte", "S3_Baixo_Sul", "S4_Costa_do_Cacau",
             "S5_Costa_do_Descobrimento", "S6_Costa_das_Baleias"]:  # S2 primeiro: tem prioridade na sobreposição
    box = ee.Geometry.Rectangle(cfg["setores"][nome]["bbox"])
    reg = box.difference(anteriores, 1)
    anteriores = anteriores.union(box, 1)
    vec = (zona.selfMask().reduceToVectors(geometry=reg, scale=90, crs="EPSG:31984",
                                           maxPixels=1e10, geometryType="polygon", bestEffort=True)
           .union(100))
    fc = ee.FeatureCollection([ee.Feature(vec.geometry().simplify(90), {"setor": nome})])
    t = ee.batch.Export.table.toDrive(collection=fc, description=f"zona_costeira_{nome}",
                                      folder=cfg["drive_folder"], fileFormat="GeoJSON")
    t.start()
    tasks.append(t)
    print("exportando", nome)

# %% Acompanhar tarefas (repita a célula até COMPLETED)
for t in tasks:
    print(t.status()["description"], t.status()["state"])

# %% (Opcional) Visualizar com geemap
try:
    import geemap
    m = geemap.Map(center=[-14.5, -39.0], zoom=7)
    m.addLayer(zona.selfMask(), {"palette": ["orange"]}, "zona costeira")
    m.addLayer(ocean.selfMask(), {"palette": ["blue"]}, "oceano (WBM)")
    m
except ImportError:
    pass
