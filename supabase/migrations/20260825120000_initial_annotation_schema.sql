-- Initial schema for shared fish-image annotation.
-- Authentication identities come from Supabase Auth (auth.users).

create extension if not exists pgcrypto;

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null check (char_length(display_name) between 1 and 60),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.datasets (
  dataset_id text primary key,
  generated_at timestamptz,
  task_count integer not null default 0 check (task_count >= 0),
  candidate_count integer not null default 0 check (candidate_count >= 0),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.labeling_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  dataset_id text not null references public.datasets(dataset_id) on delete restrict,
  started_at timestamptz not null default now(),
  ended_at timestamptz
);

create table public.annotations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  session_id uuid references public.labeling_sessions(id) on delete set null,
  dataset_id text not null references public.datasets(dataset_id) on delete restrict,
  target_id text not null,
  fish_id text not null,
  canonical_name text not null,
  reference_filename text,
  candidate_id text not null,
  candidate_image_url text,
  candidate_source_page_url text,
  judgment text not null check (judgment in ('yes', 'no', 'unsure', 'broken')),
  position integer not null check (position > 0),
  question_batch_id uuid not null,
  created_at timestamptz not null default now(),
  unique (user_id, dataset_id, fish_id, candidate_id)
);

create index annotations_user_dataset_created_idx
  on public.annotations (user_id, dataset_id, created_at desc);
create index annotations_dataset_fish_idx
  on public.annotations (dataset_id, fish_id);
create index annotations_question_batch_idx
  on public.annotations (question_batch_id);
create index labeling_sessions_user_dataset_idx
  on public.labeling_sessions (user_id, dataset_id, started_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

alter table public.profiles enable row level security;
alter table public.datasets enable row level security;
alter table public.labeling_sessions enable row level security;
alter table public.annotations enable row level security;

create policy "users can view their own profile"
  on public.profiles for select
  to authenticated
  using ((select auth.uid()) = id);

create policy "users can create their own profile"
  on public.profiles for insert
  to authenticated
  with check ((select auth.uid()) = id);

create policy "users can update their own profile"
  on public.profiles for update
  to authenticated
  using ((select auth.uid()) = id)
  with check ((select auth.uid()) = id);

create policy "authenticated users can view datasets"
  on public.datasets for select
  to authenticated
  using (true);

create policy "users can view their own sessions"
  on public.labeling_sessions for select
  to authenticated
  using ((select auth.uid()) = user_id);

create policy "users can create their own sessions"
  on public.labeling_sessions for insert
  to authenticated
  with check ((select auth.uid()) = user_id);

create policy "users can update their own sessions"
  on public.labeling_sessions for update
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "users can view their own annotations"
  on public.annotations for select
  to authenticated
  using ((select auth.uid()) = user_id);

create policy "users can create their own annotations"
  on public.annotations for insert
  to authenticated
  with check ((select auth.uid()) = user_id);
