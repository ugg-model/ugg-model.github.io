/* UGG, Tables 1–4 (manuscript pages 7–10). Values are transcribed, not estimated.
 * Row values are dataset-major, then metric-major. Keep the manuscript precision.
 * The charts, full tables and CSV all use this single data source.
 */
(() => {
  'use strict';
  const rows = text => text.trim().split('\n').map(line => {
    const [method, numbers] = line.trim().split('|');
    return { method, values: numbers.trim().split(/\s+/).map(Number) };
  });
  const metric = (key, label, direction, digits) => ({ key, label, direction, digits });
  const generationMetrics = [metric('psnr', 'PSNR (dB)', 'up', 2), metric('lpips', 'LPIPS', 'down', 3), metric('ssim', 'SSIM', 'up', 3)];
  const depthMetrics = [metric('rel', 'Abs Rel', 'down', 3), metric('delta', 'δ < 1.25', 'up', 3)];
  const poseMetrics = [metric('ate', 'ATE', 'down', 3), metric('rpet', 'RPEₜ', 'down', 3), metric('rper', 'RPEᵣ (°)', 'down', 3)];
  const generationSets = ['RealEstate10K', 'SpatialVID', 'DL3DV'];
  const poseSets = ['RealEstate10K', 'Sintel', 'TUM', 'ScanNetV2', 'ScanNet++'];
  const depthSets = ['ScanNet++', '7-Scenes', 'KITTI', 'Sintel', 'Bonn'];
  window.UGG_BENCHMARKS = {
    source: {
      title: 'UGG: Unified Generative Geometry Model',
      file: '4D_World_Model__NeurIPS_2026.zip',
      sha256: 'fc99c4a2a17e86f22b6b36a9bf8dfca7b83711f0f0eda19fe87d3e505967386f',
      note: 'Transcribed from the manuscript source in that archive: tables/final_nvs_table.tex, final_pose_table.tex, final_depth_table.tex and ablations.tex.',
      tables: '1–4', valueCount: 428
    },
    // One fixed, globally unique color per method / variant. Never recycle colors
    // by chart position; legends and bars both read this registry. See COLORS.md.
    methods: {
      aether: { label: 'Aether', color: '#e47739' },
      seva: { label: 'SEVA', color: '#bd4147' },
      geo4d: { label: 'Geo4D', color: '#20996d' },
      gen3r: { label: 'Gen3R', color: '#cf9a21' },
      chrono: { label: 'ChronoDepth', color: '#ce789f' },
      marigold: { label: 'Marigold', color: '#8b909a' },
      ugg: { label: 'UGG (Ours)', color: '#377bd4', kind: 'ours' },
      tts: { label: 'UGG (TTS)', color: '#8d68c8', kind: 'ours' },
      oracle: { label: 'UGG (TTS Oracle)', color: '#5f3c83', kind: 'oracle' },
      full: { label: 'Full model', color: '#244c80', kind: 'ours' },
      'no-rgb': { label: 'w/o RGB generation', color: '#944827' },
      'no-re10k': { label: 'w/o RE10K data', color: '#6c7a24' },
      single: { label: 'Single transformer', color: '#199dab' },
      'no-depth': { label: 'w/o depth prediction', color: '#a53d79' },
      'dense-rays': { label: 'Dense ray maps', color: '#967c55' },
      'global-camera': { label: 'Global camera tokens', color: '#54505e' },
      'no-pose': { label: 'w/o pose estimation', color: '#d04d20' },
      w0: { label: 'w_hist = 0', color: '#eead83' },
      w1: { label: 'w_hist = 1', color: '#83ba95' },
      w2: { label: 'w_hist = 2', color: '#75a5df' },
      w4: { label: 'w_hist = 4', color: '#b6a0cd' }
    },
    tasks: [
      { key: 'generation', label: 'Generation', title: 'Camera-controlled generation', page: 7,
        note: 'Observed RGB frame(s) and the target camera trajectory condition the generated video. PSNR and SSIM: higher is better. LPIPS: lower is better.',
        settings: [
          { key: 'two-view', label: '2-view', caption: 'First and last RGB frames + camera trajectory', table: '1', datasets: generationSets, metrics: generationMetrics,
            rows: rows(`
              aether|20.02 0.196 0.624 13.84 0.489 0.334 13.14 0.399 0.243
              seva|25.25 0.081 0.838 15.44 0.344 0.466 17.61 0.211 0.552
              ugg|25.73 0.061 0.849 16.99 0.288 0.535 16.61 0.239 0.495`) },
          { key: 'one-view', label: '1-view', caption: 'First RGB frame + camera trajectory', table: '1', datasets: generationSets, metrics: generationMetrics,
            rows: rows(`
              aether|15.79 0.335 0.469 11.81 0.632 0.283 11.96 0.506 0.240
              seva|19.58 0.194 0.703 13.35 0.472 0.343 13.50 0.393 0.335
              ugg|21.79 0.150 0.779 14.86 0.428 0.405 13.92 0.385 0.346`) }
        ] },
      { key: 'pose', label: 'Camera Pose', title: 'Camera pose estimation', page: 8,
        note: 'Dense trajectories use Sim(3) Umeyama alignment. Sparse evaluation scores only the two observed frames, with translation angular error (tAE) and rotational RPE, not ATE or translation RPE. UGG uses shared intrinsics. TTS selects among candidates at inference; TTS Oracle is a separate reference, not a selectable method. All errors: lower is better.',
        settings: [
          { key: 'dense', label: 'Dense', caption: 'Full RGB sequence observed · ATE / RPEₜ / RPEᵣ', table: '2', datasets: poseSets, metrics: poseMetrics,
            rows: rows(`
              geo4d|0.026 0.028 0.147 0.160 0.097 0.911 0.052 0.029 1.414 0.074 0.044 1.762 0.190 0.090 5.591
              gen3r|0.030 0.011 0.141 0.233 0.066 1.538 0.046 0.016 0.943 0.075 0.024 1.018 0.232 0.066 5.760
              aether|0.018 0.014 0.851 0.180 0.867 1.354 0.041 0.016 1.462 0.075 0.030 1.617 0.225 0.068 5.944
              ugg|0.010 0.004 0.076 0.098 0.034 0.708 0.018 0.007 1.052 0.038 0.016 0.938 0.087 0.036 3.861
              tts|0.009 0.004 0.076 0.091 0.033 0.684 0.017 0.007 1.054 0.038 0.016 0.937 0.082 0.035 4.105
              oracle|0.008 0.004 0.076 0.072 0.030 0.695 0.015 0.006 1.053 0.033 0.015 0.939 0.072 0.035 4.078`) },
          { key: 'sparse', label: 'Sparse', caption: 'First and last RGB frames observed · tAE / RPEᵣ', table: '2', datasets: poseSets,
            metrics: [metric('tae', 'tAE', 'down', 3), metric('rper', 'RPEᵣ (°)', 'down', 3)],
            rows: rows(`
              geo4d|117.079 3.407 108.628 24.160 100.224 11.936 90.812 43.458 82.747 83.019
              gen3r|44.004 4.197 75.984 24.984 82.875 12.374 79.871 43.481 92.324 82.540
              aether|39.834 14.969 78.012 33.640 48.436 6.234 70.925 36.720 77.234 81.681
              ugg|8.260 1.287 35.479 22.065 9.938 1.371 28.240 21.417 40.194 43.078
              tts|3.475 1.393 18.733 20.646 8.520 1.444 20.057 18.911 31.835 37.875
              oracle|1.550 1.399 8.521 26.135 3.401 1.154 9.683 20.688 7.892 43.836`) }
        ] },
      { key: 'depth', label: 'Depth', title: 'Depth prediction', page: 9,
        note: 'Video-level scale and shift alignment. Abs Rel: lower is better; δ < 1.25: higher is better (fractions, not percentages). TTS selects from 16 candidates using RGB reprojection error; improvements are not uniform. TTS Oracle is shown only as a separate reference, not as the reprojection-selected method.',
        settings: [
          { key: 'dense', label: 'Dense', caption: 'Full RGB sequence observed', table: '3', datasets: depthSets, metrics: depthMetrics,
            rows: rows(`
              chrono|0.177 0.724 0.116 0.871 0.120 0.857 0.394 0.530 0.092 0.920
              geo4d|0.106 0.894 0.080 0.923 0.097 0.923 0.247 0.676 0.057 0.972
              gen3r|0.157 0.772 0.079 0.937 0.185 0.777 0.414 0.520 0.168 0.805
              aether|0.166 0.769 0.109 0.898 0.056 0.975 0.351 0.607 0.095 0.911
              marigold|0.175 0.730 0.094 0.910 0.098 0.910 0.388 0.517 0.082 0.933
              ugg|0.073 0.952 0.083 0.921 0.064 0.960 0.303 0.654 0.060 0.963
              tts|0.072 0.954 0.084 0.920 0.063 0.962 0.293 0.661 0.059 0.969
              oracle|0.063 0.963 0.074 0.923 0.055 0.967 0.263 0.692 0.056 0.973`) },
          { key: 'sparse', label: 'Sparse', caption: 'First and last RGB frames observed', table: '3', datasets: depthSets, metrics: depthMetrics,
            rows: rows(`
              chrono|0.199 0.700 0.130 0.844 0.089 0.905 0.424 0.487 0.072 0.960
              geo4d|0.177 0.737 0.098 0.912 0.100 0.897 0.310 0.554 0.067 0.966
              gen3r|0.238 0.620 0.124 0.867 0.104 0.888 0.347 0.510 0.127 0.847
              aether|0.269 0.567 0.167 0.772 0.149 0.786 0.487 0.424 0.138 0.849
              marigold|0.169 0.733 0.106 0.890 0.087 0.921 0.345 0.527 0.071 0.970
              ugg|0.101 0.884 0.087 0.916 0.099 0.917 0.258 0.660 0.049 0.977
              tts|0.082 0.917 0.086 0.916 0.087 0.934 0.219 0.678 0.047 0.979
              oracle|0.055 0.966 0.075 0.923 0.068 0.946 0.177 0.781 0.043 0.979`) }
        ] },
      { key: 'ablations', label: 'Ablations', title: 'Ablation studies', page: 10,
        note: 'Separate, matched-budget experiments: Wan2.1-1.3B fine-tuned on TartanAir and RE10K for 7,500 steps, batch size 8. These are not the main-benchmark checkpoints. In Table 4b, task/architecture and camera-representation comparisons are separate blocks; the full-model and dense-ray-map rows are kept distinct.',
        settings: [
          { key: 'depth', label: 'Depth', caption: 'Training tasks, heterogeneous data and architecture', table: '4a', datasets: ['Bonn', 'KITTI'], metrics: depthMetrics,
            rows: rows(`
              full|0.135 0.843 0.152 0.791
              no-rgb|0.178 0.782 0.322 0.486
              no-re10k|0.239 0.651 0.196 0.732
              single|0.129 0.870 0.248 0.640`) },
          { key: 'pose', label: 'Camera Pose', caption: 'Task / architecture and camera-representation comparisons', table: '4b', datasets: ['ScanNetV2', 'ScanNet++'],
            metrics: [metric('ate', 'ATE', 'down', 3), metric('rper', 'RPEᵣ (°)', 'down', 2)],
            blocks: [['full', 'no-depth', 'single'], ['dense-rays', 'global-camera']],
            rows: rows(`
              full|0.074 2.91 0.193 6.18
              no-depth|0.081 4.30 0.234 7.57
              single|0.083 3.02 0.204 6.60
              dense-rays|0.071 2.80 0.206 6.09
              global-camera|0.103 3.44 0.233 6.61`) },
          { key: 'generation', label: 'Generation', caption: 'Pose supervision, architecture and camera representation', table: '4c', datasets: generationSets, metrics: [generationMetrics[0]],
            rows: rows(`
              full|20.18 13.67 12.60
              no-pose|13.26 11.87 10.95
              single|19.68 12.75 11.61
              global-camera|20.03 12.89 11.64`) },
          { key: 'guidance', label: 'History Guidance', caption: 'History-guidance weight w_hist', table: '4d', datasets: ['ScanNetV2', 'ScanNet++'],
            metrics: [metric('ate', 'ATE', 'down', 4), metric('rper', 'RPEᵣ (°)', 'down', 2)],
            rows: rows(`
              w0|0.0796 2.46 0.2170 5.77
              w1|0.0741 2.83 0.2089 6.09
              w2|0.0740 3.24 0.2091 6.45
              w4|0.0765 4.22 0.2141 7.70`) }
        ] }
    ]
  };
})();
