-- ============================================================
-- 猫咪时间报 · 用户管理表
-- 在 Supabase Dashboard → SQL Editor 中执行此脚本
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

-- 允许匿名访问（因为前端使用 anon key）
CREATE POLICY "allow_all_users" ON workbench_users
  FOR ALL USING (true) WITH CHECK (true);

-- 启用 Realtime
ALTER PUBLICATION supabase_realtime ADD TABLE workbench_users;
