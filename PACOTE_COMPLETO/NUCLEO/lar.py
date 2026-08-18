# -*- coding: utf-8 -*-
"""
LAR — a memória mora nos Documentos, não na pasta do programa.

O QUE ELE PEDIU
───────────────
    "memória inteligente salva em c: documentos, pois independente de
     atualizações a memória sempre será resgatada"

E ELE ESTÁ APONTANDO UM DEFEITO REAL, NÃO PEDINDO UM CAPRICHO
─────────────────────────────────────────────────────────────
Hoje a memória grava ao lado do programa:

    ROOT = Path(__file__).resolve().parent          # a pasta do pacote
    self.path = ROOT / f"memoria_{jogo}.json"

Cada versão que eu mando é uma pasta nova. `PACOTE_COMPLETO_v124`,
`PACOTE_COMPLETO_v125`. Ele descompacta a nova, roda a nova, e a memória fica
para trás na pasta velha: as decisões avaliadas, o placar, os pesos aprendidos
por eixo, o que cada teoria rendeu. Tudo aquilo que só existe depois de horas
rodando -- e que é justamente o que a IA precisa para aprender qualquer coisa --
zerava a cada entrega minha.

Pior: o autoexame precisa de 12 janelas fechadas por teoria antes de julgar
qualquer uma. Se a memória zera a cada versão, ele nunca chega às 12, e a
autocrítica dele fica presa em "ainda não sei dizer" para sempre. O aprendizado
não estava lento; estava sendo apagado por mim.

ONDE FICA, E POR QUE ASSIM
──────────────────────────
Uma pasta nos Documentos do usuário, fora do pacote:

    C:\\Users\\<ele>\\Documents\\memorias casino

O nome é o que ele pediu depois, por mensagem: "coloque o software para
salvar toda sua memoria de aprendizado em c:/documentos com o nome da pasta
memorias casino". Antes disso a pasta se chamava `PACOTE_COMPLETO_MEMORIA` --
ver `NOMES_ANTIGOS` abaixo para a migração que traz o que já acumulou lá para
o nome novo, sem duplicar e sem perder nada.

Documentos é o lugar certo por três motivos: sobrevive a trocar a pasta do
programa, não precisa de permissão de administrador (ao contrário de
`C:\\PACOTE_COMPLETO`, que no Windows moderno cai em virtualização de escrita), e
ele sabe onde é -- pode copiar, levar para outra máquina, ou apagar se quiser
começar do zero.

O DETALHE DO ONEDRIVE, QUE QUEBRARIA ISTO EM SILÊNCIO
─────────────────────────────────────────────────────
No Windows com OneDrive ligado -- que é o padrão de fábrica há anos -- a pasta
Documentos costuma estar redirecionada para `%USERPROFILE%\\OneDrive\\Documentos`,
e `~/Documents` pode nem existir. Se eu simplesmente escrevesse em
`Path.home() / "Documents"`, criaria uma pasta paralela vazia ao lado da real, e
ele juraria que a memória não está salvando. Então procuro na ordem, incluindo o
nome em português, e uso a primeira que EXISTE antes de criar qualquer coisa.

O QUE ACONTECE SE NÃO DER
─────────────────────────
Pasta sem permissão de escrita, disco cheio, perfil de rede indisponível: cai de
volta para a pasta do programa e DIZ o motivo. O que não pode acontecer é o
software achar que salvou e não ter salvado -- perder memória em silêncio é
exatamente o problema que este arquivo existe para resolver.

E A MUDANÇA NÃO PODE COMER A MEMÓRIA QUE JÁ EXISTE
──────────────────────────────────────────────────
Ele já tem horas rodando na pasta antiga. Na primeira vez que o novo caminho é
usado, o que estiver na pasta do programa é COPIADO para o lar -- copiado, não
movido, para que uma falha no meio não perca as duas cópias. E o arquivo do lar
nunca é sobrescrito por um da pasta do programa: se os dois existem, o lar é a
verdade, porque é o que vem acumulando entre versões.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

RAIZ_PACOTE = Path(__file__).resolve().parent.parent

NOME_DA_PASTA = "memorias casino"

# O nome anterior, para trazer o que já rodou lá antes dele pedir a troca.
# Ele já tinha "horas rodando" nessa pasta quando pediu o nome novo -- se eu
# só trocasse `NOME_DA_PASTA`, o software abriria uma pasta NOVA e vazia, e
# tudo que a Academia aprendeu (o autoexame, os pesos por eixo, o placar)
# ficaria para trás, órfão, do mesmo jeito que a pasta do programa ficava
# órfã antes deste arquivo existir. A mesma doença, com outro nome de pasta.
NOMES_ANTIGOS = ("PACOTE_COMPLETO_MEMORIA",)

# o que é memória e portanto tem de sobreviver às atualizações. Nomes exatos e
# prefixos -- `memoria_lightning.json`, `memoria_crazy_time_a.json` etc.
PREFIXOS = ("memoria_", "forca_dos_eixos", "academia_", "autoexame",
            "automelhoria", "pesquisa_", "biblioteca_", "descobertas",
            "placar", "publico_")

_motivo: List[str] = []          # o que houve na hora de escolher o lar
_lar: Optional[Path] = None
_migrado = False


def _candidatas() -> List[Path]:
    """Onde os Documentos podem estar, na ordem em que devo procurar.

    A ordem importa: primeiro os caminhos que o OneDrive cria, depois os
    clássicos, e em cada caso o nome em português junto do inglês. Uma máquina em
    português com OneDrive tem `OneDrive\\Documentos` e pode não ter `Documents`.
    """
    casa = Path.home()
    saida: List[Path] = []
    # o OneDrive avisa por variável de ambiente onde ele mora
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        v = os.environ.get(var)
        if v:
            for nome in ("Documentos", "Documents"):
                saida.append(Path(v) / nome)
    for base in (casa / "OneDrive", casa):
        for nome in ("Documentos", "Documents"):
            saida.append(base / nome)
    # último recurso: a própria pasta do usuário
    saida.append(casa)
    vistos, unicas = set(), []
    for p in saida:
        s = str(p)
        if s not in vistos:
            vistos.add(s)
            unicas.append(p)
    return unicas


def _escrevivel(pasta: Path) -> bool:
    """A pasta aceita escrita AGORA? Testado escrevendo, não deduzido.

    `os.access` mente em rede e em pastas sincronizadas. A única forma honesta de
    saber se dá para gravar é gravar.
    """
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        alvo = pasta / ".lar_teste"
        alvo.write_text("ok", encoding="utf-8")
        alvo.unlink()
        return True
    except Exception:
        return False


def _escolher() -> Tuple[Path, List[str]]:
    """Decide o lar e devolve junto a explicação da escolha."""
    notas: List[str] = []
    forcado = os.environ.get("PACOTE_MEMORIA_DIR")
    if forcado:
        p = Path(forcado)
        if _escrevivel(p):
            notas.append(f"lar forçado por PACOTE_MEMORIA_DIR: {p}")
            return p, notas
        notas.append(f"PACOTE_MEMORIA_DIR={forcado} não aceita escrita — ignorado")

    for docs in _candidatas():
        # só considero uma pasta de Documentos que EXISTE; criar `~/Documents`
        # numa máquina onde o OneDrive redirecionou seria criar uma pasta
        # paralela vazia, e ele acharia que a memória não salva
        if not docs.is_dir():
            continue
        alvo = docs / NOME_DA_PASTA
        if _escrevivel(alvo):
            notas.append(f"memória nos Documentos: {alvo}")
            return alvo, notas
        notas.append(f"{alvo} não aceita escrita — tentando o próximo")

    # nenhuma serviu: a pasta do programa, dizendo por quê
    notas.append("nenhuma pasta de Documentos aceitou escrita — a memória fica na "
                 "pasta do programa e SERÁ PERDIDA na próxima versão")
    return RAIZ_PACOTE, notas


def lar() -> Path:
    """A pasta onde a memória mora. Decidida uma vez por execução."""
    global _lar
    if _lar is None:
        _lar, notas = _escolher()
        _motivo.extend(notas)
        _migrar()
    return _lar


def motivo() -> List[str]:
    """Como o lar foi escolhido, para ir ao log. Ele precisa poder conferir."""
    lar()
    return list(_motivo)


def esquecer() -> None:
    """Faz o lar ser decidido de novo na próxima chamada.

    Serve a dois casos reais, além do teste: ele mover a pasta de memória para
    outro lugar e apontar `PACOTE_MEMORIA_DIR` para lá, e o perfil de rede ter
    subido depois do programa (aí a primeira tentativa falhou e a segunda dá).
    Sem isto a decisão da primeira chamada valeria até fechar o software.
    """
    global _lar, _migrado
    _lar = None
    _migrado = False
    _motivo.clear()


def _migrar() -> None:
    """Traz para o lar o que já existe na pasta do programa E na pasta antiga.

    COPIA, não move: se der erro no meio, as duas cópias continuam de pé. E não
    sobrescreve o que já está no lar -- entre a memória que vem acumulando e uma
    que veio dentro do zip (ou de um nome de pasta anterior), a que acumulou é
    a verdade.
    """
    global _migrado
    if _migrado or _lar is None or _lar == RAIZ_PACOTE:
        # se o lar É a pasta do programa, não há nada para trazer
        _migrado = True
        return
    _migrado = True
    trazidos = 0
    origens = [RAIZ_PACOTE, RAIZ_PACOTE / "Logs"]

    # A PASTA COM O NOME ANTIGO — ele pediu para trocar o nome DEPOIS de já
    # ter horas de memória acumuladas em `PACOTE_COMPLETO_MEMORIA`. Sem isto,
    # trocar `NOME_DA_PASTA` abriria uma pasta nova e vazia, e o aprendizado
    # ficaria órfão -- exatamente o problema que este arquivo existe para
    # resolver, só que com um nome de pasta no lugar de uma versão do zip.
    #
    # Procura em TODOS os candidatos de Documentos, não só onde o lar atual
    # caiu: se o OneDrive mudou de estado entre uma execução e outra, a pasta
    # antiga pode estar num candidato que hoje não é mais o escolhido.
    for docs in _candidatas():
        if not docs.is_dir():
            continue
        for nome_antigo in NOMES_ANTIGOS:
            antiga = docs / nome_antigo
            if antiga.is_dir() and antiga != _lar:
                origens.append(antiga)

    for origem in origens:
        if not origem.is_dir():
            continue
        for arq in origem.glob("*.json"):
            if not any(arq.name.startswith(p) for p in PREFIXOS):
                continue
            destino = _lar / arq.name
            if destino.exists():
                continue                    # o lar manda
            try:
                shutil.copy2(arq, destino)
                trazidos += 1
            except Exception:
                pass
    if trazidos:
        _motivo.append(f"trouxe {trazidos} arquivo(s) de memória de local(is) "
                       f"anterior(es) para o lar (copiados, os originais "
                       f"ficaram)")


def arquivo(nome: str) -> Path:
    """O caminho de um arquivo de memória, já no lar.

    `LAB_MEMORIA_DIR` continua mandando: a suíte de testes não pode escrever na
    memória de verdade. Isso já custou uma vez -- os testes gravaram decisões
    pendentes nos mesmos arquivos do software, e aquelas decisões apontando
    números que nenhuma mesa sorteou iam entrar no placar dele como erro.
    """
    lab = os.environ.get("LAB_MEMORIA_DIR")
    if lab:
        base = Path(lab)
        try:
            base.mkdir(parents=True, exist_ok=True)
            return base / nome
        except OSError:
            pass
    return lar() / nome


def ler_json(nome: str, padrao=None):
    """Lê um arquivo de memória; devolve `padrao` se não existir ou estiver roto."""
    try:
        p = arquivo(nome)
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return padrao


def gravar_json(nome: str, dado) -> bool:
    """Grava um arquivo de memória de forma atômica.

    Escreve num temporário e troca por cima. Sem isso, um desligamento no meio da
    escrita deixa o JSON truncado -- e um `memoria_lightning.json` truncado é a
    memória perdida do mesmo jeito, com o agravante de parecer que está lá.
    """
    try:
        p = arquivo(nome)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(dado, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, p)
        return True
    except Exception:
        return False


def resumo() -> List[str]:
    """As linhas para o log: onde a memória está e o que há nela."""
    p = lar()
    L = [f"[Memória] lar: {p}"]
    for m in motivo():
        L.append(f"[Memória] {m}")
    try:
        arqs = sorted(p.glob("*.json"))
        if arqs:
            tam = sum(a.stat().st_size for a in arqs)
            L.append(f"[Memória] {len(arqs)} arquivo(s), {tam/1024:.0f} KB — "
                     f"sobrevive à próxima versão")
        else:
            L.append("[Memória] lar vazio ainda — primeira execução")
    except Exception:
        pass
    return L
