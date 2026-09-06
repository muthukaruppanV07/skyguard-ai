# ISL_GRAMMAR.md — Grammar rules for gloss→English NLG

Used by the labeling tool (as the labeler's cheat sheet) and, in increment (f), by the
rule-based NLG layer. These rules are *observed ISL conventions* — the labeler records
what the signer actually signed; the **English sentence** is the NLG target.

## Core facts about ISL (Indian Sign Language)

- **Placement** is regional and community-based; dialect matters more than in ASL.
- Word order is predominantly **OSV** (Object → Subject → Verb).
  - ASL-ish example: sign RATION-CARD + MINE + WANT → "I want my ration card."
- **No copula** (no "is/are/am"); adjectives and predicates attach directly.
  - "Fever I" means "I have a fever" (possession usually signed, not stated).
- **Non-manual markers carry grammar**: raised brows = yes/no question, head tilt +
  furrowed brows = wh-question, negation by headshake (may occur with a manual "no" sign),
  conditional gaze/shoulder movement.
- **Fingerspelling** is used for proper nouns, English words, names, and new terms
  (A-A-D-H-A-A-R, KOVID). Fingerspelling rate is lower than ASL; signers prefer describers
  where possible.
- **2-handed signs are the norm** (unlike ASL which is predominantly 1-handed). Both
  hands matter; one hand is the "weak" hand (often static place-holder) and one the
  "strong" hand. The weak hand is a **cue**: 2-handed dominance + weak-hand placement
  (chest, palm, arm) distinguishes many minimal pairs.

## OSV mapping templates (NLG targets in increment f)

Gloss forms are stored as hyphenated **ISL glosses** in signing order; `english` is the
target sentence.

| ISL gloss (OSV) | English sentence |
| --- | --- |
| `ration-card mine need` | I need my ration card. |
| `fever I have` | I have a fever. |
| `token where` | Where is the token counter? |
| `petition judge file` | I want to file a petition before the judge. |
| `bail lawyer arrange` | The lawyer will arrange bail. |
| `A-D-H-A-A-R number give` | Please give me your Aadhaar number. |
| `medicine pharmacy buy` | I need to buy medicine from the pharmacy. |
| `referral doctor give` | The doctor gave me a referral. |
| `pain-head tablet eat` | I have a headache and need a tablet. |
| `sign here you` | Please sign here. |

## Labeling instruction (labeler cheat sheet — shown in the tool)

1. **Gloss** the signs in *signing order* (hyphenated): `card-ration mine need`.
2. Provide the **English sentence** that the signing means — NOT a word-for-word loan
   translation (no copula, no articles), but the natural service utterance.
3. Tag **region/dialect** and, if relevant, note the variant in `regional_variants`.
4. Mark **fingerspelled** words explicitly (proper nouns / English terms).
5. If the clip has low-confidence or ambiguous signing, set confidence low and flag;
   the phrase-reconstruction rule set in increment (f) will ask the user to repeat.

## Question formation (needed by the state machine)

- Yes/No: raised brows on the whole clause; answer signed with head nod / "yes".
  - Example: `ration-card you have` (raised brows) → "Do you have your ration card?"
- Wh-questions: `who/what/where/how-much` sign + furrowed brows.
  - Example: `quota how-much` → "How much is your quota?"

## Negation

- Manual "no" sign often co-occurs with headshake. Negation is clause-level, not verb-level:
  - `card fake I no` → "That is not my card." / "I do not have a card."
- The NLG layer must scope negation to the right constituent when reconstructing English.

## Use in the system

- **Increment (f)** will implement these as constrained-NLG templates + slot-fillers per
  domain (intake → verification → request → resolution), so the kiosk can drive dialogue.
- Confidence below a threshold (e.g., top-gloss consensus < 0.6) triggers a
  "please repeat" turn rather than a guessed sentence. **No hallucinated output in
  court/hospital contexts.**