# labeling/

Web-based annotation workbench for the BhashaSetu ISL corpus. Zero external
Python dependencies (stdlib only) so it runs offline on a field laptop.

## Layout

| Path | Purpose |
| --- | --- |
| `backend/store.py`      | Append-only JSONL stores (samples, labels, qa, consent) + audit log |
| `backend/consensus.py`  | Multi-annotator voting logic (agreed / ambiguous / needs_voting) |
| `backend/glossary.py`   | Namespace-aware glossary loading + autocomplete |
| `backend/manifest.py`   | Versioned manifest export with sha256 checksums |
| `backend/server.py`     | HTTP API + static SPA server (localhost-friendly, offline) |
| `frontend/`             | SPA: keypoint overlay playback, annotation, voting, QA, consent, stats |
| `scripts/`              | `build_glossaries.py`, `make_synthetic_keypoints.py`, `seed_demo.py` |

## API summary (all under `/api`, JSON)

- `GET /config`, `/glossaries[/{domain}[/search?q=]]`, `/samples?domain=&status=`,
  `/samples/{id}`, `/samples/{id}/keypoints`, `/consent/{signer}`, `/stats`,
  `/manifests`
- `POST /samples` (register), `/samples/{id}/labels`, `/samples/{id}/qa`,
  `/consent`, `/consent/withdraw`, `/export` (build manifest)

## Data flow

```
sourced/recorded clip ──► register (provenance + dialect) ──► keypoints (inc b)
        ──► >=2 annotators vote ──► consensus ──► QA gate ──► manifest export
```
A sample is **eligible for a manifest** only when consent granted + consensus
agreed + QA passed + (increment b) valid keypoints. See `docs/CONSENT.md` and
`data/README.md`.

## Verify

```powershell
python -m unittest discover -s labeling/backend -p "test_*.py" -v   # 36 tests
node --check labeling/frontend/app.js                                # JS syntax
```