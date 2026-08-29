// 家属数据合并脚本：将 u2 家属数据合并进 g1 分组数据
const SB_URL = "https://ksljnxlgoajbhxshqvaf.supabase.co";
const SB_KEY = "sb_publishable_BxKV01FyPcYliI3jwSedqg_ukfbMhgk";
const FAMILY_USER_ID = 2;

async function api(path, opts = {}) {
  const res = await fetch(SB_URL + path, {
    ...opts,
    headers: {
      "apikey": SB_KEY,
      "Authorization": "Bearer " + SB_KEY,
      "Content-Type": "application/json",
      ...(opts.headers || {})
    }
  });
  if (!res.ok) throw new Error(path + " -> " + res.status + " " + await res.text());
  return res.json();
}

async function main() {
  // 1. 读取 u2 和 g1
  const u2Rows = await api("/rest/v1/workbench_data?storage_key=eq.cat-time-bureau-v1-u2&select=storage_key,updated_at,data");
  const g1Rows = await api("/rest/v1/workbench_data?storage_key=eq.cat-time-bureau-v1-g1&select=storage_key,updated_at,data");

  const u2 = u2Rows[0]?.data || {};
  const g1 = g1Rows[0]?.data || {};

  console.log("=== 合并前 ===");
  console.log("u2 money:", (u2.money||[]).length, "todo:", (u2.todo||[]).length, "note:", (u2.note||[]).length);
  console.log("g1 money:", (g1.money||[]).length, "todo:", (g1.todo||[]).length, "note:", (g1.note||[]).length);

  // 2. 需要合并的模块
  const bizKeys = ["money", "todo", "note"];

  // 3. 构建 g1 现有 id 集合（用于去重）
  const existingIds = {};
  bizKeys.forEach(k => {
    (g1[k] || []).forEach(r => { if (r.id) existingIds[k + "_" + r.id] = true; });
  });

  // 4. 收集需要新增的家属记录
  const toAdd = { money: [], todo: [], note: [] };
  let dupCount = 0;
  let seedCount = 0;

  bizKeys.forEach(k => {
    (u2[k] || []).forEach(r => {
      const idKey = k + "_" + r.id;
      if (existingIds[idKey]) {
        dupCount++;
        return;
      }
      // 判断是否为种子数据（种子 id: money 51-54,9002; todo 11-13; note 61,9001,9003）
      const seedIds = { money: [51,52,53,54,9002], todo: [11,12,13], note: [61,9001,9003] };
      const isSeed = seedIds[k].includes(r.id);
      // 标记家属来源
      const newRec = { ...r, createUserId: FAMILY_USER_ID, createRole: "family", createdBy: "family" };
      // 防止糖币发放
      if (k === "todo" && newRec.done) newRec._candySettled = true;
      if (k === "money") newRec._candySettled = true;
      if (isSeed) seedCount++;
      toAdd[k].push(newRec);
    });
  });

  const totalNew = toAdd.money.length + toAdd.todo.length + toAdd.note.length;
  console.log("\n=== 合并预览 ===");
  console.log("新增记账:", toAdd.money.length, "条");
  console.log("新增任务:", toAdd.todo.length, "条");
  console.log("新增灵感:", toAdd.note.length, "条");
  console.log("去重跳过:", dupCount, "条");
  console.log("其中种子数据:", seedCount, "条");

  if (totalNew === 0) {
    console.log("\n没有需要合并的新记录");
    return;
  }

  // 5. 合并到 g1
  const newG1 = { ...g1 };
  bizKeys.forEach(k => {
    newG1[k] = [...(g1[k] || []), ...toAdd[k]];
  });

  // 6. 保存到云端
  const now = new Date().toISOString();
  const deviceId = "merge-" + Date.now();

  const payload = {
    storage_key: "cat-time-bureau-v1-g1",
    data: newG1,
    device_id: deviceId,
    updated_at: now
  };

  console.log("\n=== 执行合并 ===");
  const upsertRes = await fetch(SB_URL + "/rest/v1/workbench_data?on_conflict=storage_key", {
    method: "POST",
    headers: {
      "apikey": SB_KEY,
      "Authorization": "Bearer " + SB_KEY,
      "Content-Type": "application/json",
      "Prefer": "resolution=merge-duplicates,return=minimal"
    },
    body: JSON.stringify(payload)
  });
  if (!upsertRes.ok) throw new Error("upsert failed: " + upsertRes.status + " " + await upsertRes.text());

  console.log("✅ 合并成功！");
  console.log("g1 money:", newG1.money.length, "todo:", newG1.todo.length, "note:", newG1.note.length);

  // 7. 验证
  const verifyRows = await api("/rest/v1/workbench_data?storage_key=eq.cat-time-bureau-v1-g1&select=storage_key,updated_at,data");
  const verify = verifyRows[0]?.data || {};
  console.log("\n=== 验证 ===");
  console.log("g1 money:", (verify.money||[]).length, "todo:", (verify.todo||[]).length, "note:", (verify.note||[]).length);
  const familyRecs = [];
  bizKeys.forEach(k => {
    (verify[k] || []).forEach(r => { if (r.createRole === "family") familyRecs.push({ module: k, id: r.id, title: r.title || r.content }); });
  });
  console.log("家属记录:", familyRecs.length, "条");
  familyRecs.forEach(r => console.log("  -", r.module, r.id, r.title));
}

main().catch(e => { console.error("❌ 错误:", e.message); process.exit(1); });
