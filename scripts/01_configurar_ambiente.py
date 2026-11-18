# %% [markdown]
# # 01 — Configurar ambiente (Colab ou local) e parâmetros da costa da Bahia
# Cria `config_bahia.json` usado por todos os scripts seguintes.
# **Colab:** execute as células na ordem; o Drive é montado e a pasta de trabalho é criada.
# Setores S1–S6 são caixas aproximadas (lon_min, lat_min, lon_max, lat_max) — ajuste se necessário.

# %%
import json
import os
import sys

IN_COLAB = "google.colab" in sys.modules
if IN_COLAB:
    from google.colab import drive  # noqa
    drive.mount("/content/drive")
    os.system("pip -q install earthengine-api geemap rasterio xarray netCDF4 h5netcdf utide cdsapi earthaccess h5py pyproj scipy pandas")
    if not os.path.isdir("/content/CoastShift"):
        os.system("git clone -q https://github.com/rnvuefsppgm/CoastShift /content/CoastShift")
    sys.path.insert(0, "/content/CoastShift/scripts")

BASE = os.environ.get("COASTSHIFT_BASE",
                      "/content/drive/MyDrive/CoastShift_Bahia" if IN_COLAB else os.path.abspath("dados_bahia"))
os.makedirs(BASE, exist_ok=True)

# %% Parâmetros — EDITE AQUI
config = {
    "base": BASE,
    "gee_project": "SEU-PROJETO-GEE",          # ID do projeto Cloud registrado no Earth Engine
    "drive_folder": "CoastShift_Bahia_GEE",     # pasta do Drive para as exportações do GEE
    "crs": "EPSG:31984",                        # SIRGAS 2000 / UTM 24S
    "scale_m": 30,
    "zona_costeira": {"dist_max_km": 15, "cota_max_m": 25},
    "anadem_asset": "",                          # ex.: 'projects/SEU-PROJETO/assets/anadem_ba' (upload dos tiles) ou vazio
    "dem_principal": "anadem",                   # anadem | fabdem | cop
    "mapbiomas_ano": 2024,
    "ssps": ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"],
    "anos": [2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100, 2150],
    "epoca_nmm_local": {"inicio": 2004, "fim": 2024},
    "nmm_salvador_sgb_m": None,                  # NMM do marégrafo de Salvador em altitude normal SGB (relatório RMPG/IBGE)
    "setores": {
        "S1_Litoral_Norte":          {"bbox": [-38.40, -12.95, -37.30, -11.40], "ponto_mar": [-37.9, -12.4], "aberta": True,  "declividade_praia": 0.05},
        "S2_Salvador_BTS":           {"bbox": [-39.00, -13.15, -38.30, -12.50], "ponto_mar": [-38.5, -13.1], "aberta": False, "declividade_praia": 0.03},
        "S3_Baixo_Sul":              {"bbox": [-39.30, -14.20, -38.80, -13.15], "ponto_mar": [-38.8, -13.7], "aberta": False, "declividade_praia": 0.03},
        "S4_Costa_do_Cacau":         {"bbox": [-39.30, -15.75, -38.80, -14.20], "ponto_mar": [-38.9, -15.0], "aberta": True,  "declividade_praia": 0.04},
        "S5_Costa_do_Descobrimento": {"bbox": [-39.40, -17.05, -38.75, -15.75], "ponto_mar": [-38.9, -16.4], "aberta": True,  "declividade_praia": 0.04},
        "S6_Costa_das_Baleias":      {"bbox": [-39.80, -18.40, -39.00, -17.05], "ponto_mar": [-39.0, -17.8], "aberta": True,  "declividade_praia": 0.03},
    },
    # Subdomínios para O3/O5 (hidrodinâmica) — recortes menores dentro dos setores
    "subdominios": {
        "SD_Salvador_Comercio_Ribeira": {"setor": "S2_Salvador_BTS", "bbox": [-38.53, -12.98, -38.45, -12.90]},
        "SD_Ilheus":                    {"setor": "S4_Costa_do_Cacau", "bbox": [-39.08, -14.84, -39.00, -14.76]},
        "SD_Canavieiras":               {"setor": "S4_Costa_do_Cacau", "bbox": [-39.00, -15.72, -38.92, -15.64]},
        "SD_Valenca":                   {"setor": "S3_Baixo_Sul", "bbox": [-39.12, -13.40, -39.02, -13.32]},
        "SD_Caravelas":                 {"setor": "S6_Costa_das_Baleias", "bbox": [-39.30, -17.78, -39.20, -17.70]},
    },
}
with open(os.path.join(BASE, "config_bahia.json"), "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
for sub in ["gee", "ar6", "mares", "ondas", "icesat2", "hgeohnor", "anadem_tiles", "pacotes", "resultados"]:
    os.makedirs(os.path.join(BASE, sub), exist_ok=True)
print("config salvo em", os.path.join(BASE, "config_bahia.json"))

# %% Autenticar no Earth Engine (necessário para 02–04)
try:
    import ee
    ee.Authenticate()
    ee.Initialize(project=config["gee_project"])
    print("Earth Engine OK")
except Exception as e:
    print("Earth Engine não inicializado:", e)
