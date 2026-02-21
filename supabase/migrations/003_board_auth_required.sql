-- Require authenticated users for board read/write actions.
-- Run after 001_tenant_board.sql and 002_auth_admin.sql

-- Drop permissive public policies from migration 001.
drop policy if exists "posts_select" on posts;
drop policy if exists "posts_insert" on posts;
drop policy if exists "posts_update" on posts;

drop policy if exists "replies_select" on replies;
drop policy if exists "replies_insert" on replies;

drop policy if exists "votes_select" on votes;
drop policy if exists "votes_insert" on votes;
drop policy if exists "votes_update" on votes;
drop policy if exists "votes_delete" on votes;

-- Allow only authenticated users to read/write board content.
create policy "posts_select_auth"
  on posts for select
  to authenticated
  using (true);

create policy "posts_insert_auth"
  on posts for insert
  to authenticated
  with check (true);

create policy "posts_update_auth"
  on posts for update
  to authenticated
  using (true);

create policy "replies_select_auth"
  on replies for select
  to authenticated
  using (true);

create policy "replies_insert_auth"
  on replies for insert
  to authenticated
  with check (true);

create policy "votes_select_auth"
  on votes for select
  to authenticated
  using (true);

create policy "votes_insert_auth"
  on votes for insert
  to authenticated
  with check (true);

create policy "votes_update_auth"
  on votes for update
  to authenticated
  using (true);

create policy "votes_delete_auth"
  on votes for delete
  to authenticated
  using (true);
