// Final user selection from UGG_selections_1791910567753.json.
// The latest exported selected IDs/order supersede all earlier recommendations.
export const NVS_SHOWCASE_IDS = Object.freeze([
  "re10k128_50f__ncf2-sample_00064",
  "re10k128_50f__ncf2-sample_00097",
  "re10k_c50__ncf2-sample_00008",
  "re10k_c50__ncf2-sample_00004",
  "re10k128_50f__ncf2-sample_00063",
  "re10k128_50f__ncf2-sample_00054",
  "dl3dv20__ncf2-sample_00000",
  "dl3dv20__ncf2-sample_00012",
  "re10k_c50__ncf2-sample_00006",
  "re10k128_50f__ncf2-sample_00100",
  "dl3dv20__ncf2-sample_00009",
  "dl3dv20__ncf2-sample_00007",
  "re10k_c50__ncf2-sample_00000",
  "re10k128_50f__ncf2-sample_00118",
  "re10k128_50f__ncf2-sample_00018",
  "re10k_c50__ncf2-sample_00002",
  "re10k128_50f__ncf2-sample_00025",
  "re10k128_50f__ncf2-sample_00076",
  "re10k_c50__ncf2-sample_00005",
  "re10k128_50f__ncf2-sample_00113",
  "re10k_c50__ncf2-sample_00007",
  "dl3dv20__ncf2-sample_00006",
  "dl3dv20__ncf2-sample_00018",
  "spatialvid__ncf2-sample_00007",
]);

/** Return only approved NVS cases in display order, without mutating inputs. */
export function applyNvsShowcase(manifest) {
  if (!Array.isArray(manifest?.nvs?.cases)) {
    throw new Error("NVS showcase requires an imported NVS case list.");
  }
  const gallery = manifest.nvs;
  const byId = new Map(gallery.cases.map(example => [example.id, example]));
  if (byId.size !== gallery.cases.length) {
    throw new Error("Duplicate case IDs in the imported NVS gallery.");
  }
  const missing = NVS_SHOWCASE_IDS.filter(id => !byId.has(id));
  if (missing.length) {
    // Fail closed: a re-import must not substitute unreviewed cases.
    throw new Error("Approved NVS showcase cases missing: " + missing.join(", "));
  }
  const cases = NVS_SHOWCASE_IDS.map(id => byId.get(id));
  if (cases.some(example => example.protocol !== "ncf2")) {
    throw new Error("Approved NVS showcase cases require two conditioning frames.");
  }
  const counts = {};
  cases.forEach(example => { counts[example.dataset] = (counts[example.dataset] || 0) + 1; });
  return {
    ...manifest,
    nvs: {
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
        protocol: "ncf2",
        conditioning_frames: 2,
        task_independent: true,
        page_size: 24,
        page_datasets: [counts],
        caption: "24 selected NVS examples · 2 conditioning frames. RealEstate10K: 17, DL3DV: 6, Spatial Video: 1.",
      },
    },
  };
}
