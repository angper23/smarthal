"""One-time conversion of the MiniFASNet liveness models from PyTorch to ONNX.

Only needed if liveness_models/*.onnx have to be recreated; the converted files
are committed, so normal setup never runs this. Needs PyTorch, which SmartHal
itself doesn't use, so run it in a throwaway environment:

    python3 -m venv /tmp/convert-env
    /tmp/convert-env/bin/pip install torch onnx onnxruntime numpy
    git clone --depth 1 https://github.com/minivision-ai/Silent-Face-Anti-Spoofing.git /tmp/silentface
    /tmp/convert-env/bin/python tools/convert_liveness_models.py /tmp/silentface

The weight files are opened with torch.load(weights_only=True), which only reads
numbers and refuses anything that would run code. Each converted model is
checked against the original on random inputs before it's saved.
"""
import collections
import os
import sys

import numpy as np
import onnxruntime as ort
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "liveness_models")

# (original weights file, model class name, our ONNX file name)
MODELS = (
    ("2.7_80x80_MiniFASNetV2.pth", "MiniFASNetV2", "minifasnet_v2_scale2.7.onnx"),
    ("4_0_0_80x80_MiniFASNetV1SE.pth", "MiniFASNetV1SE", "minifasnet_v1se_scale4.0.onnx"),
)


def main(repo):
    """Convert both models from a checkout of Silent-Face-Anti-Spoofing at `repo`."""
    sys.path.insert(0, repo)
    from src.model_lib import MiniFASNet  # the model's layer definitions (no weights)
    from src.utility import get_kernel

    os.makedirs(OUT_DIR, exist_ok=True)
    for weights, cls_name, out in MODELS:
        model = getattr(MiniFASNet, cls_name)(conv6_kernel=get_kernel(80, 80))
        state = torch.load(os.path.join(repo, "resources", "anti_spoof_models", weights),
                           map_location="cpu", weights_only=True)
        state = collections.OrderedDict((k[7:] if k.startswith("module.") else k, v) for k, v in state.items())
        model.load_state_dict(state)
        model.eval()

        path = os.path.join(OUT_DIR, out)
        torch.onnx.export(model, torch.rand(1, 3, 80, 80) * 255, path, input_names=["input"],
                          output_names=["logits"], opset_version=13,
                          dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}}, dynamo=False)

        session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        worst = 0.0
        for _ in range(10):
            x = torch.rand(1, 3, 80, 80) * 255
            with torch.no_grad():
                expected = torch.softmax(model(x), 1).numpy()
            logits = session.run(None, {"input": x.numpy()})[0]
            e = np.exp(logits - logits.max(1, keepdims=True))
            worst = max(worst, float(np.abs(e / e.sum(1, keepdims=True) - expected).max()))
        if worst > 1e-4:
            os.remove(path)
            sys.exit(f"{out}: ONNX output differs from PyTorch by {worst:.1e}; not saved")
        print(f"{out}: {os.path.getsize(path) / 1e6:.2f} MB, matches PyTorch (max difference {worst:.1e})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
