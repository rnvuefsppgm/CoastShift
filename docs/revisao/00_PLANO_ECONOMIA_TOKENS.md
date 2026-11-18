# Plano de economia de tokens (implementado antes da revisão)

**Data:** 18/11/2026 · **Escopo:** revisão SLR espacialmente explícita + aplicação à costa da Bahia

## Diagnóstico do diretório (feito antes de qualquer busca)

| Ativo existente | Conteúdo | Decisão |
|---|---|---|
| `Revisao_cientifica_nivel_do_mar.html` (≈57 mil caracteres de texto) | Produto 1 genérico: método, buscas Scopus/WoS, referenciais verticais, AR5/AR6/NOAA, famílias A–H, validação, 3 abordagens, ranking por escala, lacunas, 30 estudos E01–E30 | **Reaproveitar integralmente.** Não reescrever. |
| `outputs/.../Matrizes_nivel_do_mar.xlsx` | Abas Estudos (E01–E30, 22 campos), Bases (D01–D32), Modelos (M01–M18), Cenários (C01–C16) | **Reaproveitar e estender** com IDs novos (E31+, D33+, M19+, C17+) — sem duplicar linhas. |
| `Plano_de_revisao.md` | Plano anterior de busca/extração | Mantido; este plano o complementa. |

**Lacunas em relação ao novo pedido:** (1) recorte para a costa da Bahia; (2) cinco opções de modelagem graduadas por complexidade, com ferramental e acesso às bases; (3) inventário de bases brasileiras/baianas; (4) estudos brasileiros/baianos na matriz; (5) produtos em formato navegável no diretório (Markdown).

## Regras aplicadas

1. **Delta, não reescrita.** Novos arquivos tratam apenas do que falta; o conteúdo genérico é citado por ID (E/D/M/C) e por seção do HTML.
2. **Leitura enxuta.** O HTML foi convertido a texto puro uma única vez; a planilha foi lida só nas colunas de ID/nome.
3. **Verificação em lote único.** Só se busca na web o que é incerto e específico da Bahia/Brasil (DOIs, URLs de portais, produtos nacionais). Fatos já verificados na revisão anterior não são reconsultados.
4. **Sem subagentes em leque.** Um único fio de trabalho evita duplicar contexto.
5. **Um arquivo por produto novo**, com tabelas compactas; cada valor numérico fica em um lugar só.
6. **Rótulos de evidência.** `[V]` verificado nesta sessão ou na anterior; `[C]` conhecimento consolidado da literatura, sem reconsulta; `[NV]` não verificado — conferir antes de citar.
7. **Fechamento único:** índice (`README.md`) cruzando RQ1–RQ10 e Produtos 1–8 com os arquivos.

## Estrutura de saída implementada

```
Ana_Model/
├── 00_PLANO_ECONOMIA_TOKENS.md        (este arquivo)
├── README.md                          (índice e mapa RQ/Produtos → arquivos)
├── Revisao_cientifica_nivel_do_mar.html   (Produto 1 genérico — existente)
├── outputs/.../Matrizes_nivel_do_mar.xlsx (Produtos 2–5 genéricos — existente; estendida)
├── 01_Adendo_Bahia_Revisao.md         (Produto 1 regional: contexto físico, dados, implicações)
├── 02_Inventario_Bases_Bahia.md       (Produto 3 regional com URLs e acesso)
├── 03_Cinco_Opcoes_Modelagem_Bahia.md (pedido final: 5 opções + ferramental + Produtos 6 e 7)
└── 04_Referencias_Adicionais.md       (bibliografia APA dos novos itens)
```
