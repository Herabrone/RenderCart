# ADR 0004: Audio denoising without model weights

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

The public audio noise-reduction tool needs to work commercially without distributing
model weights whose rights are unclear. DeepFilterNet's upstream repository dual-licenses
its code under MIT or Apache-2.0, but the license grant for released checkpoints is
ambiguous and has an open upstream question. Demucs' code is MIT, while upstream has not
clearly documented the commercial terms for its pretrained checkpoints. The upstream
questions are [DeepFilterNet #712](https://github.com/Rikorose/DeepFilterNet/issues/712)
and [Demucs #327](https://github.com/facebookresearch/demucs/issues/327). FFmpeg documents
the `afftdn` FFT denoiser in its [official filter manual](https://www.ffmpeg.org/ffmpeg-filters.html#afftdn).

## Decision

Implement public noise reduction with FFmpeg's built-in `afftdn` spectral filter in the
existing isolated CPU sandbox. Do not bundle DeepFilterNet or Demucs checkpoints unless
their commercial rights are explicitly established. The first release exposes a strength
control and MP3/WAV outputs; the UI describes steady-noise reduction and does not promise
speech restoration or studio-quality source separation.

Charge two credits per started ten-minute band for Pro/day-pass work and enforce the
existing one-job-per-day guest/free allowance. Keep the vocal-removal / four-stem tool
unimplemented until a suitable model has clear commercial rights or the owner approves a
different licensing decision.

## Consequences

- The denoiser has no model download, GPU memory, or additional Python dependency.
- Output quality is lower than a neural speech-enhancement model and works best on steady
  background noise.
- FFmpeg's package/build license and notices remain subject to the production image audit
  recorded in `docs/licenses.md`.
- A future licensed model can be added behind the same registry manifest without changing
  the pricing contract.
