"""Build + validate domain glossaries for BhashaSetu.

Generates data/glossaries/{pds,health,legal}.json from this seed module, then runs
schema validation (unique ids/glosses, valid categories, valid region codes).

Usage:
    python labeling/scripts/build_glossaries.py [--check]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _e(id_, gloss, english, category, aliases=None, fingerspelled=False,
       sign_notes="", regional_variants=None, source_ref="community", verified=False):
    return {
        "id": id_, "gloss": gloss, "english": english, "category": category,
        "aliases": aliases or [], "fingerspelled": fingerspelled,
        "sign_notes": sign_notes, "regional_variants": regional_variants or [],
        "source_ref": source_ref, "verified": verified,
    }


PDS_GLOSSES = [
    # --- documents ---
    _e("pds_001", "ration-card", "ration card", "document", ["ration"],
       False, "2-handed: flat B-hands, thumbs placed against chest like a card; region variants differ in placement",
       [{"region": "mumbai", "note": "card at chest level, slight forward tap"}], "islrtc"),
    _e("pds_002", "aadhaar", "Aadhaar (unique ID)", "document", ["A-D-H-A-A-R", "uid"],
       True, "Often fingerspelled A-D-H-A-A-R; some regions point to forehead (identity) then sign NUMBER",
       [{"region": "chennai", "note": "point-to-forehead + NUMBER is common"}], "community"),
    _e("pds_003", "voter-id", "EPIC / voter ID", "document", ["election-card", "epic"],
       False, "Handshape imitates a card with a photo; often signed as PHOTO-CARD", [], "islrtc"),
    _e("pds_004", "bank-passbook", "bank passbook", "document", ["passbook"],
       False, "Open-book motion of both flat hands from centre to sides", [], "islrtc"),
    _e("pds_005", "income-certificate", "income certificate", "document", ["income-cert"],
       False, "Certificate (paper with seal) + MONEY-motion sequence", [], "community"),
    _e("pds_006", "caste-certificate", "caste certificate", "document", [],
       False, "Certificate + manual category marking; verify per region", [], "community"),
    _e("pds_007", "residence-proof", "residence proof", "document", ["address-proof"],
       False, "HOUSE + proof/paper sign sequence; verify", [], "community"),
    # --- items ---
    _e("pds_008", "rice", "rice", "item", ["chawal"],
       False, "C-shaped hands, fingers tap together (grain); or hand-to-mouth eating rice", [], "islrtc"),
    _e("pds_009", "wheat", "wheat", "item", ["gehu", "atta"],
       False, "Grain-like tapping; often distinguished from rice by movement", [], "islrtc"),
    _e("pds_010", "atta", "wheat flour (atta)", "item", ["flour"],
       False, "Sifting/flour motion; verify against WHEAT", [], "community"),
    _e("pds_011", "kerosene", "kerosene (oil)", "item", ["mitthi-tel"],
       False, "Liquid-pouring motion from a can; context signals kerosene", [], "community"),
    _e("pds_012", "sugar", "sugar", "item", ["chini"],
       False, "Flick over thumb-tip as if sprinkling sugar", [], "islrtc"),
    _e("pds_013", "cooking-oil", "cooking oil", "item", ["tel"],
       False, "Pouring motion; verify against KEROSENE", [], "community"),
    _e("pds_014", "salt", "salt", "item", ["namak"],
       False, "Pinch + sprinkle near mouth", [], "islrtc"),
    _e("pds_015", "dal", "pulses / dal", "item", ["pulse", "lentils"],
       False, "Open palm scooping motion; verify", [], "community"),
    _e("pds_016", "gram", "gram (chana)", "item", ["chana", "besan"],
       False, "Grain-like sign; check regional distinction from DAL", [], "community"),
    _e("pds_017", "jaggery", "jaggery (gur)", "item", ["gur"],
       False, "Dark block + sweet-taste sign combination", [], "community"),
    _e("pds_018", "onion", "onion", "item", ["pyaaz"],
       False, "Rounded hand near eye, tear motion", [], "islrtc"),
    _e("pds_019", "potato", "potato", "item", ["aloo"],
       False, "Cupped hand makes potato-shaped bulge on other hand", [], "islrtc"),
    _e("pds_020", "gas-cylinder", "LPG cylinder", "item", ["lpg", "gas"],
       False, "Both hands circle a cylinder shape at mid-torso", [], "community"),
    _e("pds_021", "lpg-refill", "LPG refill / booking", "item", ["refill", "booking"],
       False, "CYLINDER + REPEAT/circle motion (refill)", [], "community"),
    _e("pds_022", "matchbox", "matchbox", "item", ["matches"],
       False, "Strike motion on forearm + handshape of small box", [], "community"),
    # --- quantities / units ---
    _e("pds_023", "kilogram", "kilogram (kg)", "quantity", ["kg"],
       False, "Weight-balance hand motion; used with numerals", [], "islrtc"),
    _e("pds_024", "litre", "litre", "quantity", ["l", "liter"],
       False, "Filled-measure motion; context distinguishes from kg", [], "islrtc"),
    _e("pds_025", "quintal", "quintal", "quantity", ["q"],
       False, "Large scoop of both arms — big quantity marker", [], "community"),
    _e("pds_026", "quantity", "quantity / amount", "quantity", ["amount", "how-much"],
       False, "Spread fingers, wriggle + palm-up (how much)", [], "islrtc"),
    _e("pds_027", "household", "household / family", "quantity", ["family", "home"],
       False, "Two open hands draw a roof over the head (house)", [], "islrtc"),
    _e("pds_028", "member", "family member", "quantity", ["family-member", "person"],
       False, "Flat hands stacked → count; verify", [], "community"),
    # --- procedures ---
    _e("pds_029", "new-card", "new ration card", "procedure", ["fresh-card"],
       False, "RATIO-CARD + NEW (wrist sweep) sequence", [], "community"),
    _e("pds_030", "renewal", "renewal", "procedure", [],
       False, "ROTATE/replace motion over the card sign", [], "community"),
    _e("pds_031", "correction", "correction / change", "procedure", ["edit", "sudaar"],
       False, "Sweep index finger across the written-correct motion; clarify", [], "community"),
    _e("pds_032", "duplicate", "duplicate card", "procedure", [],
       False, "TWO of same card motion (repeat same sign + index-2)", [], "community"),
    _e("pds_033", "transfer", "transfer / shifting", "procedure", ["shift"],
       False, "Move flat hand from one location to another", [], "community"),
    _e("pds_034", "ekyc", "e-KYC / biometric check", "procedure", ["kyc", "biometric"],
       False, "Thumbprint/scan motion: thumb pressed to screen/pad", [], "community"),
    _e("pds_035", "fingerprint", "fingerprint", "procedure", ["thumb-impression"],
       False, "Press thumb-tip on pad, slight roll", [], "islrtc"),
    _e("pds_036", "aadhaar-link", "Aadhaar linking", "procedure", ["link"],
       False, "AADHAAR then LINK (interlocked fingers + pull)", [], "community"),
    _e("pds_037", "quota", "quota / entitlement", "procedure", ["allotment", "entitlement"],
       False, "Cup hand then portion-off dividing motion; verify regional variants",
       [{"region": "mumbai", "note": "portion gesture with both hands at mid-torso"}], "community"),
    _e("pds_038", "allocation", "allocation", "procedure", ["distribution"],
       False, "Hands distribute items to virtual shelves", [], "community"),
    _e("pds_039", "subsidy", "subsidy", "procedure", ["discount", "saudi"],
       False, "MONEY + downward/off motion (amount removed)", [], "community"),
    _e("pds_040", "token", "token / queue number", "procedure", ["number", "counter"],
       False, "Paper slip held up + number; verify", [], "community"),
    _e("pds_041", "queue", "queue / line", "procedure", ["line", "katar"],
       False, "Chop hand in front repeatedly — people in a line", [], "islrtc"),
    _e("pds_042", "receipt", "receipt", "procedure", ["bill"],
       False, "Write + tear slip motion; verify", [], "community"),
    _e("pds_043", "price", "price", "procedure", ["cost", "rate"],
       False, "Index fingers tap together (money) repeatedly; or MONEY + count", [], "islrtc"),
    _e("pds_044", "e-kyc-register", "register (e-KYC)", "procedure", ["enrolment"],
       False, "Write-in-book motion + biometric scan; verify", [], "community"),
    # --- actions ---
    _e("pds_045", "give", "give / provide", "action", ["provide"],
       False, "Open hand pushed forward from body towards receiver", [], "islrtc"),
    _e("pds_046", "need", "need / want", "action", ["want", "require"],
       False, "Draw open hand in towards chest (pull-to-self)", [], "islrtc"),
    _e("pds_047", "take", "take / collect", "action", ["collect", "le"],
       False, "Grasp + pull in from the counter space", [], "islrtc"),
    _e("pds_048", "buy", "buy / purchase", "action", ["purchase", "kharidna"],
       False, "MONEY handed over motion", [], "islrtc"),
    _e("pds_049", "fill-form", "fill (form)", "action", ["form", "apply"],
       False, "Handwriting motion across a flat palm (form)", [], "islrtc"),
    _e("pds_050", "sign", "sign / signature", "action", [],
       False, "Write squiggle in the air in front of chest", [], "islrtc"),
    _e("pds_051", "bring", "bring / carry documents", "action", ["carry"],
       False, "Both hands lift a stack (documents) towards person", [], "community"),
    _e("pds_052", "wait", "wait", "action", [],
       False, "Fingers of one hand tap on open palm (fingers-walk with still hand?) — WAIT; verify",
       [], "islrtc"),
    _e("pds_053", "help", "help", "action", ["assist"],
       False, "Place flat hand under the other arm and lift", [], "islrtc"),
    _e("pds_054", "verify", "verify / check", "action", ["check", "confirm"],
       False, "Scan motion over a document (looking + tapping)", [], "community"),
    _e("pds_055", "cancel", "cancel / remove", "action", ["delete"],
       False, "Brush index finger across the imaginary line (X)", [], "community"),
    # --- people / places / questions ---
    _e("pds_056", "dealer", "ration shop dealer", "person", ["counter-man", "pds-officer"],
       False, "Shop + person sign sequence; verify", [], "community"),
    _e("pds_057", "pds-officer", "PDS officer", "person", ["officer", "authority"],
       False, "Stamp/seal motion near shoulder (authority)", [], "community"),
    _e("pds_058", "shop", "fair price shop", "place", ["ration-shop", "store"],
       False, "Hand opens like a door + shop counter; verify", [], "community"),
    _e("pds_059", "counter", "counter", "place", ["window"],
       False, "Flat hand vertical, palm toward viewer, tapping at counter level", [], "community"),
    _e("pds_060", "yes", "yes", "question", ["haan"],
       False, "Vertical head-nod + fist 'yes' motion; non-manual nod accompanies", [], "islrtc"),
    _e("pds_061", "no", "no", "question", ["naheen"],
       False, "Headshake + flat-hand negation sweep; verify", [], "islrtc"),
    _e("pds_062", "where", "where", "question", [],
       False, "Point index finger into space, furrowed brows", [], "islrtc"),
    _e("pds_063", "when", "when", "question", [],
       False, "Index finger circles at side while tapping other wrist", [], "islrtc"),
    _e("pds_064", "how-much", "how much", "question", ["amount"],
       False, "Two palms up, fingers wriggle, brows furrowed", [], "islrtc"),
    _e("pds_065", "complaint", "complaint", "procedure", ["shikayat"],
       False, "Two hands repeatedly arc downward from mouth — speaking complaint", [], "islrtc"),
]

HEALTH_GLOSSES = [
    # --- symptoms ---
    _e("hth_001", "pain", "pain", "symptom", ["dard"],
       False, "Clawed fingers dig/press at the painful place (e.g., head, stomach)", [], "islrtc"),
    _e("hth_002", "fever", "fever", "symptom", ["bukhar"],
       False, "Fingers slide across forehead (heat) — verify per region",
       [{"region": "mumbai", "note": "forehead-to-temple sweep with open hand"}], "islrtc"),
    _e("hth_003", "headache", "headache", "symptom", ["head-pain"],
       False, "PAIN at temple/forehead (two hands clasping head)", [], "islrtc"),
    _e("hth_004", "stomachache", "stomach pain", "symptom", ["stomach-pain"],
       False, "PAIN at abdomen with clawed hand", [], "community"),
    _e("hth_005", "cough", "cough", "symptom", ["khansi"],
       False, "Fist near mouth, two quick forward motions (coughing)", [], "islrtc"),
    _e("hth_006", "cold", "cold / runny nose", "symptom", ["zukham"],
       False, "Pinch nose + close eyes motion; or sniffing; verify", [], "islrtc"),
    _e("hth_007", "vomit", "vomit", "symptom", ["naausea", "ultra"],
       False, "Hand near mouth with tremor, leaning forward", [], "community"),
    _e("hth_008", "dizziness", "dizziness", "symptom", ["chakkar", "vertigo"],
       False, "Index finger circles around ear/head", [], "community"),
    _e("hth_009", "burning", "burns / burning", "symptom", ["jaIn"],
       False, "Fingers wiggle then snap back from painful spot (heat)", [], "community"),
    _e("hth_010", "wound", "wound / injury", "symptom", ["ghaav", "injury"],
       False, "Draw slash on forearm, or bandaged-hand motion", [], "community"),
    # --- body parts ---
    _e("hth_011", "head", "head", "body_part", [],
       False, "Tap side of head with flat hand", [], "islrtc"),
    _e("hth_012", "eye", "eye", "body_part", [],
       False, "Point index finger at eye", [], "islrtc"),
    _e("hth_013", "ear", "ear", "body_part", [],
       False, "Point/pinch earlobe", [], "islrtc"),
    _e("hth_014", "nose", "nose", "body_part", [],
       False, "Pinch nose tip with two fingers", [], "islrtc"),
    _e("hth_015", "mouth", "mouth / throat", "body_part", ["throat"],
       False, "Touch mouth or throat with index finger", [], "islrtc"),
    _e("hth_016", "tooth", "tooth / teeth", "body_part", ["dant"],
       False, "Tap teeth with index finger (or finger over front teeth)", [], "islrtc"),
    _e("hth_017", "stomach", "stomach / abdomen", "body_part", ["belly"],
       False, "Both hands over abdomen, palm flat", [], "islrtc"),
    _e("hth_018", "chest", "chest", "body_part", [],
       False, "Tap chest with open hand", [], "islrtc"),
    _e("hth_019", "back", "back", "body_part", [],
       False, "Reach over shoulder, tap back", [], "islrtc"),
    _e("hth_020", "arm", "arm / hand", "body_part", ["hand"],
       False, "Tap forearm with open hand", [], "islrtc"),
    _e("hth_021", "leg", "leg / foot", "body_part", ["foot"],
       False, "Tap thigh or show foot; context distinguishes", [], "islrtc"),
    # --- medicine / treatment ---
    _e("hth_022", "medicine", "medicine", "medicine", ["dawa"],
       False, "Two fingers at palm (pill) brought to mouth", [], "islrtc"),
    _e("hth_023", "tablet", "tablet / pill", "medicine", ["pill", "capsule"],
       False, "Pinch pill and move to mouth", [], "islrtc"),
    _e("hth_024", "syrup", "syrup", "medicine", ["sherb"],
       False, "Bottle-to-spoon pour then to mouth", [], "community"),
    _e("hth_025", "injection", "injection", "medicine", ["shot", "injection"],
       False, "Index+middle of one hand press into other forearm (needle)", [], "islrtc"),
    _e("hth_026", "drip", "drip / IV", "medicine", ["saline"],
       False, "Finger slides down inner forearm with drip tap", [], "community"),
    _e("hth_027", "prescription", "prescription", "medicine", ["parchi"],
       False, "Writing + sheet of paper motion; then hand out slip", [], "community"),
    _e("hth_028", "bandage", "bandage", "medicine", ["pati"],
       False, "Wrap motion around the wounded limb", [], "community"),
    _e("hth_029", "cotton", "cotton / gauge", "medicine", [],
       False, "Pinch soft cotton motion near wound", [], "community"),
    _e("hth_030", "operation", "surgery / operation", "medicine", ["surgery"],
       False, "Scalpel cut motion across flat palm + surgical context", [], "community"),
    # --- facilities / services ---
    _e("hth_031", "hospital", "hospital", "facility", ["aspatal"],
       False, "Cross (red cross) made on arm with two fingers + building context", [], "islrtc"),
    _e("hth_032", "clinic", "clinic / doctor chamber", "facility", ["doctor-chamber"],
       False, "Cross + smaller building; or DOCTOR + room", [], "community"),
    _e("hth_033", "pharmacy", "pharmacy / chemist", "facility", ["chemist", "medical-shop"],
       False, "MEDICINE + SHOP sequence", [], "community"),
    _e("hth_034", "ambulance", "ambulance", "facility", [],
       False, "Red-cross sign + steering/bell motion; or flasing light on head; verify", [], "community"),
    _e("hth_035", "referral", "referral", "service", ["refer"],
       False, "Push flat hand from one side to other (handover to next hospital)", [], "community"),
    _e("hth_036", "wheelchair", "wheelchair", "service", [],
       False, "Both fists rotate at sides (pushing wheels)", [], "community"),
    _e("hth_037", "emergency", "emergency", "service", ["115", "92", "urgent"],
       False, "Both hands flap rapidly at sides (urgent); verify", [], "community"),
    _e("hth_038", "first-aid", "first aid", "service", [],
       False, "Cross + wrap sequence; verify", [], "community"),
    _e("hth_039", "test", "test / lab test", "service", ["x-ray", "blood-test"],
       False, "Pinch finger (blood drop) + drop on slide; verify", [], "community"),
    _e("hth_040", "x-ray", "X-ray", "service", [],
       False, "Hands framing a film + scan motion; verify", [], "community"),
    _e("hth_041", "admission", "admission (to ward)", "service", ["admit"],
       False, "Push flat hand forward into a bed/ward space", [], "community"),
    _e("hth_042", "discharge", "discharge (from hospital)", "service", [],
       False, "Pull flat hand back from ward space", [], "community"),
    _e("hth_043", "appointment", "appointment / OPD ticket", "service", ["opd"],
       False, "Write ticket + number motion; verify", [], "community"),
    _e("hth_044", "health-card", "health card / Ayushman", "service", ["ayushman"],
       False, "CARD sign at chest + health context", [], "community"),
    # --- conditions ---
    _e("hth_045", "diabetes", "diabetes / sugar", "condition", ["sugar"],
       False, "Pinch finger (blood) + drop on tongue motion; verify", [], "community"),
    _e("hth_046", "blood-pressure", "blood pressure", "condition", ["bp"],
       False, "Arm bent, index fingers press inner elbow like a cuff", [], "community"),
    _e("hth_047", "heart", "heart", "condition", ["dil"],
       False, "Both hands make heart shape over chest", [], "islrtc"),
    _e("hth_048", "asthma", "asthma / breathing trouble", "condition", ["saans"],
       False, "Hands on chest, heaving motion (breath difficulty)", [], "community"),
    _e("hth_049", "pregnancy", "pregnancy", "condition", ["garbhavati"],
       False, "Hands over belly, rounded motion", [], "community"),
    _e("hth_050", "fracture", "fracture / bone injury", "condition", ["broken-bone"],
       False, "Snap index fingers apart (bone crack) at site", [], "community"),
    _e("hth_051", "poison", "poison", "condition", ["jeher"],
       False, "Shudder + dark liquid shake motion; verify", [], "community"),
    # --- persons / questions ---
    _e("hth_052", "doctor", "doctor", "person", ["vaidya"],
       False, "Tapping pulse at wrist + STETHOSCOPE context; verify", [], "islrtc"),
    _e("hth_053", "nurse", "nurse", "person", [],
       False, "Syringe + cross combination; verify", [], "community"),
    _e("hth_054", "asha", "ASHA / ANM worker", "person", ["anm", "health-worker"],
       False, "Health-visit case motion + uniform collar; verify", [], "community"),
    _e("hth_055", "interpreter", "interpreter (sign)", "person", ["translator"],
       False, "Two index fingers point alternately at two people (between)", [], "islrtc"),
    _e("hth_056", "waiting", "wait for doctor", "action", ["wait"],
       False, "WAIT sign then point around the row; verify", [], "community"),
    _e("hth_057", "how-feel", "how do you feel", "question", ["feel", "aur-kaisa"],
       False, "Both hands wipe chest downward + WHY/WHAT brows; verify", [], "community"),
    _e("hth_058", "better", "better / improvement", "action", ["accha", "thik"],
       False, "Both thumbs up + nod, shoulders relaxed", [], "islrtc"),
]

LEGAL_GLOSSES = [
    # --- persons ---
    _e("leg_001", "judge", "judge", "person", ["adalat-adhikari"],
       False, "2 open hands horizontal at chest height (robe/slap podium); verify", [], "community"),
    _e("leg_002", "lawyer", "lawyer / advocate", "person", ["vakil"],
       False, "Both hands as wings at sides + forward motion (gown); verify", [], "community"),
    _e("leg_003", "interpreter", "interpreter (sign)", "person", ["translator"],
       False, "Two index fingers alternate between two people (between)", [], "islrtc"),
    _e("leg_004", "witness", "witness", "person", ["gavah"],
       False, "Raise arm like oath-taking (right hand up)", [], "community"),
    _e("leg_005", "accused", "accused", "person", ["abhiyukta", "defendant"],
       False, "Point-and-hold (accuse) + raising hand context; verify", [], "community"),
    _e("leg_006", "victim", "victim / aggrieved", "person", ["pidit"],
       False, "Both hands over chest, hurt expression; verify", [], "community"),
    _e("leg_007", "police", "police", "person", ["daroga"],
       False, "Forehead + salute motion; verify", [], "community"),
    _e("leg_008", "dsp", "DSP / senior officer", "person", ["officer"],
       False, "POLICE + shoulder rank tap", [], "community"),
    _e("leg_009", "petitioner", "petitioner", "person", ["ardak"],
       False, "PETITION + PERSON; or DEEKHA; verify", [], "community"),
    # --- places ---
    _e("leg_010", "court", "court", "place", ["adalat", "kacheri"],
       False, "Both hands frame a desk in front (bench) or COLUMN + table; verify",
       [{"region": "punjab", "note": "open hands frame desk, both sides"}], "community"),
    _e("leg_011", "court-room", "courtroom", "place", [],
       False, "COURT + ROOM (frame walls) sequence; verify", [], "community"),
    _e("leg_012", "lockup", "lockup / jail", "place", ["jael", "prison"],
       False, "Both fists at wrists (handcuffs) shake; verify", [], "community"),
    _e("leg_013", "jail", "jail / prison", "place", ["bandi-ghar"],
       False, "Bars with both hands + face through bars expression", [], "community"),
    _e("leg_014", "legal-aid-office", "legal aid clinic", "place", ["legal-aid"],
       False, "BALANCE gesture (leading) + office; verify", [], "community"),
    # --- documents ---
    _e("leg_015", "petition", "petition", "document", ["plik"],
       False, "Slip of paper handed upward to bench; verify",
       [{"region": "delhi", "note": "paper present + upward push; west regions vary"}], "community"),
    _e("leg_016", "affidavit", "affidavit", "document", [],
       False, "Signing + stamp + oath sequence; verify", [], "community"),
    _e("leg_017", "bail", "bail", "document", ["jamin"],
       False, "Release-from-handcuffs motion (unlock + push away)", [], "community"),
    _e("leg_018", "summon", "summon / notice", "document", ["notice", "notis"],
       False, "Paper + tap on it in front (served) then point at person", [], "community"),
    _e("leg_019", "order", "order / judgement", "document", ["hukum", "judgement"],
       False, "One hand vertical (page), other makes downward strike (stamp)", [], "community"),
    _e("leg_020", "evidence", "evidence / proof", "document", ["saboot", "proof"],
       False, "Hold up document + point to it (this proves)", [], "community"),
    _e("leg_021", "document", "document / paper", "document", ["paper", "kagaz"],
       False, "Flat open hand, other hand reads along it", [], "islrtc"),
    _e("leg_022", "charge-sheet", "charge sheet", "document", [],
       False, "Paper + stamp-down motion; verify", [], "community"),
    _e("leg_023", "verdict", "verdict / ruling", "document", ["niraaya"],
       False, "Both hands come together to centre (decision) + stamp", [], "community"),
    _e("leg_024", "stamp", "stamp / seal", "document", ["muhar", "seal"],
       False, "Closed fist presses down (stamp) on paper", [], "community"),
    _e("leg_025", "court-fee", "court fee", "document", ["fee"],
       False, "MONEY + COURT sequence; verify", [], "community"),
    _e("leg_026", "legal-aid-form", "legal aid form", "document", [],
       False, "LEGAL-AID + FORM sequence; verify", [], "community"),
    # --- procedures ---
    _e("leg_027", "file-case", "file a case", "procedure", ["case-daalna"],
       False, "Paper push into a folder/case motion", [], "community"),
    _e("leg_028", "hearing", "hearing / court date", "procedure", ["date"],
       False, "COURT + calendar/date tap; verify", [], "community"),
    _e("leg_029", "appeal", "appeal", "procedure", ["apil"],
       False, "Paper uplift + raising to higher court; verify", [], "community"),
    _e("leg_030", "witness-stand", "stand as witness", "procedure", [],
       False, "WITNESS + stand-up motion; verify", [], "community"),
    _e("leg_031", "oath", "oath / swear", "procedure", ["kasam"],
       False, "Hand raised, palm flat like Bible oath", [], "community"),
    _e("leg_032", "first-information-report", "FIR", "procedure", ["report"],
       False, "Write on paper + stamp; or POLICE + report; verify", [], "community"),
    _e("leg_033", "complaint-register", "register complaint (court)", "procedure", ["shikayat"],
       False, "COMPLAINT + file motion; verify vs PDS COMPLAINT sign", [], "community"),
    _e("leg_034", "legal-aid", "legal aid", "procedure", ["nyay-sahayata"],
       False, "SCALE/BALANCE gesture opened flat (justice) + GIVE", [], "community"),
    _e("leg_035", "legal-advice", "legal advice", "procedure", ["parivka"],
       False, "LAWYER + ARROW to head (advise) sequence; verify", [], "community"),
    _e("leg_036", "bail-hearing", "bail hearing", "procedure", [],
       False, "BAIL + HEARING (calendar tap) sequence", [], "community"),
    _e("leg_037", "custody", "custody", "procedure", ["hiraasat"],
       False, "Wrist-cuff + hold-back motion; verify", [], "community"),
    _e("leg_038", "release", "release", "procedure", ["azaadi"],
       False, "Pull hands apart from wrist-cuffs (freed)", [], "community"),
    # --- offences / actions ---
    _e("leg_039", "theft", "theft / stolen", "offence", ["chori"],
       False, "Grab from pocket + pull; verify", [], "community"),
    _e("leg_040", "fraud", "fraud / cheating", "offence", ["dhoka", "cheating"],
       False, "Two palms rubbing then one hand snatches away; verify", [], "community"),
    _e("leg_041", "assault", "assault / hitting", "offence", ["maar"],
       False, "Fist strikes other palm; hurt expression", [], "community"),
    _e("leg_042", "murder", "murder", "offence", ["hatya"],
       False, "Both hands choke + drop; verify sensitivity", [], "community"),
    _e("leg_043", "rape", "rape", "offence", [],
       False, "Sensitive — use careful handshape (grip + force); labelers briefed; verify", [],
       "community"),
    _e("leg_044", "dowry", "dowry / dowry case", "offence", ["dadhej"],
       False, "Goods handed across (wedding + goods); verify", [], "community"),
    _e("leg_045", "arrest", "arrest", "offence", ["giraphtar"],
       False, "Grab wrist with one hand and pull down; handcuff", [], "community"),
    # --- rights ---
    _e("leg_046", "rights", "rights", "rights", ["adhikaR"],
       False, "Fist thrust up at chest height (power/right)", [], "community"),
    _e("leg_047", "justice", "justice / justice for", "rights", ["nyaya"],
       False, "BALANCE scale made with both forearm hands", [], "community"),
    _e("leg_048", "fair", "fair / equal treatment", "rights", ["nyaayik", "barabar"],
       False, "Both flat hands level at same height (equal)", [], "islrtc"),
    # --- questions ---
    _e("leg_049", "where-apply", "where do I apply", "question", [],
       False, "WHERE + APPLY (paper push) sequence", [], "community"),
    _e("leg_050", "how-long", "how long / duration", "question", [],
       False, "Flat hand moves horizontally away with count (time distance)", [], "community"),
]


def main():
    parser = argparse.ArgumentParser(description="Build + validate BhashaSetu glossaries")
    parser.add_argument("--check", action="store_true",
                        help="only validate existing JSON files, do not overwrite")
    args = parser.parse_args()

    gloss_dir = ROOT / "data" / "glossaries"
    meta = json.loads((gloss_dir / "meta.json").read_text(encoding="utf-8"))
    valid_categories = {
        d: set(meta["domains"][d]["categories"]) for d in meta["domains"]
    }
    valid_regions = {r["code"] for r in meta["regions"]}

    if not args.check:
        for domain, entries in (("pds", PDS_GLOSSES), ("health", HEALTH_GLOSSES),
                               ("legal", LEGAL_GLOSSES)):
            payload = {"domain": domain, "version": "0.1.0-seed",
                       "note": "Seed glossary — grows towards 500-1000 signs/domain. "
                               "Each entry requires verification against a listed source.",
                       "glosses": entries}
            out = gloss_dir / f"{domain}.json"
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {out.relative_to(ROOT)} ({len(entries)} entries)")

    # --- validate everything ---
    errors = []
    for domain in valid_categories:
        payload = json.loads((gloss_dir / f"{domain}.json").read_text(encoding="utf-8"))
        ids, glosses = set(), set()
        for e in payload["glosses"]:
            if e["id"] in ids:
                errors.append(f"{domain}: duplicate id {e['id']}")
            ids.add(e["id"])
            if e["gloss"] in glosses:
                errors.append(f"{domain}: duplicate gloss {e['gloss']}")
            glosses.add(e["gloss"])
            if not isinstance(e["gloss"], str) or not e["gloss"].strip():
                errors.append(f"{domain}/{e['id']}: empty gloss")
            if e["category"] not in valid_categories[domain]:
                errors.append(f"{domain}/{e['id']}: bad category {e['category']}")
            for v in e["regional_variants"]:
                if v["region"] not in valid_regions:
                    errors.append(f"{domain}/{e['id']}: bad region {v['region']}")

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)
    total = sum(len(json.loads((gloss_dir / f"{d}.json").read_text(encoding="utf-8"))["glosses"])
                 for d in valid_categories)
    print(f"validate: OK — categories/regions/ids/glosses all consistent ({total} glosses total)")


if __name__ == "__main__":
    main()