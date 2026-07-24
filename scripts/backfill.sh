#!/bin/bash
#SBATCH --job-name=gdelt-log-test
#SBATCH --account=r01850
#SBATCH --export=ALL
#SBATCH --nodes=1
#SBATCH --output=logs/gdelt_%j.log
#SBATCH --error=logs/gdelt_%j.log
#SBATCH --gpus=1
#SBATCH --cpus-per-task=10
#SBATCH --mem=120G
#SBATCH --time=01:00:00
#SBATCH --mail-user=jayeun@iu.edu
#SBATCH --mail-type=BEGIN,FAIL,END
#SBATCH --partition=gpu

set -euo pipefail

export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export UV_CACHE_DIR=/N/project/eml_ai_forecasting/.uv-cache
export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1

# Prevent tqdm from updating the log excessively.
export TQDM_MININTERVAL=10
export TQDM_POSITION=-1

cd /N/project/eml_ai_forecasting/eml_transformer

uv run --frozen python -u -m eml_transformer.cli backfill \
    --source gdelt \
    --from-date 2026-01-01 \
    --to-date 2026-06-20 \
    --config configs/dev.yaml