#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
贴纸规范化脚本：缩尺寸 + 去除 AI 生成图自带的棋盘格底色

背景：
  原始 AI 生成 PNG 自带「实体棋盘格」底色，是两个交替色（约 (228,228,228) 与 (252,252,252)）。
  用「4 邻接 + 单参考色」flood-fill 只能清掉交替格中的一种颜色，另一种保留为不透明
  → App 内肉眼可见棋盘格。本脚本改用：
    - 8 邻接（含对角）：让棋盘格同色格沿对角连通
    - top-N 多参考色：保证两种（或多种）交替色都被清掉

用法：
  python3 tools/normalize-stickers.py --scan              # 只扫描，列出「有棋盘格/浅色残留」的文件
  python3 tools/normalize-stickers.py --apply [glob...]   # 处理（默认 assets/stickers/*.png）
  python3 tools/normalize-stickers.py --verify [glob...]  # 只验证断言，不改动

处理流程：
  1. 最长边 > --max-dim（默认 128）则等比缩小（保留新美术，绝不回滚旧图）
  2. 边界采样 → 量化 → 取 top-N 主色作参考色
  3. 从所有边界像素做 8 邻接 flood-fill，命中任一参考色则 alpha=0
  4. 安全帽：清除比例 > --max-clear（默认 70%）则自动降阈值重试，防止吃掉浅色主体
"""
import sys, os, glob
from collections import Counter, deque
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GLOB = "assets/stickers/*.png"


def collect_border(px, w, h):
    """采样四边像素（不含重复角）"""
    out = []
    for x in range(w):
        out.append(px[x, 0][:3])
        out.append(px[x, h - 1][:3])
    for y in range(1, h - 1):
        out.append(px[0, y][:3])
        out.append(px[w - 1, y][:3])
    return out


def top_refs(border, n):
    """量化后取 top-N 主色作为参考色集合"""
    q = [(r // 8 * 8, g // 8 * 8, b // 8 * 8) for r, g, b in border]
    return [c for c, _ in Counter(q).most_common(n)]


def flood_clear(im, refs, threshold):
    """8 邻接 flood-fill：从所有边界像素扩散，命中任一参考色则置为透明"""
    w, h = im.size
    px = im.load()
    visited = bytearray(w * h)
    q = deque()
    for x in range(w):
        q.append((x, 0)); q.append((x, h - 1))
    for y in range(1, h - 1):
        q.append((0, y)); q.append((w - 1, y))
    cleared = 0
    while q:
        x, y = q.popleft()
        if x < 0 or x >= w or y < 0 or y >= h:
            continue
        idx = y * w + x
        if visited[idx]:
            continue
        visited[idx] = 1
        r, g, b, a = px[x, y]
        hit = False
        for (R, G, B) in refs:
            if abs(r - R) + abs(g - G) + abs(b - B) <= threshold:
                hit = True
                break
        if hit:
            px[x, y] = (r, g, b, 0)
            cleared += 1
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy:
                        q.append((x + dx, y + dy))
    return cleared, w * h


def stats(im):
    """返回 (浅色占比, 不透明占比, 四角alpha, 中心alpha)"""
    w, h = im.size
    px = im.load()
    lt = tot = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b, a = px[x, y]
            if a == 255:
                tot += 1
                if r > 210 and g > 210 and b > 205:
                    lt += 1
    corners = [px[0, 0][-1], px[w - 1, 0][-1], px[0, h - 1][-1], px[w - 1, h - 1][-1]]
    center = px[w // 2, h // 2][-1]
    light_pct = lt * 100 // max(tot, 1)
    op_pct = tot * 100 // max((w // 2 + 1) * (h // 2 + 1), 1)
    return light_pct, op_pct, corners, center


def process(path, max_dim, max_clear, refs_n):
    """处理单张：缩尺寸 + 去底（带安全帽重试）"""
    im = Image.open(path)
    if max(im.size) > max_dim:
        im.thumbnail((max_dim, max_dim), Image.LANCZOS)
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    refs = top_refs(collect_border(px, w, h), refs_n)
    used_threshold = None
    for threshold in (26, 18, 12, 8):
        trial = im.copy()
        cleared, total = flood_clear(trial, refs, threshold)
        pct = cleared * 100 // max(total, 1)
        if pct <= max_clear:
            im = trial
            used_threshold = threshold
            break
    return im, used_threshold


def alpha_map(im, n=12):
    """生成 n×n 的 alpha 缩略图，用于判断是否呈连续剪影"""
    w, h = im.size
    px = im.load()
    rows = []
    for gy in range(n):
        row = ""
        for gx in range(n):
            x = min(int(gx * w / n), w - 1)
            y = min(int(gy * h / n), h - 1)
            row += "#" if px[x, y][-1] == 255 else "."
        rows.append(row)
    return rows


def scan(paths):
    print("=== 扫描：浅色残留 / 棋盘格特征 ===")
    bad = []
    for p in paths:
        try:
            im = Image.open(p).convert("RGBA")
        except Exception:
            continue
        light_pct, op_pct, corners, _ = stats(im)
        w, h = im.size
        flag = (light_pct > 60 and op_pct > 40)
        tag = "[BAD ]" if flag else "[ ok ]"
        if flag:
            bad.append(p)
        print(f"  {tag} {os.path.basename(p):30s} {w}x{h} light={light_pct:3d}% opaque={op_pct:3d}%")
    print(f"\n需处理 {len(bad)} 个文件")
    return bad


def verify(paths):
    print("=== 验证断言 ===")
    fails = []
    for p in paths:
        im = Image.open(p).convert("RGBA")
        light_pct, op_pct, corners, center = stats(im)
        ok_corner = all(c == 0 for c in corners)
        ok_light = light_pct <= 60
        ok_center = center == 255
        ok = ok_corner and ok_light and ok_center
        if not ok:
            fails.append(p)
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {os.path.basename(p):30s} corners={corners} light={light_pct}% center_a={center}")
    print(f"\n通过 {len(paths)-len(fails)}/{len(paths)}")
    return fails


def apply(paths, max_dim, max_clear, refs_n, show_map=False):
    print(f"=== 处理 {len(paths)} 个文件 (max_dim={max_dim}, max_clear={max_clear}%, refs={refs_n}) ===")
    for p in paths:
        before = Image.open(p).convert("RGBA")
        bl, bo, bc, _ = stats(before)
        out, th = process(p, max_dim, max_clear, refs_n)
        out.save(p)
        al, ao, ac, ctr = stats(out)
        name = os.path.basename(p)
        print(f"  {name:30s} {before.size[0]}x{before.size[1]} -> {out.size[0]}x{out.size[1]} "
              f"light {bl}% -> {al}%  opaque {bo}% -> {ao}%  thr={th}")
        if show_map:
            for row in alpha_map(out):
                print("        " + row)
    print("\n处理完成")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    mode = args[0]
    globs = args[1:] or [DEFAULT_GLOB]
    paths = []
    for g in globs:
        paths.extend(sorted(glob.glob(os.path.join(ROOT, g))))
    paths = [p for p in paths if os.path.isfile(p)]
    if not paths:
        print("没有匹配的文件")
        return
    max_dim = 128
    max_clear = 70
    refs_n = 4
    if mode == "--scan":
        scan(paths)
    elif mode == "--apply":
        apply(paths, max_dim, max_clear, refs_n, show_map=("--map" in args))
        print()
        verify(paths)
    elif mode == "--verify":
        verify(paths)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
