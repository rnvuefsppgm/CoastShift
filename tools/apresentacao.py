"""Gera a apresentação (PT) do Modelo 2 e do uso do CoastShift — python-pptx, 16:9, layout moderno.
Uso: python tools/apresentacao.py <pasta_figuras> <imagem_app> <saida.pptx> <json_numeros>
"""
import json
import sys

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

AZUL, LARANJA, CINZA, BRANCO, ESCURO = (RGBColor(0x0F, 0x20, 0x38), RGBColor(0xF0, 0x8A, 0x24), RGBColor(0x5A, 0x63, 0x70),
                                        RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0x1E, 0x29, 0x3B))
FIG, APP, OUT, NUM = sys.argv[1], sys.argv[2], sys.argv[3], json.load(open(sys.argv[4], encoding="utf-8"))
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BL = prs.slide_layouts[6]


def ret(s, x, y, w, h, cor, forma=MSO_SHAPE.RECTANGLE):
    r = s.shapes.add_shape(forma, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid()
    r.fill.fore_color.rgb = cor
    r.line.fill.background()
    return r


def texto(s, x, y, w, h, linhas, tam=20, cor=ESCURO, neg=False, alin=PP_ALIGN.LEFT, esp=6):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, ln in enumerate(linhas if isinstance(linhas, list) else [linhas]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        bullet = ln.startswith("• ")
        p.text = ln
        p.alignment = alin
        p.space_after = Pt(esp)
        for r in p.runs:
            r.font.size = Pt(tam)
            r.font.color.rgb = cor
            r.font.bold = neg
            r.font.name = "Segoe UI"
    return tb


def cabecalho(s, titulo, sub=None, n=None):
    ret(s, 0, 0, 13.333, 1.05, AZUL)
    ret(s, 0, 1.05, 13.333, 0.06, LARANJA)
    texto(s, 0.5, 0.18, 11.5, 0.7, titulo, 30, BRANCO, True)
    if sub:
        texto(s, 0.5, 1.2, 12.3, 0.5, sub, 15, CINZA)
    if n:
        texto(s, 12.3, 7.0, 0.9, 0.4, str(n), 11, CINZA, alin=PP_ALIGN.RIGHT)


def figura(s, f, x, y, w=None, h=None):
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    s.shapes.add_picture(f"{FIG}/{f}" if "/" not in f and "\\" not in f else f, Inches(x), Inches(y), **kw)


def cartao(s, x, y, w, h, valor, rotulo, cor=LARANJA):
    c = ret(s, x, y, w, h, RGBColor(0xF4, 0xF6, 0xF9), MSO_SHAPE.ROUNDED_RECTANGLE)
    c.adjustments[0] = 0.08
    ret(s, x, y, 0.09, h, cor)
    texto(s, x + 0.25, y + 0.12, w - 0.35, 0.7, valor, 28, AZUL, True)
    texto(s, x + 0.25, y + 0.85, w - 0.35, h - 0.9, rotulo, 13, CINZA)


n = 0
# 1 — capa
s = prs.slides.add_slide(BL)
ret(s, 0, 0, 13.333, 7.5, AZUL)
ret(s, 0, 0, 0.25, 7.5, LARANJA)
texto(s, 0.9, 1.6, 11.5, 1.2, "Inundação pela elevação do nível do mar na costa da Bahia", 40, BRANCO, True)
texto(s, 0.9, 3.0, 11.5, 0.8, "Modelo 2 (estático probabilístico) e o programa CoastShift", 24, LARANJA)
texto(s, 0.9, 4.3, 11.5, 1.4, ["Dados abertos · referencial vertical fechado · erro do relevo propagado por Monte Carlo",
                               "github.com/rnvuefsppgm/CoastShift"], 16, BRANCO)
# 2 — problema
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "O problema", "Por que mapas determinísticos de inundação enganam em costas com poucos dados", n)
texto(s, 0.6, 1.9, 6.3, 5, ["• O erro dos DEMs globais (metros) é maior que a elevação do mar até 2050 (decímetros)",
                            "• DEM, marégrafo e projeções usam referenciais verticais diferentes — desvios de ~0,5 m",
                            "• A maré domina a inundação recorrente na Bahia (mesomaré)",
                            "• Só um marégrafo geodésico longo (Salvador)",
                            "• Pergunta: qual a probabilidade de cada célula de 30 m ser inundada hoje e no futuro, e quem/o quê está exposto?"], 18)
cartao(s, 7.4, 2.0, 2.6, 1.8, "1.100 km", "de costa, 6 setores")
cartao(s, 10.2, 2.0, 2.6, 1.8, "17.549 km²", "zona costeira modelada")
cartao(s, 7.4, 4.1, 2.6, 1.8, "60 mi", "células de 30 m")
cartao(s, 10.2, 4.1, 2.6, 1.8, "16", "combinações cenário × horizonte")
# 3 — área
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Área de estudo e linha de base atual", "Zona costeira da Bahia (15 km em terra + 5 km no mar), setores S1–S6", n)
figura(s, "Fig_costa_atual_2014.png", 0.6, 1.75, h=5.6)
texto(s, 6.3, 2.0, 6.5, 5, ["• S1 Litoral Norte — praias e dunas", "• S2 Salvador e BTS — baía de maré, cidade densa",
                            "• S3 Baixo Sul — estuários e manguezais", "• S4 Costa do Cacau — planícies de cordões",
                            "• S5 Costa do Descobrimento — delta, falésias, recifes", "• S6 Costa das Baleias — planície baixa, Abrolhos",
                            f"• Hoje: {NUM['atual_EA']:,} ha de área esperada inundada na preamar de sizígia".replace(",", ".")], 17)
# 4 — escolha do modelo
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Cinco modelos — por que o Modelo 2", "Todos implementados no CoastShift; O2 é o modelo central do estudo", n)
mods = [("O1", "Bathtub conectado", "rápido, sem incerteza"), ("O2", "Estático probabilístico", "propaga o erro do DEM ✔"),
        ("O3", "Hidrodinâmico 2D", "subdomínios; verificação"), ("O4", "Costa e habitats", "erosão, manguezais"),
        ("O5", "Integrado com danos", "EAD, emulador")]
for i, (c, nome, d) in enumerate(mods):
    x = 0.6 + i * 2.5
    cor = LARANJA if c == "O2" else RGBColor(0x8A, 0x9B, 0xB0)
    k = ret(s, x, 1.9, 2.3, 2.2, RGBColor(0xF4, 0xF6, 0xF9), MSO_SHAPE.ROUNDED_RECTANGLE)
    ret(s, x, 1.9, 2.3, 0.12, cor)
    texto(s, x + 0.2, 2.1, 2.0, 0.6, c, 30, AZUL, True)
    texto(s, x + 0.2, 2.75, 2.0, 1.3, [nome, d], 14, CINZA)
texto(s, 0.6, 4.5, 12.2, 2.8, ["• Erro do DEM (NMAD ≈ 1,4 m) > elevação até 2050 → é preciso propagar a incerteza",
                               "• Inundação recorrente pela maré é lenta (12,42 h) → física estática conectada é adequada",
                               "• Escala: 60 mi de células × 500 realizações × 16 combinações → hidrodinâmico inviável",
                               "• Verificação: O3 reproduz a extensão do O2 em Salvador (CSI 0,93)"], 18)
# 5 — fluxo
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Fluxo de processamento", "14 scripts de download sem contas → pacotes por setor → Monte Carlo → produtos e validação", n)
figura(s, "Fig_fluxograma_pt.png", 3.4, 1.65, h=5.75)
# 6 — referencial vertical
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Fechando a cadeia vertical", "Todas as alturas no nível médio local de Salvador (2004–2024)", n)
texto(s, 0.6, 1.9, 7.2, 5, ["h = H(EGM2008) + N(EGM2008)", "Hₙ = h − η(hgeoHNOR2020)", "z = Hₙ − NMM_SGB",
                            "NMM_SGB = média das leituras da RMPG − K₁", "",
                            "• Mesma cadeia para o DEM e para os pontos ICESat-2",
                            "• Sem ela, a frente de inundação se desloca ~0,5 m"], 20, AZUL)
cartao(s, 8.3, 1.9, 4.4, 1.9, "0,541 ± 0,090 m", "NMM de Salvador acima do datum de Imbituba")
cartao(s, 8.3, 4.1, 4.4, 1.9, "−0,05 a +0,2 m", "viés do FABDEM em superfícies abertas (cadeia fecha)")
# 7 — erro do DEM
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Erro do relevo: por classe e correlacionado", "1,1 milhão de pontos ICESat-2; 30 % das passagens reservadas para teste", n)
figura(s, "Fig_validacao_DEM.png", 0.5, 1.8, w=8.0)
texto(s, 8.8, 1.9, 4.2, 5, ["• Viés bruto +1,46 m → corrigido −0,01 m", "• Mangue +2,8 m; floresta +3,8 m (dossel)",
                            "• 64 % do erro é espacialmente correlacionado", "• ℓ = 662 m (variograma), usado na rodada",
                            "• z_k = z − b_c − s_c·ε_k (campo gaussiano)"], 17)
# 8 — algoritmo
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Como o Modelo 2 calcula a probabilidade", "Para cada realização k = 1…500", n)
passos = ["Sorteia o quantil do AR6 (mesmo para todos os anos)", "Nível de referência: MHWS / NMM / TR + setup de ondas",
          "Sorteia o campo de erro do DEM correlacionado", "Corrige o relevo por classe de cobertura",
          "Inunda só o que está conectado ao mar (8 vizinhos)", "Repete para as 16 combinações e acumula"]
for i, p_ in enumerate(passos):
    x, y = 0.6 + (i % 3) * 4.2, 1.9 + (i // 3) * 2.3
    k = ret(s, x, y, 3.9, 2.0, RGBColor(0xF4, 0xF6, 0xF9), MSO_SHAPE.ROUNDED_RECTANGLE)
    c = ret(s, x + 0.2, y + 0.25, 0.7, 0.7, LARANJA, MSO_SHAPE.OVAL)
    texto(s, x + 0.2, y + 0.33, 0.7, 0.6, str(i + 1), 20, BRANCO, True, PP_ALIGN.CENTER)
    texto(s, x + 1.05, y + 0.25, 2.7, 1.7, p_, 16, AZUL)
texto(s, 0.6, 6.55, 12.3, 0.8, "p = fração das realizações em que a célula alaga · classes do IPCC · exposição com intervalo de 90 %", 17, CINZA)
# 9 — resultados 2100
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Resultados — 2100, cinco cenários", "Probabilidade de inundação conectada na preamar de sizígia", n)
figura(s, "Fig_painel_costa_2100.png", 0.5, 1.7, h=5.65)
texto(s, 9.0, 2.0, 4.1, 5, [f"• Hoje: {NUM['atual_EA']:,} ha".replace(",", "."), f"• 2050: {NUM['EA_2050']}",
                            f"• 2100: {NUM['EA_2100']}", f"• 2150: {NUM['EA_2150']}", "• Cenários divergem após 2050",
                            "• S3, S4 e S6 concentram a área"], 17)
# 10 — trajetória
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Trajetória da área inundada", "Área esperada na costa toda, do presente a 2150", n)
figura(s, "Fig_trajetoria_area.png", 0.5, 1.75, w=8.3)
cartao(s, 9.2, 1.9, 3.7, 1.7, "+47 %", "de hoje a 2100 (SSP5-8.5)")
cartao(s, 9.2, 3.8, 3.7, 1.7, "+37 mil ha", "nova inundação até 2100 (SSP5-8.5)")
# 11 — inundação adicional
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Onde a inundação é nova", "Células com p ≥ 0,5 hoje, novas até 2050 e novas até 2100", n)
figura(s, "Fig_inundacao_adicional.png", 0.5, 1.7, h=5.7)
texto(s, 7.8, 2.0, 5.2, 5, ["• Já hoje: 65.957 ha", "• Novas até 2050: 11.136 (SSP2-4.5) – 13.078 ha (SSP5-8.5)",
                            "• Novas até 2100: +25.742 – 36.828 ha", "• Maiores áreas: Canavieiras, Caravelas, Cairu",
                            "• Belmonte e Nova Viçosa dobram até 2100"], 17)
# 12 — exposição
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Exposição", "População, edificações e manguezais com intervalo de 90 %", n)
figura(s, "Fig_exposicao_setores.png", 0.5, 1.75, w=8.6)
texto(s, 9.4, 2.0, 3.6, 5, ["• População: 84,6 mil hoje → 118–133 mil em 2100", "• Edificações: 20 mil → 31–36 mil",
                            "• Mangue: 29 mil → 35–38 mil ha", "• S2 concentra a população; S3, o mangue"], 17)
# 13 — sensibilidade
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Robustez: sensibilidade e convergência", "Um fator por vez, sementes pareadas", n)
figura(s, "Fig_sensibilidade.png", 0.5, 1.75, w=8.4)
texto(s, 9.2, 2.0, 3.9, 5, ["• ℓ é o fator mais influente (600 m: −1 a −3 %)", "• Demais fatores: < 7 %; cenários: +47 %", "• FABDEM × Copernicus: Jaccard 0,69–0,82",
                            "• N = 250 × 500: ≤ 1,5 % na costa"], 17)
# 14 — validação
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Validação", "Inundação pela maré por radar e comparação com o modelo hidrodinâmico", n)
figura(s, "Fig_validacao_mare.png", 0.4, 1.75, w=7.0)
figura(s, "Fig_O1_O2_O3_Salvador.png", 7.6, 1.75, w=5.4)
texto(s, 7.6, 4.4, 5.4, 3, ["• Sentinel-2 passa às 12:50 UTC e nunca vê a preamar de sizígia (aliasing)",
                            "• Sentinel-1 (08 UTC) vê níveis acima da MHWS", NUM.get("S1_slide", "• Resultado do radar no relatório"),
                            "• O3 × O2 em Salvador: CSI 0,93"], 15)
# 15 — usando o programa
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Usando o aplicativo", "CoastShift.exe (Windows) ou python app.py", n)
s.shapes.add_picture(APP, Inches(0.5), Inches(1.7), width=Inches(7.6))
texto(s, 8.4, 1.9, 4.7, 5.4, ["1. Aba Dados → abrir o pacote do setor", "2. Aba Parâmetros → conferir maré, AR6, erro do DEM",
                              "3. Aba Modelo → O2, SSPs, anos, MHWS, N = 500", "4. Executar → mapa e tabela de exposição",
                              "5. Aba Validação → DEM com ICESat-2, mancha observada", "6. Exportar → GeoTIFF + CSV + metadados",
                              "Vídeo: video_app/CoastShift_demo_Modelo2_Bahia.mp4"], 16)
# 16 — lote e scripts
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Scripts e execução em lote", "Reprodutível do download ao mapa final", n)
cods = ["python 00_baixar_tudo.py            # downloads 01–14 (sem contas)",
        "python 20_montar_pacotes_O2.py      # pacotes por setor",
        "python 21_rodar_O2_resultados.py    # O2, N = 500, 16 combinações, áreas (ha)",
        "python 22_mapas_O2_Q1.py            # mapas 600 dpi + PDF",
        "python 23 / 24 / 25c / 28 …         # validação e sensibilidade",
        "python 29_lote_modelos.py --modelos O1,O3,O5 --bbox …   # qualquer modelo em lote"]
caixa = ret(s, 0.6, 1.9, 12.1, 3.9, RGBColor(0x1E, 0x29, 0x3B), MSO_SHAPE.ROUNDED_RECTANGLE)
caixa.adjustments[0] = 0.04
texto(s, 0.9, 2.1, 11.6, 3.6, cods, 17, RGBColor(0xE6, 0xED, 0xF3))
for tb in s.shapes:
    if tb.has_text_frame:
        for p in tb.text_frame.paragraphs:
            for r in p.runs:
                if r.text.startswith("python"):
                    r.font.name = "Consolas"
texto(s, 0.6, 6.05, 12.2, 1.2, "Tutoriais: entregas/04_scripts_e_tutorial e entregas/05_tutorial_aplicacao · Código: github.com/rnvuefsppgm/CoastShift", 15, CINZA)
# 17 — limitações
n += 1
s = prs.slides.add_slide(BL)
cabecalho(s, "Limitações e próximos passos", None, n)
texto(s, 0.6, 1.6, 6.0, 5.5, ["Limitações", "• Estuários grandes: O2 é limite superior", "• Maré fora de Salvador transferida por modelo",
                              "• Série de 21 anos: TR > 50 anos incerto", "• Sem drenagem, muros e morfodinâmica",
                              "• Mangue denso: ICESat-2 e radar limitados"], 18, AZUL)
texto(s, 6.9, 1.6, 6.0, 5.5, ["Próximos passos", "• Estações DHN niveladas ao SGB", "• LiDAR/GNSS nos subdomínios críticos",
                              "• O3/O5 na BTS interior e no Baixo Sul", "• Cenários de ocupação futura (SSP populacional)",
                              "• Ampliar a validação por radar"], 18, AZUL)
# 18 — encerramento
s = prs.slides.add_slide(BL)
ret(s, 0, 0, 13.333, 7.5, AZUL)
ret(s, 0, 0, 0.25, 7.5, LARANJA)
texto(s, 0.9, 2.4, 11.5, 1, "Obrigado", 44, BRANCO, True)
texto(s, 0.9, 3.6, 11.5, 1.5, ["CoastShift v1.0.1 — github.com/rnvuefsppgm/CoastShift",
                               "Artigo, material suplementar, tutoriais e scripts: pasta entregas/"], 18, LARANJA)
prs.save(OUT)
print("ok", OUT, len(prs.slides))
