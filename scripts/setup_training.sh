#!/usr/bin/env bash
set -euo pipefail

# Reproducible CUDA training setup for the IndicF5 commit used by Vāgdhenu.
# Run inside an activated Python 3.10 virtual environment.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m pip install torch==2.4.1 torchaudio==2.4.1 \
  --index-url https://download.pytorch.org/whl/cu121

# Install the ordinary requirements without the IndicF5 VCS package or
# x-transformers. x-transformers 2.19.7 now resolves torch-einops-utils 0.0.34,
# whose package metadata asks for torch>=2.5 and would silently replace the
# project's validated 2.4.1+cu121 stack. The code path used by pinned IndicF5 is
# compatible; install that pair without asking pip to re-resolve torch.
REQ_TMP="$(mktemp)"
trap 'rm -f "$REQ_TMP"' EXIT
grep -vE '^(git\+https://github.com/ai4bharat/IndicF5|x-transformers==)' \
  requirements.txt > "$REQ_TMP"
python -m pip install -r "$REQ_TMP"
python -m pip install einops==0.8.1 einx loguru packaging
python -m pip install --no-deps torch-einops-utils==0.0.34
python -m pip install --no-deps x-transformers==2.19.7
python -m pip install --no-deps \
  'git+https://github.com/ai4bharat/IndicF5.git@13f7c4d627cc10111aea8fe9c0039462cacacdc7'

# IndicF5's setup.py declares additional runtime dependencies. Most arrive via
# the packages above; install the remaining training dependencies explicitly.
python -m pip install \
  cached_path click datasets==2.21.0 pyarrow==17.0.0 ema_pytorch hydra-core jieba matplotlib pydub \
  pypinyin safetensors tomli torchdiffeq tqdm transformers_stream_generator wandb

if [ ! -d BigVGAN/.git ]; then
  git clone --depth 1 https://github.com/NVIDIA/BigVGAN.git BigVGAN
fi
python scripts/download_weights.py

python - <<'PY'
import torch, torchaudio
import f5_tts
print("torch", torch.__version__, "cuda", torch.version.cuda)
print("torchaudio", torchaudio.__version__)
print("cuda_available", torch.cuda.is_available(), "gpus", torch.cuda.device_count())
print("f5_tts", f5_tts.__file__)
assert torch.__version__.startswith("2.4.1")
assert torch.cuda.is_available()
PY

echo "Training environment ready. Add $ROOT/BigVGAN to PYTHONPATH for rendering."
