#!/bin/bash
#SBATCH --job-name=fuxi-climo-merge
#SBATCH --partition=gpu
#SBATCH --exclude=cn2,cn3,cn4,cn15,cn16,cn17
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/storage/raj.ayush/s2s_final_data/final_iteration/model-runs/fuxi/native_reforecast_full_year_2002_2021/logs/combine-%j.log
set -euo pipefail
export OPENBLAS_NUM_THREADS=1
/home/raj.ayush/.conda/envs/s2s-hind/bin/python -u /storage/raj.ayush/s2s_final_data/final_iteration/model-runs/fuxi/native_reforecast_full_year_2002_2021/runtime/scripts/build_full_year_climatology.py combine
