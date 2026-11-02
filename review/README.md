# UGG independent media-review workspace

Live entry after Pages publication: `/UGG-website/review/`.

All 210 imported candidates remain selectable: NVS 72, depth 72, camera 66. This is the website's candidate archive, not the upstream 456/80/66 experiment release. No production homepage, showcase allowlist, video encoding, camera matrix, alignment, benchmark or source manifest is changed.

The defaults are 24/24/24. Camera incorporates the user's second-round exclusions: scenes 29, 45, 0, 38, 26, 44, 19, 12 and 30. Together with the original 14 exclusions, all 23 are initially unselected. Fifteen previous camera selections remain; nine replacements are explicitly **provisional alternatives**, not verified improvements: scenes 23, 2, 27, 13, 28, 22, 20, 36 and 1. They were reconsidered from the earlier non-selected pool and still have trajectory/orientation limitations; see `config.json` for each caution. Users can choose any candidate, with no 24-case limit.

Selections, review marks and notes are stored only in this browser's `localStorage` (`ugg-material-review:v1`). They are not uploaded or applied to the homepage. Export versioned JSON to share selections or transfer between browsers. Import validates task names, selected IDs, duplicate IDs and notes before confirmation. There is also per-task ID text export, bulk selection, undo and reset-to-current-defaults. Existing saved selections are not overwritten when a preset changes; use the explicit reset button to apply a new preset.

The existing production synchronized viewer is reused, with an additional original-trajectory-video mode. Only one current viewer is retained, and inactive media are disposed. The same media and pose data remain untouched. Case links include task and ID but no personal selections. This page has no authentication; `noindex` is not access control. There is no backend or analytics.

Checks: `node review/test-state.mjs`. The actual HTML/CSS/app/viewer code was also exercised in an isolated Chromium fixture with asset/module transport and opaque-origin storage adapted. Passed: 72/72/66 candidates, defaults, 15+9 camera split, 23 exclusions, representative video and trajectory playback, frame seeking, task-isolated selection and notes, filters, bulk/undo, JSON export/import, and no horizontal overflow at 375/768/1440 px; no uncaught JS errors. Native-origin persistence and WebGL orbit were not verified in this restricted environment. Deployment success is separate from live browser acceptance.
