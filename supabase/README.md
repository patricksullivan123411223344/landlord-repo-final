# Supabase Setup for Tenant Board

## 1. Create a Supabase project

1. Go to [supabase.com](https://supabase.com) and create a project
2. In **Project Settings -> API**, copy:
   - **Project URL** -> `SUPABASE_URL`
   - **anon public** key -> `SUPABASE_ANON_KEY`

## 2. Add to `.env`

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
```

## 3. Run the migrations

In Supabase Dashboard -> **SQL Editor**, run in order:

1. `migrations/001_tenant_board.sql` - forum tables
2. `migrations/002_auth_admin.sql` - admin auth allowlist
3. `migrations/003_board_auth_required.sql` - require sign-in for board feed/post/replies/votes

Or with Supabase CLI:

```bash
supabase db push
```

## 4. Tables created

- **posts** - Roommate listings and tenant Q&A
- **replies** - AI and community replies (feed chats)
- **votes** - Up/down votes (by browser fingerprint)
- **admin_users** - Emails allowed to access the hidden admin panel

## 5. Enable Auth & add first admin

1. In Supabase Dashboard -> **Authentication** -> **Providers**, enable **Email**
2. Create at least one user in **Authentication** -> **Users** -> **Add user** (email + password)
3. Add that admin email to `admin_users` via SQL Editor:

   ```sql
   insert into admin_users (email) values ('your@email.com');
   ```

## 6. App sign-in behavior

- **Board URL:** `/fair-rent`
- Users must sign in (or create an account) before they can use the board.
- Feed posts, replies/chat messages, and votes are persisted to Supabase.

Quick verification:
1. Open `/fair-rent`, create account, then sign in.
2. Post a new roommate or tenant question.
3. Add a reply/chat message to a post.
4. Refresh and confirm data persists.
5. Check Supabase Table Editor rows in `posts` and `replies`.

## 7. Hidden admin panel

- **URL:** `/fair-rent/manage` (not linked from the site)
- **Security:** `noindex`, `nofollow`; requires sign-in + email in `admin_users`
- **Keys:** Uses same `SUPABASE_URL` and `SUPABASE_ANON_KEY` - no extra config

## Fallback

If Supabase is not configured, the Tenant Board falls back to `localStorage` with seed data.