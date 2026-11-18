# %% [markdown]
# # 03 — Exportar modelos digitais de elevação por setor (GEE → Drive)
# - Copernicus DEM GLO-30 (`COPERNICUS/DEM/GLO30`, bandas DEM e WBM; alturas ortométricas EGM2008, EPSG:3855)
# - FABDEM V1-2 (`projects/sat-io/open-datasets/FABDEM`; EGM2008; licença CC BY-NC-SA 4.0 — uso não comercial)
# - ANADEM v1 (ANA/IPH-UFRGS; Laipelt et al., 2024): informe `anadem_asset` no config **ou** baixe os tiles
#   (https://www.ufrgs.br/hge/anadem-modelo-digital-de-terreno-mdt/) para `anadem_tiles/` — o script 10 os mosaica.
# Todos exportados em EPSG:31984, 30 m, sem reamostragem vertical. A conversão de datum é feita no script 10.

# %%
import sys
if "google.colab" in sys.modules:
    sys.path.insert(0, "/content/CoastShift/scripts")
from _comum import load_config, init_ee

cfg = load_config()
ee = init_ee(cfg)
cop = ee.ImageCollection("COPERNICUS/DEM/GLO30")
fontes = {
    "cop": cop.select("DEM").mosaic(),
    "wbm": cop.select("WBM").mosaic(),
    "fabdem": ee.ImageCollection("projects/sat-io/open-datasets/FABDEM").mosaic(),
}
if cfg.get("anadem_asset"):
    a = cfg["anadem_asset"]
    try:
        fontes["anadem"] = ee.ImageCollection(a).mosaic()
    except Exception:
        fontes["anadem"] = ee.Image(a)

# %% Exportar (uma tarefa por fonte × setor)
tasks = []
for nome, s in cfg["setores"].items():
    reg = ee.Geometry.Rectangle(s["bbox"])
    for f, img in fontes.items():
        img = img.toFloat() if f != "wbm" else img.toByte()
        t = ee.batch.Export.image.toDrive(
            image=img.clip(reg), description=f"dem_{f}_{nome}", folder=cfg["drive_folder"],
            fileNamePrefix=f"dem_{f}_{nome}", region=reg, crs=cfg["crs"], scale=cfg["scale_m"],
            maxPixels=1e13, fileFormat="GeoTIFF", formatOptions={"cloudOptimized": True})
        t.start()
        tasks.append(t)
print(len(tasks), "tarefas iniciadas")

# %% Status
for t in tasks:
    st = t.status()
    print(st["description"], st["state"], st.get("error_message", ""))
