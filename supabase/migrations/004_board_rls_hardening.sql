-- Harden Tenant Board RLS and ownership tracking.
-- Run after 001_tenant_board.sql, 002_auth_admin.sql, 003_board_auth_required.sql

-- Ownership columns for auditability and policy enforcement.
alter table if exists posts
  add column if not exists author_user_id uuid default auth.uid();

alter table if exists replies
  add column if not exists author_user_id uuid default auth.uid();

alter table if exists votes
  add column if not exists voter_user_id uuid default auth.uid();

create index if not exists idx_posts_author_user_id on posts(author_user_id);
create index if not exists idx_replies_author_user_id on replies(author_user_id);
create index if not exists idx_votes_voter_user_id on votes(voter_user_id);

-- Replace trigger function so vote_count updates can continue even when direct client
-- updates on posts are restricted.
create or replace function update_post_vote_count()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  update posts
  set vote_count = coalesce((
    select sum(direction) from votes where post_id = coalesce(new.post_id, old.post_id)
  ), 0)
  where id = coalesce(new.post_id, old.post_id);
  return coalesce(new, old);
end;
$$;

-- Rebuild board policies with tighter checks.
drop policy if exists "posts_select_auth" on posts;
drop policy if exists "posts_insert_auth" on posts;
drop policy if exists "posts_update_auth" on posts;

drop policy if exists "replies_select_auth" on replies;
drop policy if exists "replies_insert_auth" on replies;

drop policy if exists "votes_select_auth" on votes;
drop policy if exists "votes_insert_auth" on votes;
drop policy if exists "votes_update_auth" on votes;
drop policy if exists "votes_delete_auth" on votes;

-- Authenticated users can read board content.
create policy "posts_select_auth"
  on posts for select
  to authenticated
  using (true);

create policy "replies_select_auth"
  on replies for select
  to authenticated
  using (true);

-- Authenticated users can create posts/replies only as themselves.
create policy "posts_insert_auth"
  on posts for insert
  to authenticated
  with check (
    auth.uid() is not null
    and coalesce(author_user_id, auth.uid()) = auth.uid()
    and length(title) between 1 and 240
    and coalesce(length(body), 0) <= 4000
    and coalesce(length(contact), 0) <= 300
  );

create policy "replies_insert_auth"
  on replies for insert
  to authenticated
  with check (
    auth.uid() is not null
    and coalesce(author_user_id, auth.uid()) = auth.uid()
    and length(text) between 1 and 4000
  );

-- Prevent direct client edits to posts/replies. Add explicit edit APIs later if needed.
create policy "posts_update_auth"
  on posts for update
  to authenticated
  using (false);

create policy "replies_update_auth"
  on replies for update
  to authenticated
  using (false);

create policy "replies_delete_auth"
  on replies for delete
  to authenticated
  using (false);

-- Votes are private to the authenticated creator (frontend only needs own votes).
create policy "votes_select_auth"
  on votes for select
  to authenticated
  using (
    auth.uid() is not null
    and coalesce(voter_user_id, auth.uid()) = auth.uid()
  );

create policy "votes_insert_auth"
  on votes for insert
  to authenticated
  with check (
    auth.uid() is not null
    and coalesce(voter_user_id, auth.uid()) = auth.uid()
    and length(voter_fingerprint) between 1 and 128
    and direction in (1, -1)
  );

create policy "votes_update_auth"
  on votes for update
  to authenticated
  using (
    auth.uid() is not null
    and coalesce(voter_user_id, auth.uid()) = auth.uid()
  )
  with check (
    auth.uid() is not null
    and coalesce(voter_user_id, auth.uid()) = auth.uid()
    and length(voter_fingerprint) between 1 and 128
    and direction in (1, -1)
  );

create policy "votes_delete_auth"
  on votes for delete
  to authenticated
  using (
    auth.uid() is not null
    and coalesce(voter_user_id, auth.uid()) = auth.uid()
  );

