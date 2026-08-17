# -*- coding: utf-8 -*-
"""
HISTÓRICO — a porta por onde os sorteios REAIS entram no software.

POR QUE ARQUIVO E NÃO API
─────────────────────────
A intenção era puxar da Caixa direto. Não dá, e o motivo não é a Caixa: a
política de saída deste ambiente recusa a conexão antes de ela sair daqui
(403 no CONNECT, registrado pelo próprio proxy, para servicebus2.caixa.gov.br e
para os espelhos). Não é intermitência e não adianta insistir — é regra da
máquina onde eu rodo, e contorná-la não é decisão minha.

Então o caminho é o mesmo do `data_inbox` do outro pacote, e é um caminho bom:
ele baixa o arquivo de resultados e larga na pasta `dados/`. O software lê dali.
Isso tem uma vantagem que a API não teria — o dado fica no disco dele, igual
todas as vezes, e duas medições sobre o mesmo arquivo dão o mesmo número.

O QUE EU NÃO CONSIGO GARANTIR DAQUI, E COMO ISTO LIDA COM ISSO
──────────────────────────────────────────────────────────────
Eu não consigo baixar o arquivo da Caixa, logo não consigo conferir o formato
exato dele. Escrevi o leitor para várias formas plausíveis (CSV com Bola1..BolaN,
JSON de API, texto solto), e é possível que a dele seja uma quarta.

Por isso este módulo não tenta adivinhar em silêncio. Ele lê, e devolve um
DIAGNÓSTICO do que entendeu: quantos concursos, quantas dezenas por concurso, de
que valor a que valor, e o primeiro concurso lido por extenso. Se o leitor errou
a coluna, isso aparece na cara — "li 6 dezenas indo de 1 a 2701" denuncia na
hora que ele pegou a coluna do número do concurso junto. O erro que eu temo é o
mudo: ler errado, não reclamar, e produzir estatística linda sobre lixo.

E o portão que vem do outro software: um histórico é conferido contra `regras.py`
no momento em que entra. Se o arquivo diz que saem 6 dezenas e eu declarei 5, ou
se aparece dezena fora do universo, o histórico entra REPROVADO e o medidor se
recusa a medir nele. Regra errada não dá erro — dá probabilidade plausível e
falsa, e é assim que se perde dinheiro achando que se tem número.

O SINTÉTICO É MARCADO A FERRO
─────────────────────────────
Este módulo também gera históricos falsos — preciso deles para provar que o
medidor funciona (um sorteio uniforme onde ele NÃO pode achar efeito, um viciado
de propósito onde ele TEM de achar). Todo histórico assim nasce com
`sintetico=True`, e o medidor recusa gravar veredito vindo de dado inventado.
Sem essa marca, o meu próprio teste poderia escrever "C01 confirmado" na base
dele com número que eu mesmo fabriquei. Seria a pior mentira possível aqui, e
seria de boa-fé — que é como as piores acontecem.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import regras

# nomes que as fontes usam para a mesma coisa. Minúsculas e sem acento na
# comparação, porque "Data do Sorteio" e "data_sorteio" são a mesma coluna.
_CHAVES_DEZENAS = ("dezenas", "listadezenas", "numeros", "números", "bolas",
                   "dezenassorteadasordemsorteio", "resultado")
_CHAVES_CONCURSO = ("concurso", "numero", "número", "numeroconcurso", "id")
_CHAVES_DATA = ("data", "datasorteio", "datadosorteio", "dataapuracao")
_CHAVES_ARRECADACAO = ("arrecadacao", "arrecadacaototal", "valorarrecadado",
                       "arrecadaçãototal")


def _simples(s: Any) -> str:
    """"Data do Sorteio" e "data_sorteio" viram a mesma chave."""
    t = str(s).strip().lower()
    for de, para in (("á", "a"), ("â", "a"), ("ã", "a"), ("é", "e"), ("ê", "e"),
                     ("í", "i"), ("ó", "o"), ("ô", "o"), ("õ", "o"), ("ú", "u"),
                     ("ç", "c")):
        t = t.replace(de, para)
    return re.sub(r"[^a-z0-9]", "", t)


def _inteiro(v: Any) -> Optional[int]:
    """"07" → 7; "1.234" → 1234; "" → None. Nunca levanta exceção."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    t = str(v).strip().replace(".", "").replace(" ", "")
    if not t or not re.fullmatch(r"-?\d+", t):
        return None
    return int(t)


def _dinheiro(v: Any) -> Optional[float]:
    """"R$ 1.234,56" → 1234.56. O formato brasileiro, que é o que ele vai ter."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    t = re.sub(r"[^\d,.-]", "", str(v))
    if not t:
        return None
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


class Historico:
    """Os sorteios de UMA loteria, com a procedência colada neles.

    A procedência não é enfeite de auditoria: é o que separa "medi nos dados
    dele" de "medi em algo que apareceu na pasta". Quando o veredito de um item
    da base for gravado, ele carrega de qual arquivo e de qual soma de
    verificação saiu — e se ele trocar o arquivo, a soma muda e a medição
    anterior deixa de valer para o novo.
    """

    def __init__(self, chave_jogo: str, concursos: Sequence[Dict[str, Any]],
                 fonte: str, arquivo: str = "", sha256: str = "",
                 sintetico: bool = False, nota: str = ""):
        self.chave_jogo = chave_jogo
        self.concursos = [dict(c) for c in concursos]
        self.fonte = fonte
        self.arquivo = arquivo
        self.sha256 = sha256
        self.sintetico = bool(sintetico)
        self.nota = nota
        self.conferido = False
        self.problemas: List[str] = []
        self._conferir()

    # ── o portão contra regras.py ─────────────────────────────────────────
    def _conferir(self) -> None:
        r = regras.conferir_com_api(self.chave_jogo, self.sorteios())
        self.conferido = bool(r.get("ok"))
        self.problemas = list(r.get("problemas") or [])
        if not self.conferido and not self.problemas:
            self.problemas = [str(r.get("nota") or "não conferido")]

    def sorteios(self) -> List[List[int]]:
        return [list(c.get("dezenas") or []) for c in self.concursos
                if c.get("dezenas")]

    def __len__(self) -> int:
        return len(self.concursos)

    def tem_ganhadores(self) -> bool:
        """Dá para medir a partilha (P01) neste arquivo?

        Só dá se o arquivo trouxer ganhadores por faixa. O CSV completo da Caixa
        traz; um arquivo só com as dezenas, não. Não é defeito do arquivo — é
        limite dele, e P01 fica "sem base" em vez de ser medida no que não há.
        """
        return any(c.get("ganhadores") for c in self.concursos)

    def pronto_para_medir(self) -> Tuple[bool, str]:
        """Pode-se medir item da base neste histórico?"""
        if not self.concursos:
            return False, "histórico vazio"
        if not self.fonte.strip():
            return False, ("histórico sem procedência declarada — não meço em "
                           "dado que não sei de onde veio")
        if not self.conferido:
            return False, ("as regras de " + self.chave_jogo + " não batem com "
                           "este arquivo: " + "; ".join(self.problemas)
                           + ". Medir assim daria número plausível e falso.")
        return True, ""

    # ── o que eu entendi do arquivo dele ─────────────────────────────────
    def diagnostico(self) -> List[str]:
        """O que o leitor entendeu, em português, para ele conferir de olho.

        Esta é a peça central do arquivo. Como eu não pude ver o formato real, a
        defesa contra ler errado não é o meu cuidado — é ele bater o olho aqui e
        ver se o que eu li é o que está no arquivo dele.
        """
        j = regras.jogo(self.chave_jogo)
        nome = j.nome if j else self.chave_jogo
        L = [f"[Histórico] {nome}: {len(self.concursos)} concursos lidos"]
        if self.sintetico:
            L.append("[Histórico] ATENÇÃO: este histórico é SINTÉTICO — eu o "
                     "inventei para testar o medidor. Não vale para decidir "
                     "nada, e nenhum veredito dele entra na base.")
        L.append(f"[Histórico]   procedência: {self.fonte}")
        if self.arquivo:
            L.append(f"[Histórico]   arquivo: {self.arquivo}")
        if self.sha256:
            L.append(f"[Histórico]   soma de verificação: {self.sha256[:16]}…")
        sorteios = self.sorteios()
        if sorteios:
            tamanhos = sorted({len(s) for s in sorteios})
            todos = [x for s in sorteios for x in s]
            L.append(f"[Histórico]   dezenas por concurso: "
                     f"{tamanhos if len(tamanhos) > 1 else tamanhos[0]}"
                     + ("  ← devia ser um número só" if len(tamanhos) > 1 else ""))
            L.append(f"[Histórico]   dezenas vão de {min(todos)} a {max(todos)}")
            primeiro = self.concursos[0]
            L.append(f"[Histórico]   primeiro lido: concurso "
                     f"{primeiro.get('concurso')} de {primeiro.get('data')} — "
                     f"{primeiro.get('dezenas')}")
            ultimo = self.concursos[-1]
            L.append(f"[Histórico]   último lido: concurso "
                     f"{ultimo.get('concurso')} de {ultimo.get('data')} — "
                     f"{ultimo.get('dezenas')}")
        L.append(f"[Histórico]   ganhadores por faixa: "
                 + ("sim — dá para medir a partilha (P01)"
                    if self.tem_ganhadores() else
                    "não vieram no arquivo — P01 fica sem base"))
        if self.conferido:
            L.append("[Histórico]   ✓ confere com as regras declaradas em "
                     "regras.py")
        else:
            L.append("[Histórico]   ✗ NÃO confere com regras.py — o medidor vai "
                     "se recusar a medir:")
            for p in self.problemas:
                L.append(f"[Histórico]       {p}")
            L.append("[Histórico]   (ou o leitor pegou a coluna errada, ou a "
                     "regra que escrevi de memória está errada. As duas se "
                     "resolvem olhando o arquivo — nenhuma se resolve medindo.)")
        return L


# ═════════════════════════════════════════════════════════ leitura de arquivo
def de_arquivo(caminho, chave_jogo: str,
               fonte: str = "") -> Tuple[Optional[Historico], List[str]]:
    """Lê o arquivo de resultados que ele baixou. Devolve (histórico, avisos).

    Tenta JSON, depois tabela (CSV/TSV/;), depois texto solto — nessa ordem,
    porque é da mais estruturada para a menos, e a menos estruturada aceita
    quase tudo (inclusive lixo, e é por isso que ela é a última).
    """
    avisos: List[str] = []
    p = Path(caminho)
    if not p.exists():
        return None, [f"não achei o arquivo: {p}"]
    bruto = p.read_bytes()
    sha = hashlib.sha256(bruto).hexdigest()
    texto = None
    for cod in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            texto = bruto.decode(cod)
            if cod != "utf-8-sig":
                avisos.append(f"arquivo lido como {cod}")
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        return None, [f"não consegui decodificar {p.name} como texto"]

    concursos: List[Dict[str, Any]] = []
    for leitor, rotulo in ((_de_json, "JSON"), (_de_tabela, "tabela"),
                           (_de_texto, "texto solto")):
        try:
            concursos = leitor(texto, chave_jogo)
        except Exception as e:                     # leitor errado, próximo
            avisos.append(f"leitor {rotulo} não serviu: {type(e).__name__}")
            concursos = []
        if concursos:
            avisos.append(f"lido como {rotulo}")
            break
    if not concursos:
        return None, avisos + [
            f"não consegui extrair sorteio nenhum de {p.name}. Se o formato for "
            f"outro, me mostre as primeiras linhas do arquivo que eu ensino o "
            f"leitor — é melhor do que eu adivinhar."]

    concursos.sort(key=lambda c: (c.get("concurso") is None,
                                  c.get("concurso") or 0))
    h = Historico(chave_jogo, concursos,
                  fonte=fonte or f"arquivo baixado por ele: {p.name}",
                  arquivo=str(p), sha256=sha)
    return h, avisos


def _de_json(texto: str, chave_jogo: str) -> List[Dict[str, Any]]:
    dados = json.loads(texto)
    if isinstance(dados, dict):
        # {"concursos": [...]} ou {"1": {...}, "2": {...}}
        for v in dados.values():
            if isinstance(v, list) and v:
                dados = v
                break
        else:
            dados = [v for v in dados.values() if isinstance(v, dict)]
    if not isinstance(dados, list):
        return []
    saida: List[Dict[str, Any]] = []
    for reg in dados:
        if not isinstance(reg, dict):
            continue
        campos = {_simples(k): v for k, v in reg.items()}
        dezenas: List[int] = []
        for ch in _CHAVES_DEZENAS:
            v = campos.get(ch)
            if isinstance(v, (list, tuple)):
                dezenas = [x for x in (_inteiro(i) for i in v) if x is not None]
                break
            if isinstance(v, str) and v:
                dezenas = [x for x in (_inteiro(i)
                                       for i in re.split(r"[^\d]+", v))
                           if x is not None]
                break
        if not dezenas:
            continue
        saida.append({
            "concurso": next((_inteiro(campos.get(c)) for c in _CHAVES_CONCURSO
                              if campos.get(c) is not None), None),
            "data": next((str(campos.get(c)) for c in _CHAVES_DATA
                          if campos.get(c)), ""),
            "dezenas": sorted(dezenas),
            "ganhadores": _ganhadores_de_json(campos),
            "arrecadacao": next((_dinheiro(campos.get(c))
                                 for c in _CHAVES_ARRECADACAO
                                 if campos.get(c) is not None), None),
        })
    return saida


def _ganhadores_de_json(campos: Dict[str, Any]) -> Dict[int, int]:
    """Ganhadores por faixa, da lista de premiações das APIs conhecidas.

    O formato comum é uma lista de {"descricao": "6 acertos", "ganhadores": 0}.
    A faixa sai do primeiro número da descrição.
    """
    saida: Dict[int, int] = {}
    for ch in ("premiacoes", "listarateiopremio", "rateiopremio", "premiacao"):
        lista = campos.get(ch)
        if not isinstance(lista, (list, tuple)):
            continue
        for it in lista:
            if not isinstance(it, dict):
                continue
            c = {_simples(k): v for k, v in it.items()}
            desc = str(c.get("descricao") or c.get("faixa") or "")
            m = re.search(r"\d+", desc)
            faixa = _inteiro(m.group()) if m else _inteiro(c.get("faixa"))
            g = _inteiro(c.get("ganhadores") or c.get("numeroganhadores")
                         or c.get("quantidadeganhadores"))
            if faixa is not None and g is not None:
                saida[faixa] = g
        if saida:
            break
    return saida


def _de_tabela(texto: str, chave_jogo: str) -> List[Dict[str, Any]]:
    """CSV/TSV com cabeçalho — o formato do arquivo de resultados da Caixa.

    As dezenas saem das colunas cujo nome começa com "bola"/"dezena"; se não
    houver coluna com esse nome, saem das colunas numéricas que caem dentro do
    universo do jogo e são exatamente `sorteadas` por linha. O segundo caminho é
    o que salva quando o cabeçalho vem em outro idioma ou abreviado.
    """
    linhas = [l for l in texto.splitlines() if l.strip()]
    if len(linhas) < 2:
        return []
    sep = max((";", "\t", ",", "|"), key=lambda s: linhas[0].count(s))
    if linhas[0].count(sep) < 2:
        return []
    cab = [c.strip().strip('"') for c in linhas[0].split(sep)]
    chaves = [_simples(c) for c in cab]
    j = regras.jogo(chave_jogo)
    if not j:
        return []

    col_dezenas = [i for i, c in enumerate(chaves)
                   if re.fullmatch(r"(bola|dezena|n|num|numero)\d*", c)]
    col_ganh = {}
    for i, c in enumerate(chaves):
        m = re.fullmatch(r"ganhadores?(\d+)(acertos?|pontos?|numeros?)?", c)
        if m:
            col_ganh[i] = int(m.group(1))
    col_arrec = next((i for i, c in enumerate(chaves)
                      if c in _CHAVES_ARRECADACAO), None)
    col_conc = next((i for i, c in enumerate(chaves)
                     if c in _CHAVES_CONCURSO), None)
    col_data = next((i for i, c in enumerate(chaves)
                     if c in _CHAVES_DATA), None)

    universo = set(j.dezenas())
    saida: List[Dict[str, Any]] = []
    for linha in linhas[1:]:
        campos = [c.strip().strip('"') for c in linha.split(sep)]
        if len(campos) < 2:
            continue
        if col_dezenas:
            dez = [x for x in (_inteiro(campos[i]) for i in col_dezenas
                               if i < len(campos)) if x is not None]
        else:
            # sem cabeçalho reconhecível: as colunas que cabem no universo,
            # pulando a do concurso (que costuma ser a primeira e cresce)
            dez = []
            for i, v in enumerate(campos):
                if i == col_conc:
                    continue
                x = _inteiro(v)
                if x is not None and x in universo:
                    dez.append(x)
            if len(dez) != j.sorteadas:
                dez = dez[:j.sorteadas] if len(dez) > j.sorteadas else []
        if len(dez) != j.sorteadas:
            continue
        ganhadores = {}
        for i, faixa in col_ganh.items():
            g = _inteiro(campos[i]) if i < len(campos) else None
            if g is not None:
                ganhadores[faixa] = g
        saida.append({
            "concurso": (_inteiro(campos[col_conc])
                         if col_conc is not None and col_conc < len(campos)
                         else None),
            "data": (campos[col_data]
                     if col_data is not None and col_data < len(campos) else ""),
            "dezenas": sorted(dez),
            "ganhadores": ganhadores,
            "arrecadacao": (_dinheiro(campos[col_arrec])
                            if col_arrec is not None and col_arrec < len(campos)
                            else None),
        })
    return saida


def _de_texto(texto: str, chave_jogo: str) -> List[Dict[str, Any]]:
    """Uma linha por concurso, só os números. O último recurso.

    Aceita a linha só quando ela tem EXATAMENTE o número de dezenas do jogo,
    todas dentro do universo. Linha que não obedece é pulada em silêncio — aqui
    o silêncio é certo, porque cabeçalho e rodapé caem nesse caso.
    """
    j = regras.jogo(chave_jogo)
    if not j:
        return []
    universo = set(j.dezenas())
    saida: List[Dict[str, Any]] = []
    for n, linha in enumerate(texto.splitlines(), 1):
        nums = [x for x in (_inteiro(t) for t in re.split(r"[^\d]+", linha))
                if x is not None]
        dez = [x for x in nums if x in universo]
        if len(nums) == j.sorteadas and len(dez) == j.sorteadas:
            saida.append({"concurso": n, "data": "", "dezenas": sorted(dez),
                          "ganhadores": {}, "arrecadacao": None})
        elif len(nums) == j.sorteadas + 1 and len(dez) >= j.sorteadas:
            # provável "concurso  d1 d2 ..." — o primeiro é o número do concurso
            resto = [x for x in nums[1:] if x in universo]
            if len(resto) == j.sorteadas:
                saida.append({"concurso": nums[0], "data": "",
                              "dezenas": sorted(resto),
                              "ganhadores": {}, "arrecadacao": None})
    return saida


# ═══════════════════════════════════════ históricos que eu invento, marcados
def sintetico_uniforme(chave_jogo: str, n: int,
                       semente: int = 20260817) -> Historico:
    """Sorteios honestos, sem padrão nenhum. O controle negativo do medidor.

    Serve para uma pergunta que o outro software me ensinou a fazer: o meu
    medidor acha coisa onde não há? Se ele "confirmar" atrasadas aqui, ele está
    quebrado, e todo veredito que ele der nos dados dele é lixo.
    """
    j = regras.jogo(chave_jogo)
    if not j:
        raise ValueError(f"jogo desconhecido: {chave_jogo}")
    rnd = random.Random(semente)
    dezenas = j.dezenas()
    concursos = [{"concurso": i, "data": "", "ganhadores": {},
                  "arrecadacao": None,
                  "dezenas": sorted(rnd.sample(dezenas, j.sorteadas))}
                 for i in range(1, n + 1)]
    return Historico(chave_jogo, concursos,
                     fonte="INVENTADO por mim: sorteio uniforme, para provar "
                           "que o medidor não acha efeito onde não há",
                     sintetico=True)


def sintetico_viciado(chave_jogo: str, n: int, forca: float = 3.0,
                      semente: int = 20260817) -> Historico:
    """Sorteios em que as ATRASADAS realmente saem mais. O controle positivo.

    Um medidor que só sabe dizer "não se sustentou" não mede nada — ele acerta
    em sorteio honesto por acidente, dizendo sempre a mesma coisa. Este
    histórico tem o efeito de C01 embutido de propósito, e o medidor TEM de
    achá-lo. Se ele não achar, ele é cego, e o "não se sustentou" dele nos dados
    dele não vale nada.

    `forca` é o peso extra que uma dezena ganha por concurso de atraso.
    """
    j = regras.jogo(chave_jogo)
    if not j:
        raise ValueError(f"jogo desconhecido: {chave_jogo}")
    rnd = random.Random(semente)
    dezenas = j.dezenas()
    atraso = {d: 0 for d in dezenas}
    concursos = []
    for i in range(1, n + 1):
        pesos = {d: 1.0 + forca * atraso[d] for d in dezenas}
        sorteio: List[int] = []
        restantes = dict(pesos)
        for _ in range(j.sorteadas):
            total = sum(restantes.values())
            alvo = rnd.random() * total
            ac = 0.0
            for d, w in restantes.items():
                ac += w
                if ac >= alvo:
                    sorteio.append(d)
                    del restantes[d]
                    break
        for d in dezenas:
            atraso[d] = 0 if d in sorteio else atraso[d] + 1
        concursos.append({"concurso": i, "data": "", "ganhadores": {},
                          "arrecadacao": None, "dezenas": sorted(sorteio)})
    return Historico(chave_jogo, concursos,
                     fonte=f"INVENTADO por mim: atrasadas viciadas de propósito "
                           f"(força {forca}), para provar que o medidor enxerga "
                           f"efeito quando ele existe",
                     sintetico=True)
