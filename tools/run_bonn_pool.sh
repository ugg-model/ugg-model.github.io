#!/bin/bash
# Bonn sample pool from the RELEASE checkpoint, via the canonical runner.
# Pool axes follow the ScanNet++ recipe: seed x hist_guidance x sample_steps.
# frame_mode=contig_first matches the existing bonn dense cells (frames.json = 0..49).
cd /n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/video_world_model_new || exit 1
export INFER_DIT_BF16=1
export HF_HOME=/n/netscratch/ydu_lab/Lab/akiruga
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
CK=/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final_release_checkpoints/spdepth_2250_NVS25.7263_BEST.ckpt
ALGO=wan_t2v_ray_depth_mot_concat_5b
PY=/n/lab_storage/ydu_lab/akiruga/.conda/envs/test2/bin/python3
OUT=/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/bonn_pool
LOG=/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/tools/logs
mkdir -p "$OUT" "$LOG"

MEMBERS=()
for sd in 400 401 402; do for hg in 0.5 1.0 1.5; do for st in 25 40 60; do
  MEMBERS+=("$sd:$hg:$st")
done; done; done          # 27 members

worker() {                 # $1 = gpu id, $2 = stride offset
  local gpu=$1 off=$2 i=0
  for m in "${MEMBERS[@]}"; do
    if [ $(( i % 2 )) -eq "$off" ]; then
      IFS=: read -r sd hg st <<< "$m"
      TAG="rel2250_sd${sd}_hg${hg}_st${st}"
      if [ -d "$OUT/$TAG/bonn" ] && [ "$(ls "$OUT/$TAG/bonn" 2>/dev/null | wc -l)" -gt 0 ]; then
        echo "[gpu$gpu] SKIP $TAG"; i=$((i+1)); continue
      fi
      echo "[gpu$gpu] START $TAG"
      CUDA_VISIBLE_DEVICES=$gpu $PY eval_pi3/run_ours_pi3.py \
        --ckpt_path "$CK" --algorithm "$ALGO" --model "$TAG" \
        --dataset bonn --dataset_cfg pi3seq_bonn \
        --output_dir "$OUT" \
        --height 288 --width 384 \
        --sample_steps "$st" --hist_guidance "$hg" --lang_guidance 0.0 \
        --frame_cap 50 --frame_mode contig_first --seed "$sd" \
        > "$LOG/pool_${TAG}.log" 2>&1
      echo "[gpu$gpu] DONE $TAG exit=$?"
    fi
    i=$((i+1))
  done
}
worker 0 0 & worker 1 1 &
wait
echo "POOL COMPLETE"
