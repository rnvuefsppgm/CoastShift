"""05 — JRC Global Surface Water v1.4 (Pekel et al., 2016): ocorrência de água 1984–2021 (%), blocos 10°×10°
do Google Cloud Storage público. Usada para a máscara de água/mar conectada (sementes do bathtub conectado).
Saídas: <BASE>/raw/gsw/*.tif e <BASE>/agua/gsw_ocorrencia_<setor>.tif (média, 0–100).
"""
import math
import _v2

URL = "https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/occurrence_{lo}_{la}v1_4_2021.tif"

if __name__ == "__main__":
    x0, y0, x1, y1 = _v2.aoi_bounds_ll()
    fontes = []
    for lo in range(math.floor(x0 / 10) * 10, math.ceil(x1 / 10) * 10, 10):
        for la in range(math.ceil(y1 / 10) * 10, math.floor(y0 / 10) * 10, -10):
            n_lo = f"{abs(lo)}{'W' if lo < 0 else 'E'}"
            n_la = f"{abs(la)}{'S' if la < 0 else 'N'}" if la != 0 else "0N"
            f = _v2.download(URL.format(lo=n_lo, la=n_la), _v2.p("raw", "gsw", f"occurrence_{n_lo}_{n_la}.tif"))
            if f:
                fontes.append(f)
    _v2.reprojetar_para_setores(fontes, "agua", "gsw_ocorrencia", "average", src_nodata=255)
