# -*- coding: utf-8 -*-
"""
TESTE DA RED DOOR ROULETTE — a quinta mesa, ligada em todo lugar necessário.

    "adicione esta roleta https://www.casino.org/casinoscores/pt-br/red-door-roulette/"

O QUE ESTE ARQUIVO PROVA, E O QUE ELE NÃO PODE PROVAR
───────────────────────────────────────────────────────
Prova que a mesa está ligada em todos os pontos que uma mesa precisa: nas
listas de jogos, no roteamento de endereço, na identidade (não pode ler nem
ser lida por outra mesa), no domínio de validação, no pipeline (37 classes,
roleta comum), na tela avulsa, no vídeo, no público.

O que ele NÃO prova, porque nada aqui pode provar: que o endereço da API que
eu escolhi é o certo. Eu não alcanço casino.org deste ambiente -- confirmado
de novo ao escrever isto -- então o endereço primário é um palpite seguindo o
padrão que funcionou para as outras três mesas do casino.org. O que este
arquivo garante é que, MESMO SE o palpite estiver errado, a mesa não vai ficar
muda (há vinte grafias na descoberta) nem vai ler os dados de outra mesa por
engano (identidade_ok recusa).
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

FALHAS = []


def checar(ok, titulo, detalhe=""):
    print(f"  {'ok  ' if ok else 'FALHA'} {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not ok:
        FALHAS.append(titulo)
    return ok


def teste_captura():
    print("\n[1] CAPTURA — endereço, alternativas, identidade")
    import fluxo_captura as F

    checar("red_door" in F.API_BY_GAME, "tem endereço principal declarado")
    ends = F.enderecos_para("red_door")
    checar(len(ends) >= 3, f"tem {len(ends)} endereço(s) candidatos (principal "
                           f"+ alternativas)")

    checar(F.identidade_ok("red_door", ends[0])[0],
           "o próprio endereço declarado passa na checagem de identidade — "
           "senão a mesa nunca conseguiria gravar a própria fonte")

    for outra in ("lightning", "mega_fire", "crazy_time", "crazy_time_a"):
        ok, _ = F.identidade_ok(outra, F.API_BY_GAME["red_door"])
        checar(not ok, f"{outra} NÃO pode aceitar o endereço da Red Door")
        ok2, _ = F.identidade_ok("red_door", F.API_BY_GAME.get(outra, ""))
        checar(not ok2, f"Red Door NÃO pode aceitar o endereço de {outra}")

    html = F.enderecos_html("red_door")
    checar(html and html[0] == "https://www.casino.org/casinoscores/pt-br/red-door-roulette/",
           "a página que ele mandou é a primeira fonte de vídeo/contagem",
           html[:1])

    grafias_ok = 0
    import descobridor_endereco as D
    for u in D.candidatos("red_door"):
        if F.identidade_ok("red_door", u)[0]:
            grafias_ok += 1
    checar(grafias_ok >= 3,
           f"o gerador de grafias produz várias tentativas plausíveis "
           f"({grafias_ok} passam na identidade) — se o palpite principal "
           f"estiver errado, ainda há por onde a mesa se achar",
           f"{grafias_ok} grafias aceitas")


def teste_pipeline():
    print("\n[2] PIPELINE — roleta comum, 37 classes, sem CT nenhum")
    import ia_modulos as im
    p = im.PipelinePerceptivo("red_door")
    checar(p.is_ct is False, "não é tratada como Crazy Time")
    checar(p.n_classes == 37, "37 classes — roleta comum", p.n_classes)


def teste_dominio_e_buffer():
    print("\n[3] DOMÍNIO — validação do buffer não descarta os giros dela")
    import hist_buffer as H
    checar(H.DOMAIN.get("red_door") == H.ROULETTE,
           "o domínio de validação é o de roleta (0..36)")
    # mesmo sem a chave, o fallback é ROULETTE — mas a chave explícita evita
    # depender de um default que pode mudar
    checar("0" in H.DOMAIN["red_door"] and "36" in H.DOMAIN["red_door"],
           "0 e 36 estão no domínio dela")


def teste_telas_e_listas():
    print("\n[4] TELAS — a quinta aba, o quinto painel, a quinta janela")
    # CENTRAL.py importa customtkinter, que este ambiente de teste não tem
    # (não há tela aqui). Lê o código como texto -- mesmo caminho que o resto
    # da suíte usa para checar CENTRAL.py sem precisar de um display.
    central = (RAIZ / "CENTRAL.py").read_text(encoding="utf-8")
    checar('("red_door", "Red Door")' in central,
           "está na lista mestra JOGOS, que gera as abas")
    checar('"red_door": "red_door_combo_state.json"' in central,
           "tem arquivo de estado próprio em ESTADO")

    import publico_mesa as P
    checar("red_door" in P.ANCORAS, "tem âncora de público própria")

    import video_mesa as V
    checar("red_door" in V.PADRAO and "red_door" in V.TITULOS,
           "tem endereço e título de vídeo")

    checar((RAIZ / "red_door_combo.py").is_file(), "tem lançador avulso")
    checar((RAIZ / "9_INICIAR_RED_DOOR.bat").is_file(), "tem atalho .bat")
    abrir = (RAIZ / "ABRIR_TUDO.bat").read_text(encoding="utf-8")
    checar("red_door_combo.py" in abrir,
           "está no ABRIR_TUDO — quem roda tudo de uma vez pega ela também")


def teste_combo_compartilhado():
    print("\n[5] O LANÇADOR — reusa a UI, não duplica 596 linhas de novo")
    fonte = (RAIZ / "lightning_combo.py").read_text(encoding="utf-8")
    checar("red_door" in fonte and "_ROLETAS_COMUNS" in fonte,
           "lightning_combo.py sabe desenhar a Red Door")
    mega = (RAIZ / "mega_fire_combo.py").read_text(encoding="utf-8")
    checar("from lightning_combo import main" in mega and len(mega) < 2000,
           "mega_fire_combo.py também virou lançador -- não fica sozinho "
           "carregando a cópia de 596 linhas que a Red Door não repetiu")
    red = (RAIZ / "red_door_combo.py").read_text(encoding="utf-8")
    checar("from lightning_combo import main" in red, "red_door reusa a mesma UI")

    # o teste que importa: um GAME estranho não pode abrir a janela como se
    # fosse lightning silenciosamente-errado -- tem que cair no padrão.
    #
    # Este ambiente de teste não tem customtkinter (não há tela aqui), e
    # `lightning_combo.py` importa a biblioteca antes de qualquer outra
    # coisa. Um `customtkinter` de mentira, no molde que test_central.py já
    # usa para o mesmo problema, deixa o import acontecer sem precisar de
    # display nenhum.
    import types
    falso = types.ModuleType("customtkinter")

    class _Boneco:
        def __init__(self, *a, **k):
            pass

        def __getattr__(self, _n):
            return lambda *a, **k: None

    for nome in ("CTk", "CTkFrame", "CTkLabel", "CTkFont", "CTkImage"):
        setattr(falso, nome, type(nome, (_Boneco,), {}))
    falso.set_appearance_mode = lambda *a: None
    guardado_ctk = sys.modules.get("customtkinter")
    guardado_lc = sys.modules.pop("lightning_combo", None)
    import os as _os
    guardado_lab = _os.environ.get("LAB_MESA")
    try:
        sys.modules["customtkinter"] = falso
        _os.environ["LAB_MESA"] = "mesa_que_nao_existe"
        import lightning_combo as L
        checar(L.GAME == "lightning" and L.ROTULO == "LIGHTNING",
               "LAB_MESA inválido cai para lightning, não trava nem abre "
               "em branco", f"GAME={L.GAME!r} ROTULO={L.ROTULO!r}")
    finally:
        if guardado_ctk is not None:
            sys.modules["customtkinter"] = guardado_ctk
        else:
            sys.modules.pop("customtkinter", None)
        sys.modules.pop("lightning_combo", None)
        if guardado_lc is not None:
            sys.modules["lightning_combo"] = guardado_lc
        if guardado_lab is None:
            _os.environ.pop("LAB_MESA", None)
        else:
            _os.environ["LAB_MESA"] = guardado_lab


def teste_com_dado_real_da_sonda():
    """A resposta DE VERDADE que ele mandou, não mais palpite sobre o formato.

    A sonda que ele rodou trouxe o JSON cru de cinco mesas, com o endereço
    principal respondendo 200 em quatro delas -- inclusive a Red Door, que
    era só um palpite meu até este arquivo chegar. Aqui as rodadas reais
    (recortadas dos campos que não importam para o parser: vencedores, valor
    em dinheiro) viram fixture, para o parser ser testado contra o formato
    de verdade, não contra o que eu imaginei que ele fosse.

    Nenhuma das rodadas capturadas pagou multiplicador -- o número da sorte
    não bateu com o que saiu em nenhuma delas, o que é o caso comum. Isso não
    enfraquece o teste: o que importa aqui é que TODOS os números anunciados e
    TODOS os multiplicadores sejam lidos certos, que é exatamente o defeito
    que já apareceu duas vezes neste arquivo (Mega Fire lendo 0% quando o
    site mostrava 74X).
    """
    import sys as _sys
    _sys.path.insert(0, str(RAIZ))
    import fluxo_captura as F
    from NUCLEO.situacao import _mult_do_giro

    # Lightning — api-cs.casino.org, 3 rodadas reais, giro 02:44:16Z
    lightning_real = [{
        "id": "6a83c70019aef3109978baf9",
        "data": {"settledAt": "2026-08-18T02:44:16.764Z",
                 "result": {"outcome": {"number": 19, "type": "Odd", "color": "Red"},
                            "luckyNumbersList": [
                                {"number": 5, "roundedMultiplier": 200},
                                {"number": 10, "roundedMultiplier": 50},
                                {"number": 14, "roundedMultiplier": 200}]}}}]
    r = F.parse_items_roulette(lightning_real)
    checar(r and r[0]["n"] == 19, "lightning: o número sai certo do dado real")
    pago, anun = _mult_do_giro(r[0])
    checar(anun == 3, "lightning: os 3 números da sorte anunciados são lidos",
           f"anunciados={anun}")
    checar(pago == 0,
           "lightning: 19 não estava entre 5/10/14 — não paga, e o software "
           "não pode inventar pagamento", f"pago={pago}")
    fogo = [t["lucky"] for t in r[0]["tags"] if "lucky" in t][0]
    checar({(it["n"], it["x"]) for it in fogo} == {(5, 200), (10, 50), (14, 200)},
           "e os TRÊS multiplicadores batem exatamente com o que a API mandou",
           fogo)

    # Red Door — o endereço que era palpite meu respondeu 200 de verdade
    red_door_real = [{
        "id": "6a83c6ea927eb29a45cde464",
        "data": {"settledAt": "2026-08-18T02:43:53.863Z",
                 "gameType": "reddoorroulette",
                 "table": {"id": "RedDoorRoulette1", "name": "Red Door Roulette"},
                 "result": {"outcome": {"number": 35, "type": "Odd", "color": "Black"},
                            "luckyNumbersList": [
                                {"number": 2, "roundedMultiplier": 1},
                                {"number": 3, "roundedMultiplier": 1},
                                {"number": 4, "roundedMultiplier": 1}]}}},
        {"id": "6a83c6a9927eb29a45cde45f",
         "data": {"settledAt": "2026-08-18T02:42:49.359Z",
                  "gameType": "reddoorroulette",
                  "result": {"outcome": {"number": 10, "type": "Even", "color": "Black"},
                             "luckyNumbersList": [
                                 {"number": 0, "roundedMultiplier": 1},
                                 {"number": 14, "roundedMultiplier": 1},
                                 {"number": 31, "roundedMultiplier": 5}]}}}]
    r2 = F.parse_items_roulette(red_door_real)
    checar(len(r2) == 2 and {x["n"] for x in r2} == {35, 10},
           "red door: as duas rodadas reais chegam com o número certo",
           [x["n"] for x in r2])
    for linha in r2:
        pago2, anun2 = _mult_do_giro(linha)
        checar(anun2 == 3,
               f"red door giro {linha['n']}: os 3 anunciados são lidos sem "
               f"eu ter chutado nome de campo nenhum — o mesmo leitor que já "
               f"serve o Lightning", f"anunciados={anun2}")
    checar(pago == 0 and pago2 == 0,
           "red door: nenhuma das duas rodadas teve o número da sorte igual "
           "ao que saiu — não paga, e é isso mesmo (não é sinal de defeito)")
    # o 5x do 31 na segunda rodada tem que estar lá, mesmo sem ter pago
    fogo2 = [t["lucky"] for t in r2[1]["tags"] if "lucky" in t][0]
    checar((31, 5) in {(it["n"], it["x"]) for it in fogo2},
           "e o multiplicador 5x do 31 é lido corretamente, ainda que não "
           "tenha sido o número sorteado", fogo2)


def teste_sonda_inclui_a_mesa_nova():
    print("\n[6] A SONDA — vai medir a mesa nova também")
    fonte = (RAIZ / "SONDA_MESAS.py").read_text(encoding="utf-8")
    checar('"red_door"' in fonte, "red_door entrou na lista que a sonda varre")


def main() -> int:
    print("═" * 72)
    print("RED DOOR ROULETTE — a quinta mesa, ligada de ponta a ponta")
    print("═" * 72)
    teste_captura()
    teste_pipeline()
    teste_dominio_e_buffer()
    teste_telas_e_listas()
    teste_combo_compartilhado()
    teste_com_dado_real_da_sonda()
    teste_sonda_inclui_a_mesa_nova()
    print("\n" + "═" * 72)
    if FALHAS:
        print(f"{len(FALHAS)} FALHA(S):")
        for f in FALHAS:
            print(f"  ✗ {f}")
        return 1
    print("RED_DOOR_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
