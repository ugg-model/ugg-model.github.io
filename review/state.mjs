// Pure review-state functions. No network or storage writes here.
export const TASKS = ["nvs", "depth", "camera"];
export const SCHEMA = "ugg-review/v1";
export const STORAGE_KEY = "ugg-material-review:v1";
export function validateManifest(manifest) {
  for (const task of TASKS) {
    const cases = manifest?.[task]?.cases;
    if (!Array.isArray(cases) || !cases.length) throw new Error(`缺少 ${task} 候选清单`);
    const ids = new Set();
    for (const c of cases) {
      if (typeof c.id !== "string" || !c.id || ids.has(c.id)) throw new Error(`${task} 案例 ID 缺失或重复`);
      ids.add(c.id);
    }
  }
  return manifest;
}
export function freshState(manifest, defaults) {
  validateManifest(manifest);
  const tasks = {};
  for (const task of TASKS) {
    const ids = new Set(manifest[task].cases.map(c => c.id));
    const selected = (defaults[task] || []).filter(id => ids.has(id));
    if (new Set(selected).size !== selected.length) throw new Error(`${task} 推荐名单存在重复`);
    tasks[task] = {selected: [...selected], records: Object.fromEntries(manifest[task].cases.map(c => [c.id, {reviewed: false, note: ""}]))};
  }
  return {schema: SCHEMA, updated_at: null, tasks};
}
export function restoreState(raw, manifest, baseline) {
  if (!raw || raw.schema !== SCHEMA || !raw.tasks || typeof raw.tasks !== "object") throw new Error("不是本筛选台导出的 JSON 文件");
  const result = structuredClone(baseline);
  const unknown = [];
  const taskNames = Object.keys(raw.tasks);
  if (!taskNames.length || taskNames.some(task => !TASKS.includes(task))) throw new Error("任务名称或结构不正确");
  for (const task of taskNames) {
    const input = raw.tasks[task];
    if (!input || !Array.isArray(input.selected) || input.selected.some(id => typeof id !== "string")) throw new Error(`${task} 勾选名单不正确`);
    if (new Set(input.selected).size !== input.selected.length) throw new Error(`${task} 勾选名单有重复 ID`);
    const known = new Set(manifest[task].cases.map(c => c.id));
    const missing = input.selected.filter(id => !known.has(id));
    if (missing.length) throw new Error(`${task} 中有当前素材库不存在的已选案例：${missing.slice(0,3).join(", ")}`);
    result.tasks[task].selected = [...input.selected];
    if (input.records !== undefined && (!input.records || Array.isArray(input.records) || typeof input.records !== "object")) throw new Error(`${task} 备注结构不正确`);
    for (const [id, record] of Object.entries(input.records || {})) {
      if (!known.has(id)) { unknown.push(`${task}/${id}`); continue; }
      if (!record || typeof record.reviewed !== "boolean" || typeof record.note !== "string" || record.note.length > 4000) throw new Error(`${task}/${id} 备注或复核状态不正确`);
      result.tasks[task].records[id] = {reviewed: record.reviewed, note: record.note};
    }
  }
  result.updated_at = typeof raw.updated_at === "string" ? raw.updated_at : null;
  return {state: result, unknown};
}
export function setSelected(state, task, id, value) {
  if (!state.tasks[task]?.records[id]) throw new Error("未知案例");
  const selected = state.tasks[task].selected;
  if (value && !selected.includes(id)) selected.push(id);
  if (!value) state.tasks[task].selected = selected.filter(item => item !== id);
  state.tasks[task].records[id].reviewed = true;
}
export function makeExport(state, manifest, source) {
  const result = structuredClone(state);
  result.exported_at = new Date().toISOString();
  result.source = source;
  result.counts = Object.fromEntries(TASKS.map(task => [task, {candidates: manifest[task].cases.length, selected: state.tasks[task].selected.length}]));
  result.note = "Selections are task-specific; no homepage changes have been applied. Candidate media are GT-oracle-selected showcase results.";
  return result;
}
