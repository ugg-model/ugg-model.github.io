#!/bin/bash
#SBATCH -J relpool
#SBATCH --gres=gpu:1
#SBATCH --constraint="h100|h200"
#SBATCH -c 8
#SBATCH --mem=96G
#SBATCH -t 02:00:00
#SBATCH -o /n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/tools/logs/relpool_%A_%a.log
# h100|h200 is mandatory: Blackwell nodes hang on the Isilon pi3 data used by
# sintel/bonn/kitti. REPO hardcoded; $(dirname $0) in sbatch is the slurmd spool.
REPO=/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/video_world_model_new
T=/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/tools
OUT=/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/release_pool
CK=/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final_release_checkpoints/spdepth_2250_NVS25.7263_BEST.ckpt
PY=/n/lab_storage/ydu_lab/akiruga/.conda/envs/test2/bin/python3
export INFER_DIT_BF16=1 HF_HOME=/n/netscratch/ydu_lab/Lab/akiruga PYTORCH_ALLOC_CONF=expandable_segments:True
LINE=$(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" "$T/joblist.tsv")
[ -z "$LINE" ] && { echo "no job for task $SLURM_ARRAY_TASK_ID"; exit 0; }
IFS=$'\t' read -r DS CFG SD HG ST <<< "$LINE"
TAG="rel2250_sd${SD}_hg${HG}_st${ST}"
if [ -d "$OUT/$TAG/$DS" ] && [ "$(ls "$OUT/$TAG/$DS" 2>/dev/null | wc -l)" -gt 0 ]; then
  echo "SKIP $TAG/$DS (already present)"; exit 0
fi
cd "$REPO" || exit 1
echo "START $DS $TAG"
"$PY" eval_pi3/run_ours_pi3.py \
  --ckpt_path "$CK" --algorithm wan_t2v_ray_depth_mot_concat_5b --model "$TAG" \
  --dataset "$DS" --dataset_cfg "$CFG" --output_dir "$OUT" \
  --height 288 --width 384 \
  --sample_steps "$ST" --hist_guidance "$HG" --lang_guidance 0.0 \
  --frame_cap 50 --frame_mode contig_first --seed "$SD"
rc=$?
echo "EXIT_STATUS=$rc"
exit $rc
