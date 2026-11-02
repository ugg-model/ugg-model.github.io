// Final user selection from UGG_selections_1791910567753.json.
// The latest exported selected IDs/order supersede all earlier recommendations.
export const DEPTH_SHOWCASE_IDS = Object.freeze([
  "scannetpp-scene_44",
  "scannetpp-scene_18",
  "scannetpp-scene_19",
  "bonn-rgbd_bonn_person_tracking2",
  "sintel-alley_2",
  "kitti-2011_09_26_drive_0095_sync_02",
  "scannetpp-scene_3",
  "scannetpp-scene_4",
  "bonn-rgbd_bonn_crowd3",
  "kitti-2011_09_28_drive_0037_sync_02",
  "scannetpp-scene_46",
  "scannetpp-scene_32",
  "scannetpp-scene_36",
  "scannetpp-scene_38",
  "kitti-2011_09_30_drive_0016_sync_02",
  "kitti-2011_10_03_drive_0047_sync_02",
  "sintel-sleeping_2",
  "bonn-rgbd_bonn_crowd2",
  "scannetpp-scene_6",
  "kitti-2011_09_26_drive_0005_sync_02",
  "scannetpp-scene_29",
  "scannetpp-scene_35",
  "scannetpp-scene_20",
  "scannetpp-scene_11",
]);

/** Return the display manifest without mutating imported cases or other tasks. */
export function applyDepthShowcase(manifest) {
  if (!Array.isArray(manifest?.depth?.cases)) {
    throw new Error("Depth showcase requires an imported depth case list.");
  }
  const gallery = manifest.depth;
  const byId = new Map(gallery.cases.map(example => [example.id, example]));
  if (byId.size !== gallery.cases.length) {
    throw new Error("Duplicate case IDs in the imported depth gallery.");
  }
  const missing = DEPTH_SHOWCASE_IDS.filter(id => !byId.has(id));
  if (missing.length) {
    // Never silently substitute an unreviewed case after re-importing assets.
    throw new Error("Approved depth showcase cases missing: " + missing.join(", "));
  }
  const cases = DEPTH_SHOWCASE_IDS.map(id => byId.get(id));
  const counts = {};
  cases.forEach(example => { counts[example.dataset] = (counts[example.dataset] || 0) + 1; });
  return {
    ...manifest,
    depth: {
      ...gallery,
      cases,
      selection: {
        method: "user_review_selection",
        source_commit: "276f6086638c506b64dab3299e35339a0746c995",
        source_export: "UGG_selections_1791910567753.json",
        source_export_sha256: "41e48de4f2353289b8fda24ccc060a6e6ca0bfc79cb97854caaf67cf19847e5c",
        exported_at: "2026-10-13T16:56:07.753Z",
        publication_record: "assets/published-selection.json",
        candidate_count: 72,
        available: gallery.selection?.available ?? gallery.cases.length,
        selected: cases.length,
        limit: cases.length,
        dataset_quotas: counts,
        task_independent: true,
        page_size: 24,
        page_datasets: [counts],
        caption: "24 selected depth examples: ScanNet++ 14, Bonn 3, KITTI 5, Sintel 2.",
      },
    },
  };
}
