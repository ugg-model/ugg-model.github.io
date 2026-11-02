# UGG benchmarks

`data.js` is the single source for the charts, complete task tables and CSV exports.
`benchmarks.js` renders it without a charting library or remote requests;
`benchmarks.css` is scoped to `#benchmarks` and inherits the site's light/dark tokens.
The layout follows the dataset-grouped mini bar charts on the MoSE3 website.

## Numerical source

Transcribed from the supplied manuscript **UGG: Unified Generative Geometry Model**,
file `4D_World_Model__NeurIPS_2026_.pdf`, Tables 1–4 on pages 7–10.

SHA-256 of the supplied PDF:
`940b454026b45c6dd9296d252e163d7d3b89683e234717fd5d6b2bd71394f5ed`

| Table | Scope | Numeric values |
| --- | --- | ---: |
| 1 | Camera-controlled generation, 2-view and 1-view | 54 |
| 2 | Camera pose, dense and sparse | 100 |
| 3 | Depth, dense and sparse, including TTS and TTS Oracle | 160 |
| 4a–d | Matched-budget ablations and history guidance | 64 |
| Total | 10 settings | 378 |

Every number and its displayed decimal precision was checked against the supplied
PDF's table text and rendered tables. This update does not replace the existing
`assets/ugg-paper.pdf`; links continue to point to that repository asset.

## Display conventions

- The first block of Table 1 is **2-view**, the second **1-view**.
- Sparse camera evaluation uses **tAE and RPEr**, following Table 2's caption and
  headers, rather than the dense ATE/RPEt metrics mentioned in nearby prose.
- Depth delta values remain fractions, not percentages.
- TTS is the paper's RGB-reprojection-selected result from 16 candidates. It is
  not portrayed as uniformly better than the single-sample model.
- TTS Oracle is an optional, dashed reference in charts and a separate row in the
  complete tables. It is excluded from best non-oracle result highlighting.
- Table 4 is a separate matched-budget ablation, not the main benchmark model.
  Table 4b retains its two comparison blocks and distinct Full model / Dense ray
  maps rows; best values are marked within each block, including ties.
- Bars start at zero. Each dataset/metric has an independent labeled scale.
  No metric is inverted, normalized, or averaged into a cross-task score.
- The complete tables and CSV contain every setting and dataset of the selected
  task, regardless of the chart filter. Their precision matches the manuscript.
- Figure 7's per-budget curves are not digitized or synthesized from the image.

## Checks and maintenance

After changing `data.js`, run from the repository root:

```sh
node scripts/test-benchmarks.mjs
```

The test checks dimensions, counts, metric directions, precision and regression
cases for the scientific distinctions above. For new manuscript versions, also
check every changed value against that manuscript and update the source hash.

Before this update was published, local browser checks covered all 10 settings,
all 378 table entries, dataset filtering, the Oracle toggle, four CSV downloads,
keyboard tabs, no-JavaScript fallback, reduced motion and chart animation.
Light/dark layouts were checked at widths 320, 390, 768 and 1440 pixels. Existing
video and 3D gallery modules are outside the scope of these benchmark checks.
