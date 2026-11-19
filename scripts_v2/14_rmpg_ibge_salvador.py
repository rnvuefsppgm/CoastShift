"""14 — Dados oficiais da Rede Maregráfica Permanente para Geodésia (RMPG/IBGE), estação Salvador (SAL):
arquivos anuais de observação (dados/<MMDD>/SALaaMMDD.zip), séries temporais (EMSAL) e documentos de níveis de
referência (niveis de referencia/Salvador), usados para obter o NMM de Salvador em altitude normal do SGB
(parâmetro NMM_SALVADOR_SGB_M do script 20) e para conferir a série UHSLC.
Também calcula o NMM de Salvador em altitude normal do SGB (datum de Imbituba):
  NMM_SGB = média das leituras horárias observadas (sensor radar, série EMSAL) − K1,
  K1 = constante da ficha "Correlação dos Níveis de Referência" (leituras → Datum de Imbituba; 6,747 ± 0,090 m em 2024).
Saídas: <BASE>/raw/rmpg/... e <BASE>/mares/nmm_salvador_sgb.json (lido pelo script 20)
"""
import glob
import os
import re
import shutil
import subprocess
import zipfile
from urllib.parse import quote, urljoin

import requests

import _v2

RAIZ = "https://geoftp.ibge.gov.br/informacoes_sobre_posicionamento_geodesico/rmpg/"


def listar(url):
    t = requests.get(url, headers=_v2.UA, timeout=120).text
    return [h for h in re.findall(r'href="([^"?]+)"', t) if not h.startswith(("http", "/"))]


def espelhar(url, destino, filtro=None, nivel=0):
    n = 0
    for h in listar(url):
        u = urljoin(url, h)
        if h.endswith("/"):
            if nivel < 2:
                n += espelhar(u, destino + [h.strip("/")], filtro, nivel + 1)
        elif filtro is None or re.search(filtro, h, re.I):
            if _v2.download(u, _v2.p("raw", "rmpg", *destino, requests.utils.unquote(h))):
                n += 1
    return n


def k1_da_ficha():
    """Lê K1 (média) da ficha PDF mais recente; requer pdftotext (poppler). Sem ele usa o valor de 2024."""
    fichas = sorted(glob.glob(os.path.join(_v2.p("raw", "rmpg", "niveis_referencia_Salvador"), "*.pdf")))
    if fichas and shutil.which("pdftotext"):
        txt = subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", fichas[-1], "-"], capture_output=True,
                             text=True, encoding="utf-8").stdout
        m = re.search(r"K1.{0,400}?m.dia\s*=\s*([\d,]+)\s*±\s*([\d,]+)", txt, re.S)
        if m:
            return float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", ".")), os.path.basename(fichas[-1])
    return 6.747, 0.090, "ficha RMPG Salvador 2024 (valor fixo)"


def nmm_sgb():
    zs = sorted(glob.glob(os.path.join(_v2.p("raw", "rmpg", "series_temporais_EMSAL"), "*", "*EMSAL.zip")))
    if not zs:
        _v2.log("série EMSAL ausente: NMM_SGB não calculado")
        return
    z = zipfile.ZipFile(zs[-1])
    n = [x for x in z.namelist() if x.lower().endswith(".txt") and "salv" in x.lower()][0]
    datas, obs = [], []
    for ln in z.read(n).decode("latin-1").splitlines()[1:]:
        v = [(m.start() + 16, m.group()) for m in re.finditer(r"-?\d+,\d+", ln[16:])]
        o = [x for p_, x in v if p_ < 22]                  # coluna "obser" (as linhas só com previsão são ignoradas)
        if o:
            datas.append(int(ln[6:10]))
            obs.append(float(o[0].replace(",", ".")))
    import numpy as np
    datas, obs = np.array(datas), np.array(obs)
    anos = {int(a): (float(obs[datas == a].mean()), int((datas == a).sum())) for a in np.unique(datas)}
    bons = [a for a, (_, c) in anos.items() if c > 0.8 * 8760]
    media = float(np.mean([anos[a][0] for a in bons]))
    tend = float(np.polyfit(bons, [anos[a][0] * 1000 for a in bons], 1)[0]) if len(bons) > 5 else float("nan")
    k1, k1_dp, fonte = k1_da_ficha()
    out = {"nmm_sgb_m": round(media - k1, 3), "incerteza_m": k1_dp, "media_leituras_m": round(media, 4),
           "anos_completos": bons, "K1_m": k1, "fonte_K1": fonte, "serie": n, "tendencia_mm_ano": round(tend, 2),
           "definicao": "NMM local (época dos anos completos) em altitude normal do SGB, datum de Imbituba"}
    _v2.salvar_json(out, "mares", "nmm_salvador_sgb.json")
    _v2.log(f"NMM de Salvador no SGB = {out['nmm_sgb_m']:.3f} ± {k1_dp:.3f} m ({len(bons)} anos; tendência {tend:.2f} mm/ano)")


if __name__ == "__main__":
    n = espelhar(urljoin(RAIZ, "dados/3112/"), ["dados"], r"^SAL\d{6}\.zip$")
    n += espelhar(urljoin(RAIZ, quote("niveis de referencia") + "/Salvador/"), ["niveis_referencia_Salvador"])
    n += espelhar(urljoin(RAIZ, "series_temporais/EMSAL/"), ["series_temporais_EMSAL"])
    n += espelhar(urljoin(RAIZ, "relatorio/"), ["relatorio"], r"(?i)salvador|rmpg|relat")
    _v2.log(f"RMPG: {n} arquivos baixados/conferidos em {_v2.p('raw', 'rmpg')}")
    nmm_sgb()
