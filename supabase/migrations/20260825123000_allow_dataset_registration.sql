-- The static website registers the dataset manifest before submitting annotations.
-- Dataset rows contain public metadata only; annotation data remains user-scoped.
create policy "authenticated users can register datasets"
  on public.datasets for insert
  to authenticated
  with check (true);
