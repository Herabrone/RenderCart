This directory vendors the inference modules from Kokoro 0.9.4 by hexgrad under Apache-2.0.

Upstream: https://github.com/hexgrad/kokoro/tree/v0.9.4

RenderCart changes: the optional eSpeak/GPL phonemizer import and multilingual path are
removed. Public TTS uses the upstream Misaki English G2P implementation with no eSpeak fallback.
