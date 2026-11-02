# Benchmark method colors

Every method or variant ID in `data.js` owns one fixed, unique RGB color across
Generation, Camera Pose, Depth and Ablations. Never assign colors by row position,
cycle a short palette per tab, or give a new method an existing method's color.
The renderer already reads this registry for both bars and legend swatches.

## Fixed palette

| Method / variant | Color |
| --- | --- |
| Aether | `#e47739` |
| SEVA | `#bd4147` |
| Geo4D | `#20996d` |
| Gen3R | `#cf9a21` |
| ChronoDepth | `#ce789f` |
| Marigold | `#8b909a` |
| UGG (Ours) | `#377bd4` |
| UGG (TTS) | `#8d68c8` |
| UGG (TTS Oracle) | `#5f3c83` |
| Full model (ablation) | `#244c80` |
| w/o RGB generation | `#944827` |
| w/o RE10K data | `#6c7a24` |
| Single transformer | `#199dab` |
| w/o depth prediction | `#a53d79` |
| Dense ray maps | `#967c55` |
| Global camera tokens | `#54505e` |
| w/o pose estimation | `#d04d20` |
| w_hist = 0 | `#eead83` |
| w_hist = 1 | `#83ba95` |
| w_hist = 2 | `#75a5df` |
| w_hist = 4 | `#b6a0cd` |

SEVA and Geo4D no longer share green. Repeated ablation variants, such as Single
transformer and Global camera tokens, retain their own colors across all panels.
The ablation Full model, each history-guidance setting, TTS and Oracle have separate
registry entries and colors rather than borrowing colors from the main methods.
Oracle retains its dashed outline; its assigned color is the outline color.

Color identifies a method or variant; **numeric bolding indicates the best
non-oracle result within its comparison block**, including ties. Color changes
must not modify values, precision, metric directions, ranking, or block membership.
Keep method labels and hover/focus descriptions available rather than relying on
color alone. Unique RGB values are not a guarantee of color-vision accessibility.

## Maintenance

After an intentional palette change or a new method, update the registry, this
reference and the explicit palette contract in the color regression test. Run:

```sh
node scripts/test-benchmark-colors.mjs
node scripts/test-benchmark-highlights.mjs
```

The color test rejects duplicate assignments, checks fixed identities in both bars
and legends across every setting/dataset filter and Oracle on/off, and verifies
that numerical labels and best-result classes are preserved. Browser checks should
also inspect computed fills, strokes and font weights in light and dark modes.
