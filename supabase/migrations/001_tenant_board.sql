-- PVD Tenant Board: posts, replies, votes
-- Run this in Supabase SQL Editor or via Supabase CLI

-- Posts (roommate listings + tenant Q&A)
create table if not exists posts (
  id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('roommate', 'tenant')),
  name text not null default 'Anonymous',
  zip text,
  title text not null,
  body text,
  topic text,
  -- roommate-specific
  budget int,
  movein text,
  seeking text,
  lifestyle text[],
  contact text,
  -- computed
  vote_count int not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_posts_type on posts(type);
create index if not exists idx_posts_zip on posts(zip);
create index if not exists idx_posts_created_at on posts(created_at desc);

-- Replies (AI + community)
create table if not exists replies (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references posts(id) on delete cascade,
  text text not null,
  is_ai boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_replies_post_id on replies(post_id);

-- Votes (anonymous: fingerprint = browser-generated id in localStorage)
create table if not exists votes (
  post_id uuid not null references posts(id) on delete cascade,
  voter_fingerprint text not null,
  direction int not null check (direction in (1, -1)),
  primary key (post_id, voter_fingerprint)
);

-- RLS: allow public read/write for anonymous forum (adjust for production)
alter table posts enable row level security;
alter table replies enable row level security;
alter table votes enable row level security;

create policy "posts_select" on posts for select using (true);
create policy "posts_insert" on posts for insert with check (true);
create policy "posts_update" on posts for update using (true);

create policy "replies_select" on replies for select using (true);
create policy "replies_insert" on replies for insert with check (true);

create policy "votes_select" on votes for select using (true);
create policy "votes_insert" on votes for insert with check (true);
create policy "votes_update" on votes for update using (true);
create policy "votes_delete" on votes for delete using (true);

-- Trigger: keep posts.vote_count in sync with votes table
create or replace function update_post_vote_count()
returns trigger as $$
begin
  update posts
  set vote_count = coalesce((
    select sum(direction) from votes where post_id = coalesce(new.post_id, old.post_id)
  ), 0)
  where id = coalesce(new.post_id, old.post_id);
  return coalesce(new, old);
end;
$$ language plpgsql;

drop trigger if exists tr_votes_update_count on votes;
create trigger tr_votes_update_count
  after insert or update or delete on votes
  for each row execute function update_post_vote_count();
