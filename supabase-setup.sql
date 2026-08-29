-- ============================================================
--  猫咪时间报 · Supabase 建表脚本
--  执行方式：Supabase Dashboard → SQL Editor → New Query → 粘贴运行
-- ============================================================

-- 1. 建表：workbench_data（主数据表，每条 storage_key 一行，存整份 JSON）
create table if not exists public.workbench_data (
  id           bigserial primary key,
  storage_key  text unique not null,   -- 数据标识（如 cat-time-bureau-v1）
  data         jsonb not null default '{}'::jsonb,  -- 整份数据 JSON
  device_id    text,                   -- 最后修改的设备 ID
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

-- 2. 索引
create index if not exists idx_workbench_data_storage_key on public.workbench_data(storage_key);

-- 3. 自动更新 updated_at 的触发器
create or replace function public.handle_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists set_updated_at on public.workbench_data;
create trigger set_updated_at
before update on public.workbench_data
for each row execute function public.handle_updated_at();

-- 4. 开启 Row Level Security（RLS）
alter table public.workbench_data enable row level security;

-- 5. RLS 策略：允许匿名读写（个人使用，简单策略）
--    注意：这是个人使用场景。如果多人使用，需要加用户认证。
drop policy if exists "Enable read access for all users" on public.workbench_data;
create policy "Enable read access for all users"
  on public.workbench_data for select
  using (true);

drop policy if exists "Enable insert access for all users" on public.workbench_data;
create policy "Enable insert access for all users"
  on public.workbench_data for insert
  with check (true);

drop policy if exists "Enable update access for all users" on public.workbench_data;
create policy "Enable update access for all users"
  on public.workbench_data for update
  using (true)
  with check (true);

drop policy if exists "Enable delete access for all users" on public.workbench_data;
create policy "Enable delete access for all users"
  on public.workbench_data for delete
  using (true);

-- 6. 开启 Realtime（实时订阅）
--    这一步需要在 Dashboard 里手动操作：
--    Database → Replication → 0 tables → 勾选 workbench_data
--    或者执行下面的 SQL（需要 superuser，Supabase 免费版可能需要在 Dashboard 操作）

-- 执行完后，去 Supabase Dashboard → Database → Replication
-- 找到 "supabase_realtime" publication，点 0 tables，勾选 workbench_data，保存
