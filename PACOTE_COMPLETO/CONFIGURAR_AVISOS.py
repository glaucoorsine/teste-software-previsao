# -*- coding: utf-8 -*-
"""
CONFIGURAR AVISOS — pergunta, configura e TESTA na hora.

    python CONFIGURAR_AVISOS.py      (ou CONFIGURAR_AVISOS.bat)

Existe porque editar `notificacoes.json` na mão é fonte de erro silencioso: o
operador trocou o tópico do ntfy no arquivo e continuou sem receber nada, sem
nenhuma pista do motivo. O motivo é que o ntfy tem DOIS lados — mudar o tópico
no arquivo não muda o que o aplicativo do celular está escutando, e é preciso
assinar o tópico novo lá também.

Aqui isso não acontece: no fim, uma mensagem de teste é enviada de verdade e a
tela diz o que aconteceu. Se não chegar no celular, você descobre agora, e não
daqui a três horas de mesa perdida.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
CFG = RAIZ / "notificacoes.json"


def sim(p, padrao=True):
    r = input(p).strip().lower()
    if not r:
        return padrao
    return r.startswith("s")


def cabeca(t):
    print()
    print("=" * 66)
    print(f" {t}")
    print("=" * 66)


cabeca("COMO VOCÊ QUER RECEBER OS AVISOS DE ENTRADA?")
print()
print("  1) WhatsApp    — chega junto com suas outras mensagens")
print("  2) Telegram    — mais confiável, mas precisa do app")
print("  3) ntfy        — sem cadastro, mas exige assinar o tópico no app")
print("  4) desligar")
print()
op = input("  Escolha [1-4]: ").strip() or "1"

cfg = {"canal": "nenhum", "topico": "", "token": "", "chat_id": "",
       "telefone": "", "apikey": ""}

if op == "1":
    cabeca("WHATSAPP — três passos, uma vez só")
    print()
    print("  1. Salve este número nos seus contatos:")
    print()
    print("         +34 644 51 95 23")
    print()
    print("  2. Mande uma mensagem de WhatsApp PARA ele, com este texto exato:")
    print()
    print("         I allow callmebot to send me messages")
    print()
    print("  3. Ele responde com uma apikey (uns números). Cole aqui embaixo.")
    print()
    print("  (É gratuito. A API oficial do WhatsApp exige empresa verificada")
    print("   e provedor pago, então este é o caminho viável para uso pessoal.)")
    print()
    tel = input("  Seu número com código do país (ex 5531999998888): ").strip()
    tel = "".join(ch for ch in tel if ch.isdigit())
    key = input("  A apikey que o bot respondeu: ").strip()
    cfg.update({"canal": "whatsapp", "telefone": tel, "apikey": key})

elif op == "2":
    cabeca("TELEGRAM")
    print()
    print("  1. No Telegram, fale com @BotFather e mande /newbot")
    print("  2. Ele devolve um token (algo como 123456:ABC-DEF...)")
    print("  3. Mande qualquer mensagem para o SEU bot")
    print("  4. Abra no navegador, trocando SEU_TOKEN:")
    print("     https://api.telegram.org/botSEU_TOKEN/getUpdates")
    print("     e procure por \"chat\":{\"id\":NUMERO")
    print()
    tok = input("  Token do bot: ").strip()
    cid = input("  chat_id: ").strip()
    cfg.update({"canal": "telegram", "token": tok, "chat_id": cid})

elif op == "3":
    cabeca("NTFY")
    print()
    print("  ATENÇÃO — este é o que já deu problema antes.")
    print("  O ntfy tem DOIS lados. Trocar o tópico aqui NÃO muda o que o")
    print("  aplicativo está escutando. Depois de escolher o nome abaixo,")
    print("  abra o app ntfy no celular e ASSINE exatamente esse mesmo nome.")
    print()
    print("  O nome funciona como senha: quem souber, recebe seus avisos.")
    print("  Use algo que ninguém adivinharia.")
    print()
    top = input("  Nome do tópico: ").strip()
    cfg.update({"canal": "ntfy", "topico": top})
    if top:
        print()
        print(f"  >>> AGORA abra o app ntfy e assine o tópico:  {top}")
        input("      Quando tiver assinado, aperte ENTER para testar.")

else:
    cabeca("AVISOS DESLIGADOS")

CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print(f"  Salvo em: {CFG}")

if cfg["canal"] == "nenhum":
    print("  Avisos desligados. Rode este arquivo de novo quando quiser ligar.")
    raise SystemExit(0)

cabeca("TESTANDO AGORA")
try:
    import notificador
    import importlib
    importlib.reload(notificador)
    if not notificador.ativo():
        print()
        print("  Faltou preencher algum campo — o canal ficou incompleto.")
        print("  Rode de novo e preencha tudo.")
        raise SystemExit(1)
    err = notificador._enviar(
        "Laboratório — teste",
        "Se você está lendo isto no celular, os avisos de entrada vão chegar.")
    print()
    if err:
        print(f"  NÃO FOI: {err}")
        print()
        if cfg["canal"] == "whatsapp":
            print("  Causas comuns:")
            print("   - a apikey está errada ou veio com espaço")
            print("   - o número precisa do código do país, só dígitos")
            print("   - você ainda não mandou a mensagem de autorização ao bot")
        elif cfg["canal"] == "ntfy":
            print("  Causa comum: o app não está assinando este tópico.")
        raise SystemExit(1)
    print("  Enviado. Olhe o celular AGORA.")
    print()
    if sim("  Chegou? [S/n]: "):
        print()
        print("  Pronto. Os avisos de entrada vão por aqui.")
    else:
        print()
        if cfg["canal"] == "ntfy":
            print("  Então o app não está no tópico certo. Abra o ntfy,")
            print(f"  toque em + e assine exatamente: {cfg['topico']}")
        elif cfg["canal"] == "whatsapp":
            print("  Verifique se você mandou a mensagem de autorização")
            print("  ao CallMeBot e se a apikey está sem espaços.")
        print("  Depois rode este configurador de novo.")
except SystemExit:
    raise
except Exception as e:
    print(f"  Erro inesperado: {type(e).__name__}: {e}")
