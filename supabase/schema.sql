-- Meu Dinheiro: estrutura do banco no Supabase
-- Cole tudo isto em Supabase > SQL Editor > New query e clique em Run.

-- Dados de cada usuário (contas, cartões, categorias, transações, ativos, operações, ajustes)
create table if not exists public.docs (
  user_id    uuid not null default auth.uid() references auth.users on delete cascade,
  col        text not null,
  id         text not null,
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, col, id)
);
alter table public.docs enable row level security;
alter table public.docs replica identity full;

drop policy if exists "docs_select" on public.docs;
drop policy if exists "docs_insert" on public.docs;
drop policy if exists "docs_update" on public.docs;
drop policy if exists "docs_delete" on public.docs;
create policy "docs_select" on public.docs for select to authenticated using (auth.uid() = user_id);
create policy "docs_insert" on public.docs for insert to authenticated with check (auth.uid() = user_id);
create policy "docs_update" on public.docs for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "docs_delete" on public.docs for delete to authenticated using (auth.uid() = user_id);

-- Dados de mercado (cotações, proventos, dólar), gravados pela rotina diária do GitHub
create table if not exists public.mercado_docs (
  col        text not null,
  id         text not null,
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (col, id)
);
alter table public.mercado_docs enable row level security;
alter table public.mercado_docs replica identity full;
drop policy if exists "mercado_select" on public.mercado_docs;
create policy "mercado_select" on public.mercado_docs for select to authenticated using (true);
-- (só a rotina, com a chave service_role, escreve nesta tabela)

-- Atualiza updated_at automaticamente
create or replace function public.touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
drop trigger if exists docs_touch on public.docs;
create trigger docs_touch before update on public.docs for each row execute function public.touch_updated_at();
drop trigger if exists mercado_touch on public.mercado_docs;
create trigger mercado_touch before update on public.mercado_docs for each row execute function public.touch_updated_at();

-- Sincronização em tempo real entre celular e computador
do $$ begin
  begin alter publication supabase_realtime add table public.docs; exception when duplicate_object then null; end;
  begin alter publication supabase_realtime add table public.mercado_docs; exception when duplicate_object then null; end;
end $$;
