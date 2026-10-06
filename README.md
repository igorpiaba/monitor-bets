# Monitor Bets

Acompanha, a cada ~10 minutos, se as casas de apostas regulamentadas no Brasil ainda redirecionam para o gov.br (bloqueio da MP nº 1.394/2026), avisa as mudanças num canal do Telegram e publica um painel.

## Rodar localmente

```bash
python3 -m venv .venv && .venv/bin/pip install httpx pytest
.venv/bin/pytest                    # testes
.venv/bin/python -m monitor.rodada  # uma rodada (sem TELEGRAM_TOKEN, só imprime os alertas)
```
