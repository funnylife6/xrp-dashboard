-- PRO_RIPPLER Supabase security setup
-- Run this in Supabase SQL Editor after creating one admin user in Authentication.
-- Recommended: disable public signups in Authentication settings.

alter table comments enable row level security;
alter table pro_rippler_news enable row level security;
alter table board_posts enable row level security;
alter table board_replies enable row level security;

grant select, insert on comments to anon;
grant select on pro_rippler_news to anon;
grant select, insert on board_posts to anon;
grant select, insert on board_replies to anon;

grant all on comments to authenticated;
grant all on pro_rippler_news to authenticated;
grant all on board_posts to authenticated;
grant all on board_replies to authenticated;

drop policy if exists "public can read visible comments" on comments;
drop policy if exists "admins can read all comments" on comments;
drop policy if exists "public can create comments" on comments;
drop policy if exists "public can update comment engagement" on comments;
drop policy if exists "admins can manage comments" on comments;

create policy "public can read visible comments"
on comments for select
to anon
using (is_hidden = false);

create policy "admins can read all comments"
on comments for select
to authenticated
using (true);

create policy "public can create comments"
on comments for insert
to anon
with check (is_hidden = false);

create policy "public can update comment engagement"
on comments for update
to anon
using (is_hidden = false)
with check (is_hidden = false);

create policy "admins can manage comments"
on comments for all
to authenticated
using (true)
with check (true);

revoke update on comments from anon;
grant update (like_count, report_count) on comments to anon;

drop policy if exists "public can read active pro news" on pro_rippler_news;
drop policy if exists "admins can manage pro news" on pro_rippler_news;

create policy "public can read active pro news"
on pro_rippler_news for select
to anon
using (is_active = true);

create policy "admins can manage pro news"
on pro_rippler_news for all
to authenticated
using (true)
with check (true);

drop policy if exists "public can read visible board posts" on board_posts;
drop policy if exists "admins can read all board posts" on board_posts;
drop policy if exists "public can create board posts" on board_posts;
drop policy if exists "public can update board post views" on board_posts;
drop policy if exists "admins can manage board posts" on board_posts;

create policy "public can read visible board posts"
on board_posts for select
to anon
using (is_hidden = false);

create policy "admins can read all board posts"
on board_posts for select
to authenticated
using (true);

create policy "public can create board posts"
on board_posts for insert
to anon
with check (is_hidden = false);

create policy "public can update board post views"
on board_posts for update
to anon
using (is_hidden = false)
with check (is_hidden = false);

create policy "admins can manage board posts"
on board_posts for all
to authenticated
using (true)
with check (true);

revoke update on board_posts from anon;
grant update (view_count) on board_posts to anon;

drop policy if exists "public can read visible board replies" on board_replies;
drop policy if exists "admins can read all board replies" on board_replies;
drop policy if exists "public can create board replies" on board_replies;
drop policy if exists "admins can manage board replies" on board_replies;

create policy "public can read visible board replies"
on board_replies for select
to anon
using (is_hidden = false);

create policy "admins can read all board replies"
on board_replies for select
to authenticated
using (true);

create policy "public can create board replies"
on board_replies for insert
to anon
with check (is_hidden = false);

create policy "admins can manage board replies"
on board_replies for all
to authenticated
using (true)
with check (true);
