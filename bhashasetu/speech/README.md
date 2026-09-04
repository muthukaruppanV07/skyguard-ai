# speech/

ASR-inverse side of BhashaSetu: speak the reconstructed English sentence, and optionally
project a text-to-ISL avatar so the deaf user sees the system's reply in sign.

Planned (increments f–g):

| Path | Purpose |
| --- | --- |
| `./tts/` | Offline TTS — gTTS / piper / espeak-ng; must run edge (no cloud); voice for court/hospital register |
| `./avatar/` | Text-to-ISL avatar rendering English utterance back in ISL (OSV gloss sequence → animated signer) |
| `./dialogue/` | NLG + per-domain conversational state machine (intake → verification → request → resolution) |

Requirements carried from the brief:

- Fully offline; <300 ms latency budget on Raspberry Pi 4 / Android Go.
- Domain-aware NLG: gloss → grammatical English using `docs/ISL_GRAMMAR.md` templates.
- The spoken output always mirrors what was shown & confirmed on screen (explainability).

Nothing landed in this increment — see `docs/ISL_GRAMMAR.md` for the grammar rule set.