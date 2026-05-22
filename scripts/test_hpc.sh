#!/bin/bash
#SBATCH -J test_job
#SBATCH -A r01850
#SBATCH --output=/N/project/eml_ai_forecasting/eml_transformer/logs/test_%j.out
#SBATCH --error=/N/project/eml_ai_forecasting/eml_transformer/logs/test_%j.err
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=2
#SBATCH --export=ALL

echo "JOB STARTED"
echo "Working directory:"
pwd

echo "Hostname:"
hostname

echo "Date:"
date

module load python/gpu/3.12.5

cd /N/project/eml_ai_forecasting/eml_transformer

echo "After cd:"
pwd

python --version

echo "JOB FINISHED"

echo "Resubmitting..."

sbatch --begin=now+2minutes \
    /N/project/eml_ai_forecasting/eml_transformer/scripts/test_hpc.sh