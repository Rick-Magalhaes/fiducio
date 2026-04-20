import re
import logging
import unicodedata

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

ESCRITORIOS = [
    ("machado meyer",      "MM"),
    ("sacramone",          "SOB"),
    ("costa tavares",      "CTP"),
    ("pinheiro guimaraes", "PGA"),
    ("pinheiro guimar",    "PGA"),
    ("felsberg",           "Fel"),
    ("journey capital",    "JNEY"),
    ("virtus br",          "VIR"),
    ("br partners",        "BR"),
    ("g5 partners",        "G5"),
    ("sob",                "SOB"),
    ("g5",                 "G5"),
]

NUM_DELIBERACOES = 6

# =============================================================================
# UTILITÁRIOS
# =============================================================================

def norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().strip()

# =============================================================================
# CLASSIFICAÇÃO DE VOTOS
# =============================================================================

def sigla_escritorio(texto: str) -> str | None:
    t = norm(texto)
    for nome, sigla in ESCRITORIOS:
        if nome in t:
            return sigla
    return None

def classificar_opcao_linha(texto_linha: str, num_delib: int) -> str | None:
    t = norm(texto_linha)
    if num_delib in (2, 3):
        sigla = sigla_escritorio(t)
        if sigla:
            return sigla
        if "nao aprovar" in t or "reprova" in t or "rejeita" in t:
            return "R"
        if "abstem" in t or "abstencao" in t or "abster" in t or "se abstem" in t or "se abster" in t:
            return "AB"
        if "aprova" in t or "aprovar" in t:
            return "A"
        return None

    if "nao aprovar" in t or "reprova" in t or "rejeita" in t:
        return "R"
    if "abstem" in t or "abstencao" in t or "abster" in t or "se abstem" in t or "se abster" in t:
        return "AB"
    if "aprova" in t or "aprovar" in t:
        return "A"
    return None

# =============================================================================
# REGEX
# =============================================================================

CABECALHO_A_RE = re.compile(
    r"^\s*\(\s*([1-6])\s*\)\s+\S",
    re.IGNORECASE,
)

CABECALHO_B_RE = re.compile(
    r"^\s*([1-6])\.\s+(?:Quanto|Em\s+rela)",
    re.IGNORECASE,
)

CABECALHO_EMBARALHADO_RE = re.compile(
    r"^\s*\({2,}\s*([1-6])\s*\){2,}",
)

OPCAO_MARCADA_RE = re.compile(
    r"^\s*\(\s*[xX]\s*\)\s*(.*)",
)

# =============================================================================
# EXTRAÇÃO LINEAR
# =============================================================================

def extrair_votos_linear_com_lookahead(texto: str):
    resultados = {}
    delib_atual = None
    delib_presente = set()
    aguardando_conteudo = False

    linhas = [l.strip() for l in texto.splitlines()]

    for linha_strip in linhas:
        if not linha_strip:
            continue

        m_emb = CABECALHO_EMBARALHADO_RE.match(linha_strip)
        if m_emb:
            delib_atual = int(m_emb.group(1))
            delib_presente.add(delib_atual)
            aguardando_conteudo = False
            continue

        m_a = CABECALHO_A_RE.match(linha_strip)
        if m_a:
            delib_atual = int(m_a.group(1))
            delib_presente.add(delib_atual)
            aguardando_conteudo = False
            continue

        m_b = CABECALHO_B_RE.match(linha_strip)
        if m_b:
            delib_atual = int(m_b.group(1))
            delib_presente.add(delib_atual)
            aguardando_conteudo = False
            continue

        if aguardando_conteudo and delib_atual is not None:
            aguardando_conteudo = False
            if delib_atual not in resultados:
                sigla = classificar_opcao_linha(linha_strip, delib_atual)
                if sigla:
                    resultados[delib_atual] = sigla
            continue

        m_opc = OPCAO_MARCADA_RE.match(linha_strip)
        if m_opc and delib_atual is not None and delib_atual not in resultados:
            conteudo = m_opc.group(1).strip()

            if conteudo:
                sigla = classificar_opcao_linha(conteudo, delib_atual)
                if sigla:
                    resultados[delib_atual] = sigla
                else:
                    aguardando_conteudo = True
            else:
                aguardando_conteudo = True

    return resultados, delib_presente

# =============================================================================
# ESPACIAL
# =============================================================================

OPCAO_MARCADA_WORD_RE = re.compile(r"^\s*\(\s*[xX]", re.IGNORECASE)

def reconstruir_linhas_pagina(pagina):
    palavras = pagina.extract_words(keep_blank_chars=False) or []
    if not palavras:
        return []

    grupos = []
    for p in sorted(palavras, key=lambda w: w["top"]):
        colocado = False
        for grupo in grupos:
            if abs(p["top"] - grupo[0]["top"]) <= 5:
                grupo.append(p)
                colocado = True
                break
        if not colocado:
            grupos.append([p])

    linhas = []
    for grupo in grupos:
        grupo.sort(key=lambda w: w["x0"])
        texto = " ".join(w["text"] for w in grupo)
        linhas.append({"top": grupo[0]["top"], "text": texto})

    return sorted(linhas, key=lambda l: l["top"])

def extrair_votos_espacial(pdf):
    todas_linhas = []
    offset = 0.0

    for pagina in pdf.pages:
        linhas = reconstruir_linhas_pagina(pagina)
        for l in linhas:
            todas_linhas.append({"top": l["top"] + offset, "text": l["text"]})
        offset += float(pagina.height or 842)

    cabecalhos = []
    marcadas = []
    vistos_cab = set()

    for l in todas_linhas:
        texto = l["text"]

        m_emb = CABECALHO_EMBARALHADO_RE.match(texto)
        if m_emb:
            num = int(m_emb.group(1))
            if num not in vistos_cab:
                cabecalhos.append({"top": l["top"], "num": num})
                vistos_cab.add(num)
            continue

        m_cab_a = CABECALHO_A_RE.match(texto)
        m_cab_b = CABECALHO_B_RE.match(texto)
        m_num = m_cab_a or m_cab_b

        if m_num:
            num = int(m_num.group(1))
            if num not in vistos_cab:
                cabecalhos.append({"top": l["top"], "num": num})
                vistos_cab.add(num)
            continue

        if OPCAO_MARCADA_WORD_RE.match(texto):
            marcadas.append({"top": l["top"], "text": texto})

    resultados = {}
    for m in marcadas:
        anteriores = [c for c in cabecalhos if c["top"] <= m["top"] + 10]
        if not anteriores:
            continue

        cab = max(anteriores, key=lambda c: c["top"])
        num = cab["num"]

        if num in resultados:
            continue

        conteudo = re.sub(r"^\s*\(\s*[xX]\s*\)\s*", "", m["text"]).strip()
        sigla = classificar_opcao_linha(conteudo or m["text"], num)

        if sigla:
            resultados[num] = sigla

    return resultados, vistos_cab

# =============================================================================
# DETECÇÃO
# =============================================================================

def detectar_deliberacoes_presentes(texto: str):
    presentes = set()

    for num in range(1, NUM_DELIBERACOES + 1):
        if (
            re.search(rf"\(\s*{num}\s*\)", texto)
            or re.search(rf"\({{2,}}\s*{num}\s*\){{2,}}", texto)
            or re.search(rf"^\s*{num}\.\s+(?:Quanto|Em\s+rela)", texto, re.MULTILINE | re.IGNORECASE)
        ):
            presentes.add(num)

    return presentes

# =============================================================================
# EXTRAÇÃO DE WIDGETS (form fields)
# =============================================================================

def extrair_votos_widgets(pdf) -> dict[int, str]:
    """
    Lê form fields (widgets) do PDF — usados quando o x está em
    camada de anotação e não é extraído pelo fluxo de texto normal.
    """
    resultados: dict[int, str] = {}

    try:
        for page in pdf.pages:
            widgets = page.widgets
            if not widgets:
                continue
            for w in widgets:
                valor = w.get("value") or w.get("V") or ""
                if not valor or str(valor).strip() in ("", "Off", "N"):
                    continue

                # tenta encontrar o texto ao redor do widget para classificar
                x0 = w.get("x0", 0)
                top = w.get("top", 0)

                # busca texto próximo na mesma página
                palavras = page.extract_words() or []
                vizinhos = [
                    p["text"] for p in palavras
                    if abs(p["top"] - top) <= 15 and p["x0"] > x0
                ]
                texto_vizinho = " ".join(vizinhos[:8])

                # tenta identificar deliberação pela posição vertical
                # procura cabeçalhos na página
                texto_pagina = page.extract_text() or ""
                linhas = texto_pagina.splitlines()

                delib_atual = None
                for linha in linhas:
                    m_b = CABECALHO_B_RE.match(linha.strip())
                    if m_b:
                        delib_atual = int(m_b.group(1))

                if delib_atual and texto_vizinho:
                    sigla = classificar_opcao_linha(texto_vizinho, delib_atual)
                    if sigla and delib_atual not in resultados:
                        resultados[delib_atual] = sigla
    except Exception as e:
        logging.warning("Erro ao ler widgets: %s", e)

    return resultados

# =============================================================================
# FINAL
# =============================================================================

def extrair_votos(pdf, texto: str | None = None):
    if texto is None:
        texto = ""
        for page in pdf.pages:
            texto += (page.extract_text() or "") + "\n"

    presentes = detectar_deliberacoes_presentes(texto)
    resultados_linear, _  = extrair_votos_linear_com_lookahead(texto)
    resultados_espacial, _ = extrair_votos_espacial(pdf)
    resultados_widgets     = extrair_votos_widgets(pdf)

    resultados_final = {}
    for num in range(1, NUM_DELIBERACOES + 1):
        if num not in presentes:
            resultados_final[num] = "NV"
        elif num in resultados_linear:
            resultados_final[num] = resultados_linear[num]
        elif num in resultados_espacial:
            resultados_final[num] = resultados_espacial[num]
        elif num in resultados_widgets:
            resultados_final[num] = resultados_widgets[num]
        else:
            resultados_final[num] = "NV"

    return [resultados_final[i] for i in range(1, NUM_DELIBERACOES + 1)]