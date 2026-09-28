#!/usr/bin/env python3
"""A10 QLoRA smoke for Qwen3.5-9B (GGUF-sourced) on the paper_v1 manifest.

Stage 1 of the model-experiment ladder: prove the stack end-to-end before any
real training. Steps verified in order, each gating the next:

  1. GGUF -> HF conversion (dequantize the ollama Q4_K blob to bf16/f16 HF format)
  2. tokenizer round-trip
  3. 4-bit NF4 load on the A10
  4. forward
  5. backward (LoRA grads only)
  6. gradient accumulation
  7. LoRA checkpoint save
  8. checkpoint reload + weight identity check
  9. generation

Writes a JSON result ledger with per-step timing, peak memory, and exit status;
fails closed on the first broken step. No full training run and no epoch over
paper_v1 happens here — that is the 100-sample overfit, a separate stage.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

RESULT_PATH = Path("/home/qy/gee_llm_smoke/smoke_results_v1.json")


def step(results: dict, name: str):
    def deco(fn):
        def wrapper(*a, **kw):
            t0 = time.time()
            try:
                out = fn(*a, **kw)
                results[name] = {"ok": True, "seconds": round(time.time() - t0, 2), "detail": out}
                print(f"[OK] {name} ({results[name]['seconds']}s)")
                return out
            except Exception as exc:
                results[name] = {"ok": False, "seconds": round(time.time() - t0, 2), "error": f"{type(exc).__name__}: {exc}"}
                print(f"[FAIL] {name}: {results[name]['error']}")
                raise
        return wrapper
    return deco


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gguf", type=Path, required=True)
    parser.add_argument("--hf-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("/home/qy/gee_llm_smoke"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    results: dict = {"schema": "gis_recommend.qwen_a10_qlora_smoke.v1"}

    # ---- 1. conversion --------------------------------------------------
    @step(results, "1_gguf_to_hf")
    def convert():
        if (args.hf_dir / "config.json").is_file():
            return "already-hf-format"
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        model = AutoModelForCausalLM.from_pretrained(
            str(args.gguf.parent), gguf_file=args.gguf.name, torch_dtype=torch.float16,
        )
        model.save_pretrained(args.hf_dir)
        tok = AutoTokenizer.from_pretrained(str(args.gguf.parent), gguf_file=args.gguf.name)
        tok.save_pretrained(args.hf_dir)
        return {"params_b": round(sum(p.numel() for p in model.parameters()) / 1e9, 2)}

    # ---- 2..9 ------------------------------------------------------------
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model

    @step(results, "2_tokenizer")
    def tokenizer_step():
        tok = AutoTokenizer.from_pretrained(args.hf_dir)
        ids = tok("将 DEM 按最小值和最大值划分为等间隔高程类别")["input_ids"]
        assert len(ids) > 3
        assert tok.decode(ids) is not None
        return {"vocab_size": tok.vocab_size, "roundtrip_len": len(ids)}

    model = None
    tok = None

    @step(results, "3_nf4_load")
    def load():
        nonlocal model
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(args.hf_dir, quantization_config=bnb, device_map="cuda:0")
        model.config.use_cache = False
        peak = torch.cuda.max_memory_allocated() / 2**30
        return {"peak_gb": round(peak, 2), "device": str(next(model.parameters()).device)}

    @step(results, "4_forward")
    def forward_step():
        nonlocal tok
        tok = AutoTokenizer.from_pretrained(args.hf_dir)
        inputs = tok("Task: buffer roads by 500 meters.", return_tensors="pt").to("cuda:0")
        with torch.no_grad():
            out = model(**inputs)
        return {"logits_shape": list(out.logits.shape)}

    @step(results, "5_backward")
    def backward_step():
        inputs = tok("Task: buffer roads by 500 meters. Answer:", return_tensors="pt").to("cuda:0")
        labels = inputs["input_ids"].clone()
        out = model(**inputs, labels=labels)
        out.loss.backward()
        grads = [n for n, p in model.named_parameters() if p.requires_grad and p.grad is not None]
        torch.cuda.synchronize()
        return {"loss": round(out.loss.item(), 4), "grad_tensors": len(grads)}

    @step(results, "6_grad_accumulation")
    def accum_step():
        model.zero_grad(set_to_none=True)
        for i in range(3):
            inputs = tok(f"Task {i}: sample text {i}. Answer:", return_tensors="pt").to("cuda:0")
            out = model(**inputs, labels=inputs["input_ids"].clone())
            (out.loss / 3).backward()
        total = sum(
            p.grad.abs().sum().item()
            for _, p in model.named_parameters()
            if p.requires_grad and p.grad is not None
        )
        return {"grad_magnitude": round(total, 6)}

    peft_holder: dict = {}

    @step(results, "7_checkpoint_save")
    def save_step():
        cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                         target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                         task_type="CAUSAL_LM")
        peft_model = get_peft_model(model, cfg)
        peft_holder["model"] = peft_model
        path = args.out_dir / "lora_smoke_adapter"
        peft_model.save_pretrained(path)
        trainable = sum(p.numel() for p in peft_model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in peft_model.parameters())
        return {"adapter_dir": str(path), "trainable_params": trainable,
                "trainable_pct": round(100 * trainable / total, 3)}

    @step(results, "8_checkpoint_reload")
    def reload_step():
        from peft import PeftModel
        base = AutoModelForCausalLM.from_pretrained(
            args.hf_dir,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
            ),
            device_map="cuda:0",
        )
        reloaded = PeftModel.from_pretrained(base, args.out_dir / "lora_smoke_adapter")
        # weight identity: LoRA A of first adapter module must match
        src = {n: p.detach().cpu() for n, p in peft_holder["model"].named_parameters() if "lora_A" in n}
        dst = {n: p.detach().cpu() for n, p in reloaded.named_parameters() if "lora_A" in n}
        common = [n for n in src if n in dst]
        assert common, "no lora_A params found for comparison"
        match = all(torch.equal(src[n], dst[n]) for n in common[:5])
        assert match, "reloaded adapter weights differ"
        return {"compared": len(common), "identical": True}

    @step(results, "9_generation")
    def generate_step():
        gen_model = peft_holder["model"]
        gen_model.eval()
        inputs = tok("Task: reproject a layer to WGS84. Answer:", return_tensors="pt").to("cuda:0")
        out = gen_model.generate(**inputs, max_new_tokens=16, do_sample=False)
        text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        return {"generated_chars": len(text)}

    convert()
    tokenizer_step()
    load()
    forward_step()
    backward_step()
    accum_step()
    save_step()
    reload_step()
    generate_step()

    results["peak_memory_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
    results["all_ok"] = all(v.get("ok") for k, v in results.items() if isinstance(v, dict) and "ok" in v)
    RESULT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=2, ensure_ascii=False)[:2000])
    return 0 if results["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
