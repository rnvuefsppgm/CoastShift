# Adendo regional — Costa do Estado da Bahia

**Complementa** a revisão genérica (`Revisao_cientifica_nivel_do_mar.html`, §§1–8) e a planilha `outputs/.../Matrizes_nivel_do_mar.xlsx` (E01–E30, D01–D32, M01–M18, C01–C16). Aqui só entra o que muda **por causa da Bahia**. IDs novos: E31+, D33+, M19+, C17+.

**Rótulos de evidência:** `[V]` verificado em fonte primária/oficial nesta sessão ou na anterior · `[C]` conhecimento consolidado da literatura, não reconsultado · `[NV]` não verificado — conferir antes de citar · `[I]` interpretação/recomendação desta revisão.

---

## 1. Por que a Bahia exige um desenho próprio

### 1.1 Forçantes físicas dominantes

| Fator | Situação na costa baiana | Consequência para a modelagem |
|---|---|---|
| Maré | Semidiurna, mesomaré; amplitude de sizígia da ordem de 2,5 m em Salvador, amplificada no interior da Baía de Todos os Santos (BTS) (Cirano & Lessa, 2007) `[C]` | A maré é a **principal** componente do nível total. Mapear só o nível médio subestima muito a área atingida com frequência. A referência de água precisa ser preamar (MHWS/MHHW) e não apenas o NMM. |
| Maré meteorológica | Moderada (dezenas de cm), associada à passagem de frentes frias e transporte de Ekman. Os episódios de erosão severa em Salvador coincidem com frentes frias em sizígia (Dutra et al., RBGf) `[V]` | Não há ciclones tropicais típicos. Envoltórias estáticas (maré + surge + SLR) são mais defensáveis aqui do que em costas com furacões `[I]`. Mesmo assim, a coincidência frente fria × sizígia controla os extremos e deve ser tratada como **evento conjunto**, não como soma de períodos de retorno. |
| Ondas | Ondulações de E–NE (alísios) e de SE–S (sistemas frontais); a costa aberta é exposta; recifes de Abrolhos, Corumbaú e beachrocks atenuam ondas e controlam a deriva (Bittencourt et al., 2000) `[V]` | Em praias expostas (Litoral Norte, Costa do Cacau, Ilhéus), *setup*/*runup* podem somar dezenas de centímetros ao nível na face de praia → incluir parametrização empírica (ex.: Stockdon et al., 2006) ou modelo de onda. Em baías e estuários, o efeito de onda local é menor e a hidrodinâmica de maré domina. |
| Tendência observada | Marégrafo de Salvador (2004–2024): elevação de **2,15 mm/ano**, aumento da frequência e severidade de níveis extremos associados a ondas subinerciais (Lessa et al., 2026, preprint SciELO) `[V]` | Há série local para calibrar a linha de base e validar extremos. Por ser série curta (21 anos), a tendência é sensível à variabilidade interanual; usar a projeção AR6 regional para o futuro e a série para referência e extremos `[I]`. |
| Movimento vertical do terreno (VLM) | Não identificamos nesta revisão estudo publicado que quantifique subsidência regional na costa baiana `[I]` | Lacuna. Auditar o termo de VLM já embutido no AR6 e verificar estações GNSS (RBMC) e InSAR antes de assumir VLM ≈ 0. Aterros urbanos (Comércio/Calçada em Salvador, áreas portuárias) são candidatos a subsidência local `[I]`. |
| Vazão fluvial | Rios Jequitinhonha, Pardo, de Contas, Una, Jaguaripe, Paraguaçu (regulado por barragem de Pedra do Cavalo), Itapicuru, Real | Em fozes e estuários, a inundação é **composta** (maré + vazão + chuva). No estuário do Maraú, um estudo com ANADEM concluiu que seria preciso aumento de ~350% na vazão para a inundação atingir a vila estudada (SBRH, 2025) `[V]`. |

### 1.2 Setorização sugerida (unidades de modelagem) `[I]`

Baseada em compartimentos geomorfológicos e hidrodinâmicos descritos para a Bahia (Bittencourt et al., 2000; Dominguez, 2009 `[C]`; MMA, 2018 `[C]`):

| Setor | Trecho | Ambientes dominantes | Processo crítico | Prioridade de método |
|---|---|---|---|---|
| S1 Litoral Norte | Mangue Seco – Itapuã | Praias expostas, dunas, falésias da Formação Barreiras, lagoas | Erosão, runup, migração de dunas | Estático + onda empírica; linha de costa |
| S2 Salvador e BTS | Itapuã – Recôncavo – Vera Cruz/Itaparica | Cidade densa, aterros, porto, baía de maré amplificada, manguezais | Inundação de maré recorrente, drenagem, extremos frente-fria | **Hidrodinâmico** (maré da BTS não é bem representada por bathtub) |
| S3 Baixo Sul | Jaguaripe – Valença – Tinharé/Boipeba – Camamu – Maraú | Estuários, manguezais extensos, ilhas-barreira | Migração de mangue, inundação estuarina composta | Hidrodinâmico em estuários + modelo de habitat |
| S4 Costa do Cacau | Itacaré – Ilhéus – Canavieiras | Planícies de cristas de praia, fozes (Contas, Cachoeira, Pardo), cidade de Ilhéus | Erosão em Ilhéus, inundação de foz | Misto: estático conectado + SFINCS em fozes urbanas |
| S5 Costa do Descobrimento | Belmonte – Porto Seguro – Cumuruxatiba | Delta do Jequitinhonha, falésias, recifes e beachrocks | Erosão de hotspots, inundação deltaica | Linha de costa + estático conectado |
| S6 Costa das Baleias | Prado – Caravelas – Mucuri | Planície costeira ampla, Abrolhos, manguezais de Caravelas | Inundação de planície baixa, habitat | Estático probabilístico + habitat |

---

## 2. Cadeia de referenciais verticais aplicada ao Brasil (crítica para a Bahia)

O erro de referencial é, na literatura, um dos que mais alteram a mancha de inundação (Gesch, 2018; Seeger & Minderhoud, 2026 — ver HTML §2 e §6). Para a Bahia a cadeia é:

```
DEM (ortométrico EGM96 ou EGM2008)
   └─ + N(EGM) ............................→ altura elipsoidal h (SIRGAS2000)
        └─ − η(hgeoHNOR2020) ..............→ altitude normal SGB (REALT-2018, datum Imbituba)
             └─ − NMM_local(SGB) ..........→ cota relativa ao nível médio local (época de referência)
                  └─ comparar com ΔRSL(AR6) + nível de maré (MHWS/MHHW) + extremos
```

- **hgeoHNOR2020** (IBGE) fornece o fator η e seu desvio-padrão para converter h → altitude normal compatível com o REALT-2018; HN = h − η; grade interpolada por spline bicúbica. O IBGE alerta que a superfície de referência das altitudes normais **não é equivalente ao geoide global**, de modo que η incorpora influências adicionais `[V]`.
- O **NMM local** em Salvador difere do datum de Imbituba por topografia dinâmica do oceano (TNMM). Esse desnível deve ser obtido pela ligação **marégrafo RMPG ↔ RN do SGB** e não presumido nulo `[C]`. Fora de Salvador, as estações da DHN/FEMAR fornecem o NR (nível de redução) relativo ao NMM (Z0) — mas a ligação ao SGB precisa ser reconstruída estação a estação `[C]`.
- **Batimetria das cartas náuticas** (DHN) está referida ao NR (aprox. baixa-mar de sizígia), com profundidades positivas para baixo. Converter para o mesmo datum antes de unir topo e batimetria `[C]`.
- **DEMs globais**: SRTM/TOPODATA → EGM96; Copernicus DEM, FABDEM → EGM2008 `[C]`. ANADEM deriva do Copernicus GLO-30 `[V]` — confirmar o datum vertical no guia do usuário `[NV]`.

**Exemplo numérico hipotético** (mesma época): DEM em altitude normal; NMM local de Salvador a +0,10 m no SGB; MHWS a +1,30 m sobre o NMM; ΔRSL(SSP2-4.5, 2100, mediana) = +0,60 m → cota d'água de preamar futura = 0,10 + 1,30 + 0,60 = **+2,00 m SGB**. Uma célula conectada a +1,70 m inunda a cada sizígia; com NMM presumido em zero e sem maré, a cota seria +0,60 m e a célula sairia "seca" — um erro de classificação de 1,4 m `[I]`. (Valores ilustrativos; os reais devem ser medidos.)

---

## 3. Cenários para a Bahia

1. **Fonte primária:** IPCC AR6 regional (D01/D02; Garner et al., 2021; Fox-Kemper et al., 2021). Usar o **ponto de grade de 1°** mais próximo de cada setor (o marégrafo de Salvador pode não constar da lista PSMSL do AR6 por série curta — verificar `[NV]`).
2. **Conjunto mínimo:** SSP1-2.6, SSP2-4.5, SSP5-8.5 × horizontes 2030, 2050, 2070, 2100 (2150 para infraestrutura de longa vida) × percentis 17-50-83. Adicionar SSP5-8.5 *low confidence* (p83) como **teste de estresse** separado (HTML §3; C06).
3. **Valores globais de referência** (AR6, mediana, rel. 1995–2014): 2050 ≈ 0,18–0,23 m; 2100 ≈ 0,38 (SSP1-1.9) a 0,77 m (SSP5-8.5) `[V]` (tabela completa no HTML §3 e aba Cenários).
4. Em costas tropicais distantes dos mantos de gelo, a impressão digital gravitacional tende a colocar o RSL **ligeiramente acima** da média global `[C]` — confirmar na extração regional.
5. **Linha de base:** alinhar a época 1995–2014 do AR6 à época do NMM local (ex.: média 2004–2024 do marégrafo de Salvador) somando a mudança 2005→2014 já observada ou extraindo a diferença dentro de cada trajetória (HTML §2) `[I]`.
6. **Extremos:** para Salvador, ajustar POT-GPD na série RMPG (2004–2024) e comparar com CoDEC/GTSM (D08) e Kirezci et al. (2020). Para setores sem marégrafo longo, usar GTSM + FES2022 com correção de viés pelas estações DHN `[I]`.
7. **Não somar** RCP e SSP nem misturar AR5 e AR6 sem harmonizar época/estatística (HTML §3).

---

## 4. O que a literatura já cobre e o que falta na Bahia

| Tema | Evidência disponível | Situação |
|---|---|---|
| Dinâmica sedimentar e deriva litorânea | Bittencourt et al. (2000) — modelo de refração e dispersão para todo o estado; Nascimento et al. (2008) Costa do Cacau `[V]` | Bom para setorização e para modelos de linha de costa (sentido da deriva, células). |
| Erosão e marés meteorológicas | Dutra et al. (Salvador, 1965–2006); estudos em Vera Cruz (2023) e Praia do Forte `[V]` | Bom para definir eventos de validação (datas de frentes frias × sizígia). |
| Oceanografia da BTS | Cirano & Lessa (2007) `[C]`; Lessa et al. (2026) série 2004–2024 com modelagem numérica e mapeamento de inundação de maré atual em Salvador `[V]` | **Principal ponto de partida** para o setor S2. |
| Inundação por SLR com DEM | Estudo do estuário do Maraú com ANADEM (SBRH 2025) `[V]`; nenhum mapeamento estadual publicado e revisado por pares foi identificado nesta busca `[I]` | **Lacuna principal** — justifica o estudo proposto. |
| Manguezais/apicuns | Mapeamento multitemporal na BTS (mangue 177,6 km²; apicum 10,2 km²; avanço do mangue sobre apicuns; Nascimento et al.) `[V conteúdo / NV referência completa]`; sem projeção de migração sob SLR identificada `[I]` | Lacuna — modelo de habitat (Opção 4). |
| Vulnerabilidade e planejamento | Salvador: PMAMC (2020) e grupo de trabalho municipal sobre elevação do nível do mar; ferramenta Climate Central lista Salvador entre cidades expostas `[V]` | Visualizadores e planos não substituem modelagem validada `[I]`. |
| Precisão de DEM em costa arenosa brasileira | Emmendorfer et al. (2024, Cassino/RS) — avaliação de DEMs globais `[V]` (E22) | Transferível com cautela; validar na Bahia com ICESat-2 e GNSS. |
| Downscaling dinâmico no Brasil | Toste et al. (2024, Guanabara, ROMS, RCP4.5) `[V]` (E21) | Modelo de referência metodológica para a BTS (Opção 4/5). |

---

## 5. Implicações metodológicas para a Bahia (síntese) `[I]`

1. **Maré > surge.** O ganho de realismo vem primeiro de usar a preamar correta e o referencial vertical certo, não de trocar de solver (coerente com Cotrim et al., 2026; HTML §8).
2. **Bathtub conectado é aceitável em costa aberta e planícies (S1, S4–S6) para triagem**, mas **não na BTS e em estuários do Baixo Sul**, onde a amplificação e a defasagem da maré e a atenuação por atrito tornam o equilíbrio estático enganoso (S2, S3).
3. **DEM é o gargalo.** Sem LiDAR estadual, usar ANADEM/FABDEM/DeltaDTM em conjunto e propagar o erro vertical (Opção 2). Áreas urbanas e manguezais são onde os DEMs globais mais erram (Hawker et al., 2022).
4. **Erosão importa tanto quanto inundação** em S1, S4 e S5 (hotspots documentados). Mapas de inundação sobre linha de costa fixa subestimam perda de terreno.
5. **Manguezais são o principal ecossistema exposto**; sua resposta depende de acreção e espaço de migração (apicuns, áreas baixas não ocupadas) — modelar com regras de quadro de maré.

Ver as **cinco opções de implementação** em `03_Cinco_Opcoes_Modelagem_Bahia.md` e as bases em `02_Inventario_Bases_Bahia.md`.
