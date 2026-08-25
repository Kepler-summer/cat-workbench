# 🐱 猫咪时间报 · 部署指南

## 一、本地访问

本地服务已启动，访问地址：
```
http://localhost:8765/index.html
```

## 二、Supabase 数据库初始化

### 步骤 1：打开 Supabase Dashboard

访问 https://supabase.com/dashboard 登录，进入对应的项目。

### 步骤 2：执行建表 SQL

左侧菜单 → **SQL Editor** → **New Query**，依次执行以下两个脚本：

#### 脚本 1：主数据表（如已执行可跳过）
> 文件：`supabase-setup.sql`

```sql
-- ============================================================
--  猫咪时间报 · Supabase 建表脚本
-- ============================================================

-- 1. 建表：workbench_data（主数据表）
create table if not exists public.workbench_data (
  id           bigserial primary key,
  storage_key  text unique not null,
  data         jsonb not null default '{}'::jsonb,
  device_id    text,
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

-- 5. RLS 策略
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

-- 6. 开启 Realtime
-- Database → Replication → supabase_realtime → 勾选 workbench_data
```

#### 脚本 2：用户表（必须执行）
> 文件：`supabase-users-setup.sql`

```sql
-- ============================================================
--  猫咪时间报 · 用户管理表
-- ============================================================

-- 用户表：最多 2 个账号（管理员 + 家属）
CREATE TABLE IF NOT EXISTS workbench_users (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'family' CHECK (role IN ('admin', 'family')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 启用 RLS
ALTER TABLE workbench_users ENABLE ROW LEVEL SECURITY;

-- 允许匿名访问
CREATE POLICY "allow_all_users" ON workbench_users
  FOR ALL USING (true) WITH CHECK (true);

-- 启用 Realtime（可选）
ALTER PUBLICATION supabase_realtime ADD TABLE workbench_users;
```

### 步骤 3：开启 Realtime（可选，用于多设备实时同步）

左侧菜单 → **Database** → **Replication** → 找到 `supabase_realtime` → 点击表格数 → 勾选 `workbench_data` 和 `workbench_users` → 保存。

## 三、初始化数据

建表完成后，刷新页面即可使用：

1. 首次访问会跳转到**登录页**
2. 点击"没有账号？去注册" → 创建第一个账号（角色选管理员）
3. 登录后进入工作台，系统会自动同步数据到云端
4. 在"用户管理"中可以查看已注册账号

## 四、数据迁移（从旧版升级）

如果之前已经使用过旧版（未登录状态的数据）：

1. 旧数据存储在 localStorage 的 `cat-time-bureau-v1` key 中
2. 注册新账号后，数据会按用户隔离存储在 `cat-time-bureau-v1-u{用户ID}` 中
3. 如需迁移旧数据，可在浏览器控制台执行：

```javascript
// 先登录新账号，然后执行以下代码迁移旧数据
const oldData = localStorage.getItem('cat-time-bureau-v1');
if (oldData) {
  const newKey = CONFIG.storageKey; // 当前用户的 storage key
  localStorage.setItem(newKey, oldData);
  store.save(); // 同步到云端
  console.log('数据迁移完成！');
  location.reload();
}
```

## 五、常见问题

**Q: 注册时提示"数据库未连接"？**
A: 检查 Supabase 项目是否正常运行，anon key 是否正确。

**Q: 云端数据和本地不一致？**
A: 系统采用"本地优先，云端同步"策略，保存操作会在 800ms 后同步到云端。刷新页面会自动拉取云端最新数据。

**Q: 忘记密码怎么办？**
A: 目前需要在 Supabase Dashboard → Table Editor → workbench_users 中手动重置 password_hash 字段，或删除账号重新注册。
