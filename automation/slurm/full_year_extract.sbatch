#!/bin/bash
#SBATCH --job-name=fuxi-full-climo
#SBATCH --array=0-104%24
#SBATCH --partition=gpu
#SBATCH --exclude=cn2,cn3,cn4,cn15,cn16,cn17
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=/storage/raj.ayush/s2s_final_data/final_iteration/model-runs/fuxi/native_reforecast_full_year_2002_2021/logs/extract-%A_%a.log
set -euo pipefail
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=1
/home/raj.ayush/.conda/envs/s2s-hind/bin/python -u /storage/raj.ayush/s2s_final_data/final_iteration/model-runs/fuxi/native_reforecast_full_year_2002_2021/runtime/scripts/build_full_year_climatology.py extract --slot-index "$SLURM_ARRAY_TASK_ID"
