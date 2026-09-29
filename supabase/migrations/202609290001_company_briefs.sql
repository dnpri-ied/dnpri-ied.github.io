-- Ficha Empresa: persistencia, versiones, permisos y archivos privados.
create extension if not exists pgcrypto;

create or replace function public.es_editor_dnpri()
returns boolean language sql stable security definer set search_path=public
as $$
  select exists (
    select 1 from public.usuarios_dnpri
    where lower(email)=lower(coalesce(auth.jwt()->>'email',''))
      and activo is true and lower(rol) in ('administrador','editor')
  );
$$;

create table if not exists public.fichas_empresa (
  id uuid primary key default gen_random_uuid(),
  empresa text not null check (char_length(empresa) between 1 and 160),
  estado text not null default 'borrador' check (estado in ('borrador','final')),
  contenido jsonb not null default '{}'::jsonb,
  fuentes jsonb not null default '[]'::jsonb,
  creado_por uuid not null references auth.users(id),
  usuario_email text not null,
  creado_en timestamptz not null default now(),
  actualizado_en timestamptz not null default now()
);

create table if not exists public.fichas_empresa_versiones (
  id bigint generated always as identity primary key,
  ficha_id uuid not null references public.fichas_empresa(id) on delete cascade,
  contenido jsonb not null,
  fuentes jsonb not null,
  creado_por uuid not null references auth.users(id),
  creado_en timestamptz not null default now()
);

alter table public.fichas_empresa enable row level security;
alter table public.fichas_empresa_versiones enable row level security;
create policy "editores gestionan fichas" on public.fichas_empresa for all to authenticated using (public.es_editor_dnpri()) with check (public.es_editor_dnpri() and creado_por=auth.uid());
create policy "editores consultan versiones" on public.fichas_empresa_versiones for select to authenticated using (public.es_editor_dnpri());
create policy "editores crean versiones" on public.fichas_empresa_versiones for insert to authenticated with check (public.es_editor_dnpri() and creado_por=auth.uid());

insert into storage.buckets (id,name,public,file_size_limit,allowed_mime_types)
values ('fichas-empresa','fichas-empresa',false,52428800,array['application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/pdf'])
on conflict (id) do nothing;
create policy "editores leen exportaciones" on storage.objects for select to authenticated using (bucket_id='fichas-empresa' and public.es_editor_dnpri());
create policy "editores crean exportaciones" on storage.objects for insert to authenticated with check (
  bucket_id='fichas-empresa' and public.es_editor_dnpri() and (storage.foldername(name))[1]=auth.uid()::text
);
