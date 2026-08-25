-- Public, aggregate-only leaderboard. Individual annotations remain private.
create or replace function public.get_annotation_leaderboard(
  p_dataset_id text,
  p_period text default 'all'
)
returns table (rank bigint, display_name text, label_count bigint)
language sql
security definer
set search_path = public
stable
as $$
  with grouped as (
    select a.user_id, count(*)::bigint as label_count
    from public.annotations a
    where a.dataset_id = p_dataset_id
      and (p_period <> 'week' or a.created_at >= date_trunc('week', now()))
    group by a.user_id
  ), ranked as (
    select dense_rank() over (order by g.label_count desc) as rank,
           coalesce(p.display_name, '匿名協作者') as display_name,
           g.label_count
    from grouped g
    left join public.profiles p on p.id = g.user_id
  )
  select ranked.rank, ranked.display_name, ranked.label_count
  from ranked
  order by ranked.rank, ranked.display_name
  limit 20;
$$;

revoke all on function public.get_annotation_leaderboard(text, text) from public;
grant execute on function public.get_annotation_leaderboard(text, text) to anon, authenticated;
