#!/usr/bin/env node
/**
 * 校验单文件 HTML 内联 <script> 的语法。
 *
 * 背景：2026-09-08 事故——index.html 的 renderTodoPage 末尾多了一个 `}`，
 * 整个 6020 行内联 script 语法解析失败，全部 JS 不执行（go/render/view 全 undefined、
 * 底部栏 onclick 没绑），但首页静态 HTML 照常显示，看起来"正常"，实际整页交互瘫痪。
 * 本脚本用于提交前拦截这类语法错。
 *
 * 用法：
 *   node tools/check-syntax.js [file.html]     // 默认 ./index.html
 * 退出码：0=语法通过，1=有语法错，2=用法/环境错误
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const file = path.resolve(process.argv[2] || 'index.html');
if (!fs.existsSync(file)) {
  console.error('找不到文件: ' + file);
  process.exit(2);
}

const html = fs.readFileSync(file, 'utf8');

// 提取所有内联 <script>（跳过带 src 的外链）
const re = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
const blocks = [];
let m;
while ((m = re.exec(html)) !== null) {
  const attrs = m[1] || '';
  if (/\bsrc\s*=/.test(attrs)) continue;
  // <script> 起始标签所在行号（全文数换行）
  let tagLine = 1;
  for (let i = 0; i < m.index; i++) if (html[i] === '\n') tagLine++;
  blocks.push({ tagLine, code: m[2] });
}

if (!blocks.length) {
  console.log('未发现内联 <script>，跳过');
  process.exit(0);
}

const nodeBin = process.execPath;
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'htmlchk-'));
let failed = false;

blocks.forEach((b, i) => {
  const tmpFile = path.join(tmpDir, `inline${i}.js`);
  fs.writeFileSync(tmpFile, b.code);
  const res = spawnSync(nodeBin, ['--check', tmpFile], { encoding: 'utf8' });
  if (res.status === 0) {
    console.log(`  [块${i + 1} L${b.tagLine}] OK (${b.code.split('\n').length} 行)`);
    return;
  }
  failed = true;
  const out = (res.stderr || '').toString();
  const lm = /^.*?:(\d+)$/m.exec(out);           // 形如 "/tmp/inline0.js:1555"
  const msgM = /SyntaxError:\s*(.+)/.exec(out);
  const blockLine = lm ? +lm[1] : null;
  // inline.js 第 N 行 == 原文件第 (tagLine + N - 1) 行（<script> 标签后紧跟换行）
  const realLine = blockLine ? b.tagLine + blockLine - 1 : null;
  console.error(`\n  [块${i + 1} L${b.tagLine}] 语法错误: ${msgM ? msgM[1].trim() : out.split('\n')[0].trim()}`);
  if (realLine) {
    console.error(`    位置: ${file}:${realLine}`);
    const lines = html.split('\n');
    const from = Math.max(0, realLine - 4);
    const to = Math.min(lines.length, realLine + 3);
    for (let n = from; n < to; n++) {
      const mark = (n === realLine - 1) ? ' >> ' : '    ';
      console.error(`    ${mark}${String(n + 1).padStart(5)}| ${lines[n]}`);
    }
  } else {
    console.error(out.split('\n').slice(0, 5).join('\n'));
  }
});

try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch (_) {}

if (failed) {
  console.error(`\n❌ ${path.basename(file)} 内联 JS 存在语法错误，已阻止提交`);
  process.exit(1);
}
console.log(`✅ ${path.basename(file)} 内联 JS 语法校验通过 (${blocks.length} 个块)`);
process.exit(0);
