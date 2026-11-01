# Meu Dinheiro

Controle financeiro pessoal (contas, cartões, lançamentos) e carteira de investimentos (ações, FIIs, ETFs, BDRs, exterior e cripto) com proventos automáticos.

- **App:** `index.html` (publicado pelo GitHub Pages). Login e dados no Supabase.
- **Banco:** `supabase/schema.sql` (rodar uma vez no SQL Editor do Supabase).
- **Rotina diária:** `.github/workflows/atualizar.yml` roda `scripts/atualizar.py` em dias úteis, às 8h e às 19h (Brasília), e grava cotações, dólar e proventos. Precisa do segredo `SUPABASE_SERVICE_KEY` em *Settings > Secrets and variables > Actions*.

Fontes: Yahoo Finance (cotações e dólar), Status Invest e B3 (proventos no Brasil), Nasdaq (proventos nos EUA).
