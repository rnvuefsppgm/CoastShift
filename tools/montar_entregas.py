"""Monta as entregas finais em Ana_Model/entregas (artigo EN/PT + suplementar, documento metodológico com a
revisão, apresentação). Requer os resultados dos scripts 21–28 e o texto S1 em <entregas>/01_artigo/s1_texto.json.
Uso: python tools/montar_entregas.py
"""
import glob
import json
import os
import shutil
import subprocess
import sys

import pandas as pd
import pypandoc
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

AM = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))       # Ana_Model
RES, ENT, REPO = os.path.join(AM, "resultados_O2_Bahia"), os.path.join(AM, "entregas"), os.path.join(AM, "CoastShift")
ART, FIG = os.path.join(ENT, "01_artigo"), os.path.join(ENT, "01_artigo", "figuras")
SUP = os.path.join(ART, "suplementar")


def ref_doc(path):
    pd_ = pypandoc.get_pandoc_path()
    open(path, "wb").write(subprocess.run([pd_, "--print-default-data-file", "reference.docx"], capture_output=True).stdout)
    d = Document(path)
    for name, size, bold in [("Normal", 11, None), ("Body Text", 11, None), ("First Paragraph", 11, None), ("Compact", 9, None),
                             ("Title", 16, True), ("Subtitle", 12, False), ("Heading 1", 13, True), ("Heading 2", 12, True),
                             ("Heading 3", 11, True), ("Image Caption", 9.5, False), ("Table Caption", 9.5, False)]:
        try:
            st = d.styles[name]
        except KeyError:
            continue
        st.font.name, st.font.size = "Times New Roman", Pt(size)
        rpr = st.element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.append(rf)
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(a), "Times New Roman")
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
            if rf.get(qn(a)) is not None:
                del rf.attrib[qn(a)]
        if bold is not None:
            st.font.bold = bold
        st.font.color.rgb = RGBColor(0, 0, 0)
        pf = st.paragraph_format
        if name in ("Body Text", "First Paragraph"):
            pf.line_spacing, pf.alignment, pf.space_after = 1.5, WD_ALIGN_PARAGRAPH.JUSTIFY, Pt(6)
        if name.startswith("Heading"):
            pf.space_before, pf.space_after, pf.keep_with_next = Pt(12), Pt(6), True
    d.save(path)


def md_docx(md, docx, rdoc, recursos):
    pypandoc.convert_file(md, "docx", outputfile=docx, extra_args=["--reference-doc", rdoc, f"--resource-path={recursos}"])
    d = Document(docx)
    for t in d.tables:
        tp = t._tbl.tblPr
        b = OxmlElement("w:tblBorders")
        for e in ("top", "bottom", "insideH"):
            x = OxmlElement(f"w:{e}")
            x.set(qn("w:val"), "single")
            x.set(qn("w:sz"), "6")
            x.set(qn("w:color"), "000000")
            b.append(x)
        old = tp.find(qn("w:tblBorders"))
        if old is not None:
            tp.remove(old)
        tp.append(b)
        for r in t.rows:
            for c in r.cells:
                for p in c.paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(9)
    for p in d.paragraphs:                                     # figuras: largura máxima de 6,3 in
        for r in p.runs:
            for ins in r._r.findall(".//" + qn("wp:inline")):
                ext = ins.find(qn("wp:extent"))
                cx, cy = int(ext.get("cx")), int(ext.get("cy"))
                mx = int(Inches(6.3))
                if cx > mx:
                    ext.set("cx", str(mx))
                    ext.set("cy", str(int(cy * mx / cx)))
                    for g in ins.findall(".//" + qn("a:ext")):
                        g.set("cx", str(mx))
                        g.set("cy", str(int(cy * mx / cx)))
    d.save(docx)


def tabela_md(df, cols=None, n=None):
    df = df[cols] if cols else df
    df = df.head(n) if n else df
    linhas = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    for _, r in df.iterrows():
        linhas.append("| " + " | ".join(f"{v:,.2f}" if isinstance(v, float) else str(v) for v in r.values) + " |")
    return "\n".join(linhas)


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    os.makedirs(SUP, exist_ok=True)
    # 1) figuras principais
    for f in ["mapas/Fig_costa_atual_2014", "mapas/Fig_painel_costa_2100", "mapas/Fig_costa_ssp585_2100",
              "graficos/Fig_validacao_DEM", "graficos/Fig_trajetoria_area", "graficos/Fig_inundacao_adicional",
              "graficos/Fig_exposicao_setores", "graficos/Fig_niveis_referencia", "graficos/Fig_sensibilidade",
              "graficos/Fig_validacao_mare", "graficos/Fig_O1_O2_O3_Salvador"]:
        for ext in (".png", ".pdf"):
            if os.path.exists(os.path.join(RES, f + ext)):
                shutil.copy(os.path.join(RES, f + ext), FIG)
    # 2) textos da validação S1
    s1 = json.load(open(os.path.join(ART, "s1_texto.json"), encoding="utf-8"))
    for md, chaves in [(os.path.join(ART, "EN", "manuscript_EN.md"), ("S1_ABSTRACT", "S1_RESULTADOS")),
                       (os.path.join(ART, "PT", "manuscrito_PT.md"), ("S1_RESUMO", "S1_RESULTADOS_PT"))]:
        t = open(md, encoding="utf-8").read()
        for k in chaves:
            t = t.replace(f"[[{k}]]", s1[k])
        open(md, "w", encoding="utf-8").write(t)
    # 3) suplementar (tabelas e mapas)
    for d_ in ("mapas_principais", "mapas_episodicos_2150", "tabelas", "validacao"):
        os.makedirs(os.path.join(SUP, d_), exist_ok=True)
    for f in glob.glob(os.path.join(RES, "mapas", "*.png")):
        shutil.copy(f, os.path.join(SUP, "mapas_principais"))
    for pasta in ("episodico_NMM", "episodico_TR10", "episodico_TR100", "horizonte_2150"):
        for f in glob.glob(os.path.join(RES, pasta, "mapas", "*.png")):
            shutil.copy(f, os.path.join(SUP, "mapas_episodicos_2150", f"{pasta}_{os.path.basename(f)}"))
    for f in glob.glob(os.path.join(RES, "tabelas", "*.*")) + glob.glob(os.path.join(RES, "sensibilidade", "*.csv")):
        shutil.copy(f, os.path.join(SUP, "tabelas"))
    for f in glob.glob(os.path.join(RES, "validacao", "*.csv")) + glob.glob(os.path.join(RES, "validacao", "*.json")):
        shutil.copy(f, os.path.join(SUP, "validacao"))
    for f in ("Fig_municipios_top15", "Fig_incerteza", "Fig_convergencia"):
        if os.path.exists(os.path.join(RES, "graficos", f + ".png")):
            shutil.copy(os.path.join(RES, "graficos", f + ".png"), FIG)
    mun = pd.read_csv(os.path.join(RES, "tabelas", "municipios_O2.csv"))
    sen = pd.read_csv(os.path.join(RES, "sensibilidade", "sensibilidade.csv"))
    sen_t = sen[sen.setor == "TOTAL_COSTA_BAHIA"].pivot_table(index="variante", columns="cenario", values="dif_vs_base_%").round(1).reset_index()
    par = json.load(open(os.path.join(AM, "dados_bahia_v2", "ondas", "ondas_setores.json"), encoding="utf-8"))
    mar = json.load(open(os.path.join(AM, "dados_bahia_v2", "mares", "mares_setores.json"), encoding="utf-8"))
    tpar = pd.DataFrame([{"sector": k, "MHWS (m)": mar[k]["mhws"], "MHHW (m)": mar[k]["mhhw"], "f_s": mar[k]["fator_transferencia_salvador"],
                          "Hs99 (m)": v["hs"], "Tp (s)": v["tp"], "beta_f": v["beach_slope"], "set-up (m)": v["setup_stockdon_m"],
                          "open coast": v["costa_aberta"]} for k, v in par.items()])
    s1v = os.path.join(RES, "validacao", "s1_intermare_metricas.csv")
    tval = pd.read_csv(s1v) if os.path.exists(s1v) else pd.DataFrame()
    for lang in ("EN", "PT"):
        L = (lambda en, pt: en if lang == "EN" else pt)
        txt = [f"---\ntitle: \"{L('Supplementary Material', 'Material Suplementar')}\"\nsubtitle: \"{L('Closing the vertical-datum chain for probabilistic sea-level rise inundation mapping — coast of Bahia, Brazil', 'Fechando a cadeia de referenciais verticais no mapeamento probabilístico da inundação pela ENM — costa da Bahia, Brasil')}\"\n---\n",
               L("# S1. Literature review and model options", "# S1. Revisão da literatura e opções de modelagem"),
               L("The full review (research questions RQ1–RQ10, model families A–H, data inventory and the five model options O1–O5) is provided in Portuguese in `02_metodologia_e_revisao/Documento_metodologico_e_revisao.docx`. Model O2 was selected for the reasons summarised in Section 3 of the main text.",
                 "A revisão completa (questões RQ1–RQ10, famílias de modelos A–H, inventário de dados e as cinco opções O1–O5) está em `02_metodologia_e_revisao/Documento_metodologico_e_revisao.docx`. O Modelo O2 foi escolhido pelas razões resumidas na Seção 3 do texto principal."),
               L("# S2. Sector parameters", "# S2. Parâmetros por setor"),
               L("**Table S1.** Tidal datums (relative to MSL), transfer factor and wave parameters by sector.", "**Tabela S1.** Níveis de maré (em relação ao NMM), fator de transferência e parâmetros de onda por setor."),
               tabela_md(tpar),
               L("# S3. Sensitivity results", "# S3. Resultados de sensibilidade"),
               L("**Table S2.** Change in coast-wide expected inundated area relative to the baseline (%), N = 100, paired seeds (tide-amplification variants affect sector S2 only; see main text).",
                 "**Tabela S2.** Variação da área esperada inundada da costa em relação à base (%), N = 100, sementes pareadas (as variantes de amplificação afetam só o S2; ver texto principal)."),
               tabela_md(sen_t),
               L("# S4. Municipalities", "# S4. Municípios"),
               L("**Table S3.** Expected inundated area (ha) and expected exposed population by municipality (top 20 by SSP5-8.5 2100).",
                 "**Tabela S3.** Área esperada inundada (ha) e população exposta esperada por município (20 maiores no SSP5-8.5 2100)."),
               tabela_md(mun, ["municipio", "E_A_ha_atual", "E_A_ha_ssp245_2100", "E_A_ha_ssp585_2100", "pop_esperada_atual", "pop_esperada_ssp585_2100"], 20),
               f"![{L('Figure S1. Municipalities with the largest expected inundated area.', 'Figura S1. Municípios com maior área esperada inundada.')}](../figuras/Fig_municipios_top15.png)",
               L("# S5. Uncertainty and convergence", "# S5. Incerteza e convergência"),
               f"![{L('Figure S2. Monte Carlo standard error and FABDEM × Copernicus agreement (SSP5-8.5, 2100).', 'Figura S2. Erro-padrão do Monte Carlo e concordância FABDEM × Copernicus (SSP5-8.5, 2100).')}](../figuras/Fig_incerteza.png)",
               f"![{L('Figure S3. Monte Carlo convergence (N = 250 vs N = 500).', 'Figura S3. Convergência do Monte Carlo (N = 250 × N = 500).')}](../figuras/Fig_convergencia.png)",
               L("# S6. Tidal-inundation validation by sector", "# S6. Validação da inundação pela maré por setor"),
               (tabela_md(tval, [c for c in ["setor", "preamar", "nivel_preamar_m", "baixamar", "nivel_baixamar_m", "TP", "FP", "FN", "CSI", "HR", "FAR", "Brier", "sem_mangue_CSI"] if c in tval.columns]) if len(tval) else ""),
               L("Sentinel-2 single-scene and high/low-tide pair diagnostics are in `validacao/` (sentinel2_cena_unica_metricas.csv, intermare_metricas.csv).",
                 "Os diagnósticos do Sentinel-2 (cena única e pares preamar/baixa-mar) estão em `validacao/` (sentinel2_cena_unica_metricas.csv, intermare_metricas.csv)."),
               L("# S7. Maps", "# S7. Mapas"),
               L("All coast maps (present day and 15 scenario–horizon combinations), sector panels, and the maps for MSL, 10- and 100-year return levels and 2150 are provided as 600 dpi PNG files in `mapas_principais/` and `mapas_episodicos_2150/`. GeoTIFF probability and class rasters are reproducible with scripts 21–22.",
                 "Todos os mapas da costa (Atual e 15 combinações cenário–horizonte), os painéis por setor e os mapas de NMM, TR 10 e 100 anos e 2150 estão em PNG 600 dpi nas pastas `mapas_principais/` e `mapas_episodicos_2150/`. Os rasters GeoTIFF de probabilidade e classe são reproduzíveis com os scripts 21–22."),
               L("# S8. Software", "# S8. Software"),
               L("CoastShift v1.0.1 (GPL-3.0): https://github.com/rnvuefsppgm/CoastShift. Scripts 00–29 (`scripts_v2`), the application (`app.py`, `CoastShift.exe`) and the tutorials are listed in `04_scripts_e_tutorial` and `05_tutorial_aplicacao`.",
                 "CoastShift v1.0.1 (GPL-3.0): https://github.com/rnvuefsppgm/CoastShift. Os scripts 00–29 (`scripts_v2`), o aplicativo (`app.py`, `CoastShift.exe`) e os tutoriais estão em `04_scripts_e_tutorial` e `05_tutorial_aplicacao`.")]
        open(os.path.join(SUP, f"Supplementary_{lang}.md"), "w", encoding="utf-8").write("\n\n".join(txt))
    rdoc = os.path.join(ART, "_ref.docx")
    ref_doc(rdoc)
    md_docx(os.path.join(ART, "EN", "manuscript_EN.md"), os.path.join(ART, "EN", "Manuscript_EN.docx"), rdoc, os.path.join(ART, "EN"))
    md_docx(os.path.join(ART, "PT", "manuscrito_PT.md"), os.path.join(ART, "PT", "Manuscrito_PT.docx"), rdoc, os.path.join(ART, "PT"))
    for lang in ("EN", "PT"):
        md_docx(os.path.join(SUP, f"Supplementary_{lang}.md"), os.path.join(SUP, f"Supplementary_{lang}.docx"), rdoc, SUP)
    # 4) documento metodológico + revisão (PT)
    D2 = os.path.join(ENT, "02_metodologia_e_revisao")
    pt = open(os.path.join(ART, "PT", "manuscrito_PT.md"), encoding="utf-8").read()
    metodos = pt[pt.index("# 3. Escolha do modelo"):pt.index("# 5. Resultados")].replace("../figuras/", "../01_artigo/figuras/")
    metodos = metodos.replace("\n# ", "\n## ").replace("\n## 3. Escolha", "\n## 3. Escolha")
    revisao_md = pypandoc.convert_file(os.path.join(AM, "Revisao_cientifica_nivel_do_mar.html"), "markdown", format="html")
    revisao_md = "\n".join(("#" + l if l.startswith("#") else l) for l in revisao_md.splitlines())
    corpo = (open(os.path.join(D2, "parte1_decisoes.md"), encoding="utf-8").read()
             + "\n\n# Parte II — Metodologia detalhada (Modelo O2 e fluxo V2)\n\n" + metodos
             + "\n\n## Operação: scripts, parâmetros e tutoriais\n\nA execução passo a passo (scripts 00–29, entradas, saídas e verificações) está em `04_scripts_e_tutorial/Tutorial_scripts_fluxo_V2.docx`; o uso do aplicativo e a execução em lote estão em `05_tutorial_aplicacao/Tutorial_aplicacao_e_lote.docx`.\n\n"
             + "# Parte III — Revisão científica de base\n\n" + revisao_md)
    open(os.path.join(D2, "Documento_metodologico_e_revisao.md"), "w", encoding="utf-8").write(corpo)
    md_docx(os.path.join(D2, "Documento_metodologico_e_revisao.md"), os.path.join(D2, "Documento_metodologico_e_revisao.docx"), rdoc, D2)
    os.remove(rdoc)
    # 5) apresentação
    D3 = os.path.join(ENT, "03_apresentacao")
    os.makedirs(D3, exist_ok=True)
    num = json.load(open(os.path.join(ART, "s1_texto.json"), encoding="utf-8"))["numeros_slide"]
    json.dump(num, open(os.path.join(D3, "_num.json"), "w", encoding="utf-8"))
    subprocess.run([sys.executable, os.path.join(REPO, "tools", "apresentacao.py"), FIG, os.path.join(D3, "app_tela.png"),
                    os.path.join(D3, "Apresentacao_CoastShift_Modelo2.pptx"), os.path.join(D3, "_num.json")], check=True)
    os.remove(os.path.join(D3, "_num.json"))
    print("entregas montadas")
