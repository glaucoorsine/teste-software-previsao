# Correções — 11/08/2026 (BUILD 2026-08-11-v39)

## Propósito do software
Laboratório de **previsibilidade acadêmica** sobre sequências categóricas de jogos específicos.
Objetivo técnico: medir se estruturas (padrões, familiaridades, resíduos) superam baselines em avaliação prospectiva, com placar de acertos/erros por janela e rastreabilidade.

## Bloqueadores corrigidos
1. Timestamps canônicos (`time_utils.py`) — Z e +00:00 unificados
2. `hist_buffer.py` único — rejeita domínio inválido; lock falhou não grava
3. `fetch_historico.py` — page_size e max_pages respeitados
4. LSTM — manifesto obrigatório no save/load; torch em requirements
5. Horizonte fixo nos 4 combos — janela não encerra no primeiro acerto
6. `db_path()` dinâmico no catálogo

## Placar de acertos e erros
- Contagem **por janela completa** (horizonte fixo)
- HIT no meio da janela não fecha a janela
- Ao final: +1 acerto se houve pelo menos um HIT; senão +1 erro
- Placar na UI: `Acertos X | Erros Y`
- Histórico visual: ✓ / ✗ por evento
- Persistido em `*_combo_state.json` (ok, err, keys)

## Pacotes
`PACOTE_COMPLETO.zip` inclui academia_autonoma + utilitários + combos.
