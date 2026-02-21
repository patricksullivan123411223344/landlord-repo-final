-- Auth skeleton: admin_users table
-- Only emails in this table can access the hidden admin panel.
-- Add your admin email after creating a Supabase Auth user.

create table if not exists admin_users (
  email text primary key,
  created_at timestamptz not null default now()
);

-- RLS: only admins can read the list (to check if current user is admin)
alter table admin_users enable row level security;

-- Allow authenticated users to check if their own email is in the list
create policy "admin_users_select_self"
  on admin_users for select
  using (auth.jwt() ->> 'email' = email);

-- Service role can manage (use Supabase Dashboard to add first admin)
-- For first-time setup: insert via Supabase Dashboard SQL Editor:
--   insert into admin_users (email) values ('your@email.com');
