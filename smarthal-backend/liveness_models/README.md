# Liveness models (anti-spoofing)

`liveness.py` uses these two files to tell a real face from a photo or a phone screen:

| File | Crop around the face | Original |
|---|---|---|
| `minifasnet_v2_scale2.7.onnx` | 2.7 × the face box, resized to 80 × 80 | `2.7_80x80_MiniFASNetV2.pth` |
| `minifasnet_v1se_scale4.0.onnx` | 4 × the face box, resized to 80 × 80 | `4_0_0_80x80_MiniFASNetV1SE.pth` |

They are **MiniFASNet** models from [Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing) by Minivision, licensed under the **Apache License 2.0**, converted from PyTorch to ONNX without changes to the trained weights. To recreate them, see `tools/convert_liveness_models.py`.

Each model outputs three scores (fake 2D, real, fake 3D). `liveness.py` averages the two models' "real" scores.

## License notice

Copyright Minivision. Licensed under the Apache License, Version 2.0 (the "License"); you may not use these files except in compliance with the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0. Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
