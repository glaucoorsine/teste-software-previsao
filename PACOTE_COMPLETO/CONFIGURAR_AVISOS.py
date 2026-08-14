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
import secrets
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
CFG = RAIZ / "notificacoes.json"

# Sem vogais parecidas nem 0/O, 1/l: o tópico vai ser digitado à mão no
# celular, e um caractere ambíguo aqui vira uma hora procurando por que o
# aviso não chega.
ALFABETO = "abcdefghjkmnpqrstuvwxyz23456789"


def topico_novo() -> str:
    """Nome que ninguém adivinha — no ntfy o tópico é a senha."""
    return "lab-" + "-".join(
        "".join(secrets.choice(ALFABETO) for _ in range(5)) for _ in range(3))


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
print("  1) ntfy        — o mais simples: instale o app e pronto.")
print("                   Sem cadastro, sem bot, sem apikey.")
print("  2) WhatsApp    — chega junto com suas outras mensagens,")
print("                   mas depende do CallMeBot autorizar")
print("  3) Telegram    — precisa criar um bot no @BotFather")
print("  4) desligar")
print()
op = input("  Escolha [1-4]: ").strip() or "1"

cfg = {"canal": "nenhum", "topico": "", "token": "", "chat_id": "",
       "telefone": "", "apikey": ""}

if op == "1":
    cabeca("NTFY — dois passos")
    print()
    print("  1. No celular, instale o aplicativo  ntfy  (Android ou iPhone).")
    print()
    print("  2. Abra o app, toque no  +  e assine EXATAMENTE este tópico:")
    print()
    top = (input("     (ENTER para eu sortear um nome seguro, ou digite o seu): ")
           .strip())
    if not top:
        top = topico_novo()
    print()
    print("     ┌" + "─" * 52 + "┐")
    print(f"     │  {top:<50}│")
    print("     └" + "─" * 52 + "┘")
    print()
    print("  Copie letra por letra. Esse nome é a senha: quem souber, recebe")
    print("  os seus avisos — por isso não é um nome bonitinho.")
    print()
    print("  E atenção ao que já te derrubou uma vez: o ntfy tem DOIS lados.")
    print("  Trocar o nome aqui NÃO muda o que o aplicativo está escutando.")
    print("  Se você não assinar no app, nada chega e nada avisa que falhou.")
    print()
    cfg.update({"canal": "ntfy", "topico": top})
    input("  Quando tiver assinado no app, aperte ENTER para eu testar.")

elif op == "2":
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

elif op == "3":
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
        # Falha de rede não é falha de configuração. Sem separar as duas, o
        # aviso manda procurar defeito no app quando o problema era a internet.
        if any(p in err for p in ("ProxyError", "ConnectionError", "Timeout",
                                  "SSLError", "NameResolution", "ConnectTimeout")):
            print("  Isto foi a conexão, não a sua configuração.")
            print("  O computador não conseguiu falar com o servidor.")
            print("  Confira a internet (ou se um firewall/antivírus está")
            print("  bloqueando) e rode este configurador de novo.")
            raise SystemExit(1)
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
