-- Optional image mirror for frequently used candidate images.
-- Public read keeps the static GitHub Pages app simple; uploads remain private
-- to service-role/admin tooling and are never exposed to browser users.
insert into storage.buckets (id, name, public)
values ('candidate-images', 'candidate-images', true)
on conflict (id) do update set public = excluded.public;

create policy "public can view candidate image mirrors"
  on storage.objects for select
  to anon, authenticated
  using (bucket_id = 'candidate-images');
