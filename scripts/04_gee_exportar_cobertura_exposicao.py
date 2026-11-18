# %% [markdown]
# # 04 — Cobertura da terra, água, população e edificações (GEE → Drive)
# - MapBiomas Brasil, Coleção 10 (`projects/mapbiomas-public/assets/brazil/lulc/v1`, filtro collection_id = 10; CC BY 4.0)
#   Classes usadas: 5 mangue, 32 apicum, 23 praia/duna, 24 urbano, 33 água, 3 floresta…
# - JRC Global Surface Water v1.4 (`JRC/GSW1_4/GlobalSurfaceWater`, banda occurrence)
# - GHS-POP R2023A (`JRC/GHSL/P2023A/GHS_POP/2025`, pessoas por célula de 100 m)
# - Open Buildings 2.5D Temporal (`GOOGLE/Research/open-buildings-temporal/v1`, building_fractional_count) somado em 30 m
# Para população do Censo 2022 (IBGE), substitua pop.tif no script 11 (grade estatística / setores).

# %%
import sys
if "google.colab" in sys.modules:
    sys.path.insert(0, "/content/CoastShift/scripts")
from _comum import load_config, init_ee

cfg = load_config()
ee = init_ee(cfg)
ano = cfg["mapbiomas_ano"]

mb = (ee.ImageCollection("projects/mapbiomas-public/assets/brazil/lulc/v1")
      .filter(ee.Filter.eq("collection_id", 10.0)).filter(ee.Filter.eq("version", "v1"))
      .filter(ee.Filter.eq("year", ano)))
if mb.size().getInfo() == 0:  # fallback: Coleção 9, imagem de integração multibanda
    print("Coleção 10 não encontrada com esse filtro; usando Coleção 9 (2023).")
    lc = ee.Image("projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1").select("classification_2023")
else:
    lc = mb.mosaic().select(0)

gsw = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").unmask(0)
pop = ee.Image("JRC/GHSL/P2023A/GHS_POP/2025").select("population_count")
bld = (ee.ImageCollection("GOOGLE/Research/open-buildings-temporal/v1")
       .filterDate("2023-01-01", "2024-01-01").select("building_fractional_count").mosaic()
       .reduceResolution(ee.Reducer.sum(), maxPixels=1024).reproject(cfg["crs"], None, cfg["scale_m"]))

camadas = {"landcover": (lc.toInt16(), 30), "gsw": (gsw.toByte(), 30), "pop": (pop.toFloat(), 100),
           "buildings": (bld.toFloat(), 30)}

# %%
tasks = []
for nome, s in cfg["setores"].items():
    reg = ee.Geometry.Rectangle(s["bbox"])
    for k, (img, sc) in camadas.items():
        t = ee.batch.Export.image.toDrive(image=img.clip(reg), description=f"{k}_{nome}",
                                          folder=cfg["drive_folder"], fileNamePrefix=f"{k}_{nome}", region=reg,
                                          crs=cfg["crs"], scale=sc, maxPixels=1e13, fileFormat="GeoTIFF")
        t.start()
        tasks.append(t)
print(len(tasks), "tarefas iniciadas")

# %%
for t in tasks:
    st = t.status()
    print(st["description"], st["state"], st.get("error_message", ""))
# Ao concluir, copie os GeoTIFFs da pasta do Drive para <BASE>/gee/ (no Colab: shutil.copy de /content/drive/MyDrive/<pasta>).
