# deploy/

Edge runtime for BhashaSetu government-service kiosks. Planned (increments e–g).

| Path | Purpose |
| --- | --- |
| `./runtime/` | Python/ONNX runtime entrypoint; camera loop → keypoints → model → NLG → TTS |
| `./quant/` | TFLite/ONNX quantization (4-bit weights, FP16 activations) for Raspberry Pi 4 / Android Go |
| `./degrade/` | Graceful degradation: cached models, queued logs + anonymized correction upload when online |

Environment handling carried into this increment:

- **Background subtraction / person tracking** — read signs from the correct person;
  distance-adaptive cropping; low-light compensation (planned in the camera pipeline).
- **Latency budget < 300 ms**, fully on-device; no video leaves the device.
- **Audit log**: every session (timestamp, anonymized signer ID, gloss, output,
  confidence) for court/legal record.

Runtimes will be verified on target hardware (Pi 4 / Android Go kiosk) before each
release. Nothing landed in this increment.