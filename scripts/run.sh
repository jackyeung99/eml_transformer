#!/bin/bash
#SBATCH -J ingestion
#SBATCH -A r01850
#SBATCH --export=ALL
#SBATCH --nodes=1
#SBATCH -o=logs/run_%j.txt
#SBATCH -e=logs/run_%j.err
#SBATCH --gpus=1
#SBATCH --cpus-per-task=10
#SBATCH --mem=120G
#SBATCH --time=20:00:00
#SBATCH --mail-user=jayeun@iu.edu
#SBATCH --mail-type=BEGIN,FAIL,END
#SBATCH --partition=gpu

set -euo pipefail

export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export UV_CACHE_DIR=/N/project/eml_ai_forecasting/.uv-cache

cd /N/project/eml_ai_forecasting/eml_transformer

uv run --frozen python -m eml_transformer.cli run_all \
    --config configs/dev.yaml

# Schedule the next run only if this run succeeded.
sbatch --begin=now+12hours \
    /N/project/eml_ai_forecasting/eml_transformer/scripts/run.sh