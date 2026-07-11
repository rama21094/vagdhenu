"""Fine-tune IndicF5 (F5/flow-matching) on pilot_reciter 5h. Warm-start from the GRN-corrected
checkpoint loaded directly into the CFM. DDP via `accelerate launch --multi_gpu`."""
import argparse, os, random, torch
from f5_tts.infer.utils_infer import load_model
from f5_tts.model import DiT, Trainer
from f5_tts.model.dataset import load_dataset


def _load_state(path):
    """Load base safetensors or F5 Trainer checkpoints into a plain CFM state dict."""
    if path.endswith(".safetensors"):
        from safetensors.torch import load_file
        raw = load_file(path, device="cpu")
    else:
        raw = torch.load(path, map_location="cpu", weights_only=True)
    if "ema_model_state_dict" in raw:
        raw = raw["ema_model_state_dict"]
    elif "model_state_dict" in raw:
        raw = raw["model_state_dict"]
    elif "model" in raw and isinstance(raw["model"], dict):
        raw = raw["model"]
    return {k: v for k, v in raw.items() if k not in ("initted", "step")}


def _normalize_state(raw, target):
    """Remove EMA/compile prefixes and bridge the pinned IndicF5 GRN rename."""
    normalized = {}
    for key, value in raw.items():
        while key.startswith("ema_model."):
            key = key[len("ema_model."):]
        while key.startswith("_orig_mod."):
            key = key[len("_orig_mod."):]
        if key not in target and ".grn.weight" in key:
            candidate = key.replace(".grn.weight", ".grn.gamma")
            if candidate in target:
                key = candidate
        if key not in target and ".grn.bias" in key:
            candidate = key.replace(".grn.bias", ".grn.beta")
            if candidate in target:
                key = candidate
        if key in target and target[key].shape == value.shape:
            normalized[key] = value
    return normalized

ap = argparse.ArgumentParser()
ap.add_argument("--vocab", required=True)
ap.add_argument("--warm", required=True)
ap.add_argument("--data_dir", required=True)
ap.add_argument("--save_dir", required=True)
ap.add_argument("--wandb_name", required=True)
ap.add_argument("--epochs", type=int, default=600)
ap.add_argument("--lr", type=float, default=1e-5)
ap.add_argument("--bs", type=int, default=19200)
ap.add_argument("--bstype", default="frame")
ap.add_argument("--warmup", type=int, default=500)
ap.add_argument("--save_per", type=int, default=2000)
ap.add_argument("--max_samples", type=int, default=64)
ap.add_argument("--logger", choices=("wandb", "none"), default="none")
ap.add_argument("--seed", type=int, default=1337)
a = ap.parse_args()

random.seed(a.seed); torch.manual_seed(a.seed)
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

CFG = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
cfm = load_model(DiT, CFG, mel_spec_type="vocos", vocab_file=a.vocab, device="cpu")
sd = _normalize_state(_load_state(a.warm), cfm.state_dict())
miss, unexp = cfm.load_state_dict(sd, strict=False)
missing_model = [m for m in miss if "mel_spec" not in m]
loaded_fraction = len(sd) / max(1, len([k for k in cfm.state_dict() if "mel_spec" not in k]))
print("[warm-start] loaded:", len(sd), f"({loaded_fraction:.1%})",
      "| missing(non-melspec):", len(missing_model), "| unexpected:", len(unexp), flush=True)
if loaded_fraction < 0.95 or missing_model:
    print("[warm-start] missing keys:", missing_model[:20], flush=True)
    raise RuntimeError("warm checkpoint did not cover the complete non-melspec model")

trainer = Trainer(
    cfm, epochs=a.epochs, learning_rate=a.lr,
    num_warmup_updates=a.warmup, save_per_updates=a.save_per, last_per_steps=a.save_per,
    checkpoint_path=a.save_dir, batch_size=a.bs, batch_size_type=a.bstype, max_samples=a.max_samples,
    grad_accumulation_steps=1, max_grad_norm=1.0,
    logger=None if a.logger == "none" else "wandb",
    wandb_project="indicf5-sanskrit", wandb_run_name=a.wandb_name,
                             mel_spec_type="vocos", log_samples=False,
)
MELKW = dict(n_fft=1024, hop_length=256, win_length=1024, n_mel_channels=100,
             target_sample_rate=24000, mel_spec_type="vocos")
train_dataset = load_dataset("indicf5", "custom", dataset_type="CustomDatasetPath",
                             mel_spec_kwargs=MELKW, data_dir=a.data_dir)
trainer.train(train_dataset)
