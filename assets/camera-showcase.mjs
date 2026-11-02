// Final user selection from UGG_selections_1791910567753.json.
// The latest exported selected IDs/order supersede all earlier recommendations.
export const CAMERA_SHOWCASE_IDS = Object.freeze([
  "scannetpp-scene_3",
  "scannetpp-scene_42",
  "scannetpp-scene_4",
  "scannetpp-scene_32",
  "sintel-temple_2",
  "scannetpp-scene_46",
  "scannetpp-scene_25",
  "scannetpp-scene_6",
  "scannetpp-scene_2",
  "scannetpp-scene_37",
  "scannetpp-scene_33",
  "scannetpp-scene_11",
  "scannetpp-scene_9",
  "scannetpp-scene_17",
  "scannetpp-scene_1",
  "sintel-sleeping_2",
  "scannetpp-scene_28",
  "scannetpp-scene_24",
  "scannetpp-scene_45",
  "scannetpp-scene_10",
  "scannetpp-scene_12",
  "scannetpp-scene_22",
  "scannetpp-scene_19",
  "bonn-rgbd_bonn_balloon2",
]);

/** Return only approved camera cases in display order, without mutating inputs. */
export function applyCameraShowcase(manifest) {
  if (!Array.isArray(manifest?.camera?.cases)) {
    throw new Error("Camera showcase requires an imported camera case list.");
  }
  const gallery = manifest.camera;
  const byId = new Map(gallery.cases.map(example => [example.id, example]));
  if (byId.size !== gallery.cases.length) {
    throw new Error("Duplicate case IDs in the imported camera gallery.");
  }
  const missing = CAMERA_SHOWCASE_IDS.filter(id => !byId.has(id));
  if (missing.length) {
    // Fail closed: never substitute unreviewed cases after an asset re-import.
    throw new Error("Approved camera showcase cases missing: " + missing.join(", "));
  }
  const cases = CAMERA_SHOWCASE_IDS.map(id => byId.get(id));
  const counts = {};
  cases.forEach(example => { counts[example.dataset] = (counts[example.dataset] || 0) + 1; });
  return {
    ...manifest,
    camera: {
      ...gallery,
      cases,
      selection: {
        method: "user_review_selection",
        source_commit: "276f6086638c506b64dab3299e35339a0746c995",
        source_export: "UGG_selections_1791910567753.json",
        source_export_sha256: "41e48de4f2353289b8fda24ccc060a6e6ca0bfc79cb97854caaf67cf19847e5c",
        exported_at: "2026-10-13T16:56:07.753Z",
        publication_record: "assets/published-selection.json",
        candidate_count: 66,
        available: gallery.selection?.available ?? gallery.cases.length,
        selected: cases.length,
        limit: cases.length,
        dataset_quotas: counts,
        task_independent: true,
        page_size: 24,
        page_datasets: [counts],
        caption: "24 selected camera-pose examples: ScanNet++ 21, Sintel 2, Bonn 1.",
      },
    },
  };
}
