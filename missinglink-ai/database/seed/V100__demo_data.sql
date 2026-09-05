-- ============================================================
-- MISSINGLINK AI — V100: SYNTHETIC DEMO DATA
-- Entirely fictional. No real person's data is used.
-- All demo users share the password: Demo123!
-- ============================================================

-- ------------------------------------------------------------
-- Users (roles referenced by name for readability)
-- ------------------------------------------------------------
INSERT INTO users (email, password_hash, full_name, phone, role_id, status, mfa_enabled) VALUES
  ('admin@missinglink.demo',  '$2b$10$qODVy68IOqK3AEZk6dOaKeHSJynhtayQURJBW2BGCwNKCm9JfL8ce', 'Aisha Verma',   '+91-0000000001', (SELECT id FROM roles WHERE name='ADMIN'),         'ACTIVE', FALSE),
  ('investigator@missinglink.demo', '$2b$10$qODVy68IOqK3AEZk6dOaKeHSJynhtayQURJBW2BGCwNKCm9JfL8ce', 'Rohan Deshmukh', '+91-0000000002', (SELECT id FROM roles WHERE name='INVESTIGATOR'), 'ACTIVE', FALSE),
  ('family1@missinglink.demo', '$2b$10$qODVy68IOqK3AEZk6dOaKeHSJynhtayQURJBW2BGCwNKCm9JfL8ce', 'Priya Nair',    '+91-0000000003', (SELECT id FROM roles WHERE name='FAMILY'),        'ACTIVE', FALSE),
  ('family2@missinglink.demo', '$2b$10$qODVy68IOqK3AEZk6dOaKeHSJynhtayQURJBW2BGCwNKCm9JfL8ce', 'Arjun Gupta',   '+91-0000000004', (SELECT id FROM roles WHERE name='FAMILY'),        'ACTIVE', FALSE),
  ('family3@missinglink.demo', '$2b$10$qODVy68IOqK3AEZk6dOaKeHSJynhtayQURJBW2BGCwNKCm9JfL8ce', 'Meena Iyer',    '+91-0000000005', (SELECT id FROM roles WHERE name='FAMILY'),        'ACTIVE', FALSE),
  ('public1@missinglink.demo', '$2b$10$qODVy68IOqK3AEZk6dOaKeHSJynhtayQURJBW2BGCwNKCm9JfL8ce', 'Karan Malhotra','+91-0000000006', (SELECT id FROM roles WHERE name='PUBLIC_USER'),   'ACTIVE', FALSE),
  ('public2@missinglink.demo', '$2b$10$qODVy68IOqK3AEZk6dOaKeHSJynhtayQURJBW2BGCwNKCm9JfL8ce', 'Sneha Reddy',   '+91-0000000007', (SELECT id FROM roles WHERE name='PUBLIC_USER'),   'ACTIVE', FALSE),
  ('public3@missinglink.demo', '$2b$10$qODVy68IOqK3AEZk6dOaKeHSJynhtayQURJBW2BGCwNKCm9JfL8ce', 'Vikram Singh',  '+91-0000000008', (SELECT id FROM roles WHERE name='PUBLIC_USER'),   'ACTIVE', FALSE);

-- ------------------------------------------------------------
-- Missing person cases MP-101 .. MP-110 (all synthetic)
-- ------------------------------------------------------------
INSERT INTO missing_person_cases
  (case_reference, reporter_id, status, priority_level, emergency_classification,
   title, first_name, last_name, age, gender, height_cm, identification_marks,
   languages, last_known_activity, transportation, possible_destinations, description,
   last_known_place, last_known_at, last_known_lat, last_known_lng, is_public, created_at)
VALUES
  ('MP-101', (SELECT id FROM users WHERE email='family1@missinglink.demo'),  'ACTIVE', 'CRITICAL', 'At-risk person — child',
   'Case MP-101 — Aarav', 'Aarav', 'Menon', 9, 'MALE', 132, 'Mole on left cheek; scar on right knee',
   'Malayalam, English', 'Returning home from tuition', 'Walking', 'Friends'' houses, local park',
   'Did not return home from tuition on Friday evening.', 'Indiranagar, Bengaluru',
   now() - interval '6 hours', 12.9719, 77.6412, TRUE, now() - interval '6 hours'),

  ('MP-102', (SELECT id FROM users WHERE email='family1@missinglink.demo'),  'ACTIVE', 'HIGH', 'At-risk person — elder',
   'Case MP-102 — Krishnan', 'Krishnan', 'Nair', 74, 'MALE', 165, 'Grey beard; walks with slight limp',
   'Malayalam, Hindi', 'Morning walk to temple', 'Walking', 'Temple, market, bus stand',
   'Left for morning walk and did not return.', 'Fort Kochi, Kochi',
   now() - interval '30 hours', 9.9658, 76.2421, TRUE, now() - interval '30 hours'),

  ('MP-103', (SELECT id FROM users WHERE email='family2@missinglink.demo'),  'ACTIVE', 'CRITICAL', 'At-risk person — adult',
   'Case MP-103 — Zoya', 'Zoya', 'Khan', 22, 'FEMALE', 158, 'Small tattoo on left wrist',
   'Hindi, English', 'Last seen at metro station after college', 'Metro, bus', 'Campus, friend''s flat, city centre',
   'Disappeared after leaving college campus.', 'Jamia Nagar, New Delhi',
   now() - interval '52 hours', 28.5627, 77.2823, TRUE, now() - interval '52 hours'),

  ('MP-104', (SELECT id FROM users WHERE email='family2@missinglink.demo'),  'ACTIVE', 'STANDARD', 'At-risk person — adult',
   'Case MP-104 — Rajesh', 'Rajesh', 'Pillai', 41, 'MALE', 178, 'Thick moustache',
   'Hindi, Marathi', 'Left for a business meeting', 'Car', 'Office, railway station',
   'Has not been in touch since leaving for a business meeting.', 'Powai, Mumbai',
   now() - interval '3 days', 19.1176, 72.9060, FALSE, now() - interval '3 days'),

  ('MP-105', (SELECT id FROM users WHERE email='family3@missinglink.demo'),  'ACTIVE', 'HIGH', 'At-risk person — adult',
   'Case MP-105 — Meera', 'Meera', 'Kulkarni', 29, 'FEMALE', 162, 'Piercing on right nostril',
   'Marathi, English', 'Took an auto to the station', 'Auto, train', 'Family home, station, friend''s place',
   'Family reported her missing after she failed to arrive at the station.', 'Shivajinagar, Pune',
   now() - interval '2 days', 18.5313, 73.8449, TRUE, now() - interval '2 days'),

  ('MP-106', (SELECT id FROM users WHERE email='family3@missinglink.demo'),  'ACTIVE', 'CRITICAL', 'At-risk person — child',
   'Case MP-106 — Ishan', 'Ishan', 'Gupta', 13, 'MALE', 148, 'Birthmark on left forearm',
   'Hindi, English', 'Last seen near school playground', 'Bicycle', 'School, park, friends'' homes',
   'Missing after leaving school.', 'Salt Lake, Kolkata',
   now() - interval '10 hours', 22.5804, 88.4299, TRUE, now() - interval '10 hours'),

  ('MP-107', (SELECT id FROM users WHERE email='public1@missinglink.demo'),  'ACTIVE', 'STANDARD', 'At-risk person — adult',
   'Case MP-107 — Devi', 'Devi', 'Chandran', 35, 'FEMALE', 155, 'Long black hair, traditional bangles',
   'Tamil, English', 'Last seen at a bus stand', 'Bus', 'Relatives, market',
   'Reported by colleague after she missed work for a week.', 'T. Nagar, Chennai',
   now() - interval '5 days', 13.0418, 80.2341, TRUE, now() - interval '5 days'),

  ('MP-108', (SELECT id FROM users WHERE email='public2@missinglink.demo'),  'ACTIVE', 'HIGH', 'At-risk person — elder',
   'Case MP-108 — Harpal', 'Harpal', 'Singh', 68, 'MALE', 172, 'White turban, grey beard',
   'Punjabi, Hindi', 'Went for an evening walk', 'Walking', 'Gurudwara, market',
   'Did not return from evening walk.', 'Ludhiana, Punjab',
   now() - interval '20 hours', 30.9010, 75.8573, FALSE, now() - interval '20 hours'),

  ('MP-109', (SELECT id FROM users WHERE email='public3@missinglink.demo'),  'ACTIVE', 'STANDARD', 'At-risk person — adult',
   'Case MP-109 — Nandini', 'Nandini', 'Reddy', 26, 'FEMALE', 160, 'Dimple on right cheek',
   'Telugu, Hindi, English', 'Went to a job interview', 'Auto, metro', 'Office area, mall',
   'Last contact was a text before the interview.', 'Banjara Hills, Hyderabad',
   now() - interval '40 hours', 17.4156, 78.4343, TRUE, now() - interval '40 hours'),

  ('MP-110', (SELECT id FROM users WHERE email='family1@missinglink.demo'),  'LOCATED', 'STANDARD', 'At-risk person — adult',
   'Case MP-110 — Joseph', 'Joseph', 'Fernandes', 55, 'MALE', 170, 'Spectacles',
   'Konkani, English', 'Went to the pharmacy', 'Walking', 'Pharmacy, church, home',
   'Located safely; case closed.', 'Panaji, Goa',
   now() - interval '14 days', 15.4909, 73.8278, FALSE, now() - interval '14 days');

-- ------------------------------------------------------------
-- Consent records
-- ------------------------------------------------------------
INSERT INTO consent_records (case_id, granter_id, consent_type, consent_text, signed_at)
SELECT id, reporter_id, 'PHOTO_USE', 'I authorize the use of the provided photographs for AI-assisted matching within this platform.', created_at
FROM missing_person_cases;

-- ------------------------------------------------------------
-- Person profiles
-- ------------------------------------------------------------
INSERT INTO person_profiles (case_id, hair, eyes, skin_tone, clothing, accessories, backpack, shoes, other_characteristics, searchable_text, created_at)
SELECT
  c.id,
  'Black, short curly',   'Dark brown', 'Wheatish',   'Blue school uniform with crest',   'None',                    'Blue backpack',    'White sneakers', 'Mole on left cheek', 'Aarav Menon male child 9 years blue school uniform crest blue backpack white sneakers', c.created_at
FROM missing_person_cases c WHERE c.case_reference='MP-101'
UNION ALL
SELECT c.id,
  'Grey, short', 'Brown', 'Fair', 'White kurta and mundu', 'Gold chain', 'None', 'Brown sandals', 'Grey beard, limp', 'Krishnan Nair male elder 74 white kurta mundu gold chain brown sandals', c.created_at
FROM missing_person_cases c WHERE c.case_reference='MP-102'
UNION ALL
SELECT c.id,
  'Black, long straight', 'Dark brown', 'Fair', 'Denim jacket over black kurta', 'Silver earrings', 'Beige tote', 'Black sneakers', 'Tattoo on left wrist', 'Zoya Khan female 22 denim jacket black kurta silver earrings beige tote black sneakers', c.created_at
FROM missing_person_cases c WHERE c.case_reference='MP-103'
UNION ALL
SELECT c.id,
  'Black, thick', 'Dark', 'Wheatish', 'Navy blazer, grey trousers', 'Wrist watch', 'Black laptop bag', 'Black formal shoes', 'Thick moustache', 'Rajesh Pillai male 41 navy blazer grey trousers wrist watch laptop bag black shoes', c.created_at
FROM missing_person_cases c WHERE c.case_reference='MP-104'
UNION ALL
SELECT c.id,
  'Brown, shoulder length', 'Brown', 'Fair', 'Maroon saree with gold border', 'Small gold studs', 'None', 'Sandals', 'Nose piercing', 'Meera Kulkarni female 29 maroon saree gold border gold studs sandals', c.created_at
FROM missing_person_cases c WHERE c.case_reference='MP-105'
UNION ALL
SELECT c.id,
  'Black, short', 'Dark brown', 'Wheatish', 'Red polo shirt, blue jeans', 'None', 'Grey backpack', 'Red sports shoes', 'Birthmark on left forearm', 'Ishan Gupta male child 13 red polo shirt blue jeans grey backpack red sports shoes', c.created_at
FROM missing_person_cases c WHERE c.case_reference='MP-106'
UNION ALL
SELECT c.id,
  'Black, long', 'Dark', 'Brown', 'Green cotton saree', 'Bangles', 'None', 'Kolhapuri sandals', 'Traditional bangles', 'Devi Chandran female 35 green cotton saree bangles sandals', c.created_at
FROM missing_person_cases c WHERE c.case_reference='MP-107'
UNION ALL
SELECT c.id,
  'Grey, beard', 'Brown', 'Wheatish', 'Cream kurta, blue turban cloth', 'Turban', 'None', 'Black shoes', 'White turban', 'Harpal Singh male elder 68 cream kurta blue turban black shoes', c.created_at
FROM missing_person_cases c WHERE c.case_reference='MP-108'
UNION ALL
SELECT c.id,
  'Black, wavy', 'Dark brown', 'Wheatish', 'Teal top, white trousers', 'Chain necklace', 'Handbag', 'Beige heels', 'Dimple on right cheek', 'Nandini Reddy female 26 teal top white trousers chain necklace handbag heels', c.created_at
FROM missing_person_cases c WHERE c.case_reference='MP-109'
UNION ALL
SELECT c.id,
  'Grey, glasses', 'Brown', 'Fair', 'Light blue shirt, khaki trousers', 'Spectacles', 'None', 'Brown shoes', 'Wears spectacles', 'Joseph Fernandes male 55 light blue shirt khaki trousers spectacles brown shoes', c.created_at
FROM missing_person_cases c WHERE c.case_reference='MP-110';

-- ------------------------------------------------------------
-- Authorized photos (synthetic placeholder storage keys)
-- ------------------------------------------------------------
INSERT INTO authorized_photos (case_id, uploader_id, storage_key, photo_type, created_at)
SELECT c.id, c.reporter_id, 'demo/cases/' || lower(c.case_reference) || '/front.jpg', 'FRONT_FACE', c.created_at FROM missing_person_cases c
UNION ALL
SELECT c.id, c.reporter_id, 'demo/cases/' || lower(c.case_reference) || '/side.jpg', 'SIDE_PROFILE', c.created_at FROM missing_person_cases c
UNION ALL
SELECT c.id, c.reporter_id, 'demo/cases/' || lower(c.case_reference) || '/body.jpg', 'FULL_BODY', c.created_at FROM missing_person_cases c;

-- ------------------------------------------------------------
-- Sightings ST-1001 .. ST-1030
-- ------------------------------------------------------------
INSERT INTO sightings (sighting_reference, submitter_id, case_id, description, clothing, direction_of_movement, vehicle_info, notes, lat, lng, location_name, captured_at, reported_at, source, status, metadata)
VALUES
  ('ST-1001', (SELECT id FROM users WHERE email='public1@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-101'),
   'Child in blue school uniform seen near the park gate around evening.', 'Blue school uniform', 'Towards park gate', NULL,
   'Looked calm but alone.', 12.9738, 77.6429, 'Bengaluru — Domlur park', now() - interval '5 hours', now() - interval '4 hours', 'WEB', 'UNVERIFIED',
   jsonb_build_object('quality', 0.82, 'gps_accuracy_m', 12, 'has_face', TRUE)),

  ('ST-1002', (SELECT id FROM users WHERE email='public2@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-101'),
   'Saw a boy in blue uniform with a blue backpack near the bus stop.', 'Blue uniform, blue backpack', 'Towards bus stop', NULL,
   'He boarded a city bus.', 12.9701, 77.6380, 'Bengaluru — 100ft Road bus stop', now() - interval '4 hours 30 minutes', now() - interval '4 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.70, 'gps_accuracy_m', 25, 'has_face', FALSE)),

  ('ST-1003', (SELECT id FROM users WHERE email='public3@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-101'),
   'Blue uniform child walked towards the mall direction.', 'Blue uniform', 'Towards mall', NULL,
   'CCTV footage nearby may help.', 12.9695, 77.6352, 'Bengaluru — CMH Road', now() - interval '4 hours', now() - interval '3 hours 30 minutes', 'WEB', 'DUPLICATE',
   jsonb_build_object('quality', 0.61, 'gps_accuracy_m', 40, 'has_face', FALSE)),

  ('ST-1004', (SELECT id FROM users WHERE email='public1@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-102'),
   'Elderly man in white kurta walking slowly near the temple road.', 'White kurta', 'Towards temple', NULL,
   'Seemed disoriented.', 9.9675, 76.2433, 'Kochi — Temple road', now() - interval '26 hours', now() - interval '24 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.66, 'gps_accuracy_m', 18, 'has_face', TRUE)),

  ('ST-1005', (SELECT id FROM users WHERE email='public2@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-102'),
   'Elderly man with grey beard at the fish market.', 'White kurta and mundu', 'Towards market exit', NULL,
   'Same clothing as poster.', 9.9689, 76.2448, 'Kochi — Fish market', now() - interval '23 hours', now() - interval '21 hours', 'WEB', 'VERIFIED',
   jsonb_build_object('quality', 0.74, 'gps_accuracy_m', 10, 'has_face', TRUE)),

  ('ST-1006', (SELECT id FROM users WHERE email='public3@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-102'),
   'Man matching description resting on bench near bus stand.', 'White kurta', 'Stationary', NULL,
   NULL, 9.9662, 76.2410, 'Kochi — Bus stand', now() - interval '20 hours', now() - interval '19 hours', 'WEB', 'REJECTED',
   jsonb_build_object('quality', 0.55, 'gps_accuracy_m', 30, 'has_face', TRUE)),

  ('ST-1007', (SELECT id FROM users WHERE email='public1@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-103'),
   'Young woman in denim jacket near metro exit looking for directions.', 'Denim jacket, black kurta', 'Towards city centre', NULL,
   'Beige tote bag visible.', 28.5641, 77.2835, 'Delhi — Jamia metro', now() - interval '48 hours', now() - interval '46 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.88, 'gps_accuracy_m', 8, 'has_face', TRUE)),

  ('ST-1008', (SELECT id FROM users WHERE email='public2@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-103'),
   'Saw woman with silver earrings at the market.', 'Denim jacket', 'Towards market lane', NULL,
   NULL, 28.5609, 77.2798, 'Delhi — Hazrat Nizamuddin market', now() - interval '44 hours', now() - interval '42 hours', 'WEB', 'UNVERIFIED',
   jsonb_build_object('quality', 0.59, 'gps_accuracy_m', 22, 'has_face', FALSE)),

  ('ST-1009', (SELECT id FROM users WHERE email='public3@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-103'),
   'Similar looking woman near the park entrance.', 'Black kurta', 'Towards park', NULL,
   NULL, 28.5620, 77.2812, 'Delhi — Lodi garden area', now() - interval '40 hours', now() - interval '38 hours', 'WEB', 'DUPLICATE',
   jsonb_build_object('quality', 0.50, 'gps_accuracy_m', 35, 'has_face', FALSE)),

  ('ST-1010', (SELECT id FROM users WHERE email='public1@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-104'),
   'Man in navy blazer boarding a train.', 'Navy blazer, grey trousers', 'Towards platform', 'Local train', 
   'Carried a laptop bag.', 19.1170, 72.9048, 'Mumbai — Kurla station', now() - interval '3 days', now() - interval '2 days 22 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.72, 'gps_accuracy_m', 15, 'has_face', TRUE)),

  ('ST-1011', (SELECT id FROM users WHERE email='public2@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-104'),
   'Businessman matching poster near Vikhroli exit.', 'Navy blazer', 'Towards Vikhroli', 'Auto',
   NULL, 19.1068, 72.9269, 'Mumbai — Vikhroli', now() - interval '2 days 20 hours', now() - interval '2 days 18 hours', 'WEB', 'UNVERIFIED',
   jsonb_build_object('quality', 0.63, 'gps_accuracy_m', 20, 'has_face', FALSE)),

  ('ST-1012', (SELECT id FROM users WHERE email='public3@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-105'),
   'Woman in maroon saree bought a ticket to Pune.', 'Maroon saree', 'Towards ticket counter', NULL,
   'Gold border on saree.', 18.5250, 73.8420, 'Pune — Shivajinagar station', now() - interval '2 days', now() - interval '1 day 22 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.79, 'gps_accuracy_m', 12, 'has_face', TRUE)),

  ('ST-1013', (SELECT id FROM users WHERE email='public1@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-105'),
   'Saw a woman matching the description near the market.', 'Maroon saree', 'Towards market', NULL,
   NULL, 18.5288, 73.8461, 'Pune — Market yard', now() - interval '1 day 18 hours', now() - interval '1 day 16 hours', 'WEB', 'DUPLICATE',
   jsonb_build_object('quality', 0.47, 'gps_accuracy_m', 28, 'has_face', FALSE)),

  ('ST-1014', (SELECT id FROM users WHERE email='public2@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-106'),
   'Boy in red polo on a bicycle near the lake.', 'Red polo, blue jeans', 'Towards lake', 'Bicycle',
   'Grey backpack on his back.', 22.5815, 88.4310, 'Kolkata — Lake Town', now() - interval '9 hours', now() - interval '8 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.84, 'gps_accuracy_m', 9, 'has_face', TRUE)),

  ('ST-1015', (SELECT id FROM users WHERE email='public3@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-106'),
   'Red polo boy asking for directions near the crossing.', 'Red polo', 'Towards crossing', NULL,
   NULL, 22.5798, 88.4282, 'Kolkata — Salt Lake crossing', now() - interval '8 hours', now() - interval '7 hours 30 minutes', 'WEB', 'UNVERIFIED',
   jsonb_build_object('quality', 0.58, 'gps_accuracy_m', 16, 'has_face', TRUE)),

  ('ST-1016', (SELECT id FROM users WHERE email='public1@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-107'),
   'Woman in green saree seen at the bus terminal.', 'Green saree', 'Towards platform 2', 'Bus',
   NULL, 13.0430, 80.2355, 'Chennai — Broadway bus stand', now() - interval '4 days', now() - interval '3 days 20 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.69, 'gps_accuracy_m', 14, 'has_face', TRUE)),

  ('ST-1017', (SELECT id FROM users WHERE email='public2@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-107'),
   'Saree-clad woman with bangles at the ration shop.', 'Green saree, bangles', 'Towards shop', NULL,
   NULL, 13.0451, 80.2377, 'Chennai — Mylapore', now() - interval '3 days 22 hours', now() - interval '3 days 18 hours', 'WEB', 'DUPLICATE',
   jsonb_build_object('quality', 0.52, 'gps_accuracy_m', 31, 'has_face', FALSE)),

  ('ST-1018', (SELECT id FROM users WHERE email='public3@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-108'),
   'Turbaned elder near the gurudwara in the evening.', 'Cream kurta, blue turban', 'Towards gurudwara', NULL,
   'Grey beard.', 30.9022, 75.8585, 'Ludhiana — Gurudwara', now() - interval '19 hours', now() - interval '18 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.77, 'gps_accuracy_m', 11, 'has_face', TRUE)),

  ('ST-1019', (SELECT id FROM users WHERE email='public1@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-108'),
   'Elder matching description at the vegetable market.', 'Cream kurta', 'Towards market exit', NULL,
   NULL, 30.9040, 75.8602, 'Ludhiana — Sabzi Mandi', now() - interval '17 hours', now() - interval '15 hours', 'WEB', 'UNVERIFIED',
   jsonb_build_object('quality', 0.61, 'gps_accuracy_m', 19, 'has_face', FALSE)),

  ('ST-1020', (SELECT id FROM users WHERE email='public2@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-109'),
   'Woman in teal top seen entering an office building.', 'Teal top, white trousers', 'Towards building', NULL,
   'Handbag with her.', 17.4168, 78.4351, 'Hyderabad — Jubilee Hills', now() - interval '39 hours', now() - interval '38 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.81, 'gps_accuracy_m', 10, 'has_face', TRUE)),

  ('ST-1021', (SELECT id FROM users WHERE email='public3@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-109'),
   'Similar woman at the mall food court.', 'Teal top', 'Stationary', NULL,
   NULL, 17.4181, 78.4370, 'Hyderabad — Inorbit Mall', now() - interval '36 hours', now() - interval '34 hours', 'WEB', 'DUPLICATE',
   jsonb_build_object('quality', 0.56, 'gps_accuracy_m', 24, 'has_face', FALSE)),

  ('ST-1022', (SELECT id FROM users WHERE email='public1@missinglink.demo'), NULL,
   'Person in a teal top took an auto near the metro.', 'Teal top', 'Towards metro', 'Auto',
   NULL, 17.4149, 78.4335, 'Hyderabad — Metro station', now() - interval '33 hours', now() - interval '31 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.62, 'gps_accuracy_m', 13, 'has_face', FALSE)),

  ('ST-1023', (SELECT id FROM users WHERE email='public2@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-101'),
   'Boy with blue backpack at the convenience store paying with coins.', 'Blue uniform, blue backpack', 'Towards store', NULL,
   'Bought water and chips.', 12.9720, 77.6405, 'Bengaluru — Domlur store', now() - interval '3 hours 30 minutes', now() - interval '3 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.85, 'gps_accuracy_m', 7, 'has_face', TRUE)),

  ('ST-1024', (SELECT id FROM users WHERE email='public3@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-103'),
   'Woman matching poster on an auto near the flyover.', 'Denim jacket', 'Towards flyover', 'Auto',
   NULL, 28.5660, 77.2861, 'Delhi — Mathura Road', now() - interval '39 hours', now() - interval '37 hours', 'WEB', 'UNVERIFIED',
   jsonb_build_object('quality', 0.64, 'gps_accuracy_m', 17, 'has_face', FALSE)),

  ('ST-1025', (SELECT id FROM users WHERE email='public1@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-106'),
   'Red polo boy seen with another child near the park slide.', 'Red polo, blue jeans', 'Towards slide', NULL,
   NULL, 22.5823, 88.4322, 'Kolkata — Community park', now() - interval '7 hours', now() - interval '6 hours', 'WEB', 'UNVERIFIED',
   jsonb_build_object('quality', 0.73, 'gps_accuracy_m', 12, 'has_face', TRUE)),

  ('ST-1026', (SELECT id FROM users WHERE email='public2@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-102'),
   'Elderly man asking for directions to the bus stand.', 'White kurta, mundu', 'Towards bus stand', NULL,
   'May have gotten on a bus.', 9.9700, 76.2461, 'Kochi — Marine Drive', now() - interval '18 hours', now() - interval '16 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.68, 'gps_accuracy_m', 14, 'has_face', TRUE)),

  ('ST-1027', (SELECT id FROM users WHERE email='public3@missinglink.demo'), NULL,
   'Saw someone matching the Kochi poster near the bus terminal.', 'White kurta', 'Towards terminal', 'Bus',
   NULL, 9.9712, 76.2478, 'Kochi — Ernakulam terminal', now() - interval '15 hours', now() - interval '14 hours', 'MOBILE', 'UNVERIFIED',
   jsonb_build_object('quality', 0.60, 'gps_accuracy_m', 21, 'has_face', FALSE)),

  ('ST-1028', (SELECT id FROM users WHERE email='public1@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-105'),
   'Woman with nose stud matching poster at the temple entrance.', 'Maroon saree', 'Towards temple', NULL,
   NULL, 18.5301, 73.8477, 'Pune — Dagdusheth temple', now() - interval '1 day 12 hours', now() - interval '1 day 10 hours', 'WEB', 'UNVERIFIED',
   jsonb_build_object('quality', 0.70, 'gps_accuracy_m', 12, 'has_face', TRUE)),

  ('ST-1029', (SELECT id FROM users WHERE email='public2@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-109'),
   'Teal top woman at the pharmacy counter.', 'Teal top, white trousers', 'Stationary', NULL,
   NULL, 17.4175, 78.4360, 'Hyderabad — Jubilee pharmacy', now() - interval '30 hours', now() - interval '29 hours', 'MOBILE', 'VERIFIED',
   jsonb_build_object('quality', 0.86, 'gps_accuracy_m', 8, 'has_face', TRUE)),

  ('ST-1030', (SELECT id FROM users WHERE email='public3@missinglink.demo'), (SELECT id FROM missing_person_cases WHERE case_reference='MP-101'),
   'Unrelated sighting of a school group — likely not the missing child.', 'School uniform', 'Towards school', NULL,
   'Group of 12 children with a teacher.', 12.9745, 77.6440, 'Bengaluru — St. Marys school', now() - interval '2 hours', now() - interval '1 hour', 'WEB', 'REJECTED',
   jsonb_build_object('quality', 0.90, 'gps_accuracy_m', 9, 'has_face', TRUE));

-- ------------------------------------------------------------
-- Evidence for each sighting (synthetic storage keys)
-- ------------------------------------------------------------
INSERT INTO evidence (sighting_id, case_id, uploader_id, storage_key, original_filename, content_type, size_bytes, sha256, malware_scan_status, quality_score, uploaded_at)
SELECT s.id, s.case_id, s.submitter_id,
       'demo/sightings/' || lower(s.sighting_reference) || '/photo.jpg',
       lower(s.sighting_reference) || '-photo.jpg', 'image/jpeg', 480000,
       md5(s.sighting_reference), 'CLEAN', COALESCE((s.metadata->>'quality')::float, 0.6), s.reported_at
FROM sightings s
WHERE s.status <> 'REJECTED';

-- ------------------------------------------------------------
-- Evidence clusters (duplicate detection demo)
-- ------------------------------------------------------------
INSERT INTO evidence_clusters (title, centroid, first_timestamp, last_timestamp, source_count, avg_similarity, meta)
VALUES
  ('Evidence Cluster #24 — Bengaluru bus-stop sighting', ST_SetSRID(ST_MakePoint(77.6380, 12.9701), 4326),
   now() - interval '4 hours 30 minutes', now() - interval '4 hours', 3, 0.81,
   jsonb_build_object('sighting_refs', '["ST-1001","ST-1002","ST-1003"]')),
  ('Evidence Cluster #31 — Delhi metro sighting', ST_SetSRID(ST_MakePoint(77.2835, 28.5641), 4326),
   now() - interval '48 hours', now() - interval '40 hours', 3, 0.74,
   jsonb_build_object('sighting_refs', '["ST-1007","ST-1008","ST-1009"]')),
  ('Evidence Cluster #42 — Kolkata lake sighting', ST_SetSRID(ST_MakePoint(88.4310, 22.5815), 4326),
   now() - interval '9 hours', now() - interval '6 hours', 2, 0.79,
   jsonb_build_object('sighting_refs', '["ST-1014","ST-1015","ST-1025"]'));

UPDATE sightings SET evidence_cluster_id = c.id
FROM evidence_clusters c
WHERE c.meta->>'sighting_refs' LIKE '%' || sightings.sighting_reference || '%';

-- ------------------------------------------------------------
-- Potential matches (AI lead queue) — explanations + limitations
-- ------------------------------------------------------------
INSERT INTO potential_matches
  (case_id, sighting_id, evidence_id, overall_score, face_similarity, clothing_similarity,
   accessory_similarity, body_similarity, image_similarity, location_relevance, time_relevance,
   text_similarity, status, explanation, limitations, model_version_id, created_at)
SELECT
  c.id, s.id, e.id,
  round(0.84::numeric, 2), 0.82, 0.76, 0.70, 0.72, 0.81, 0.91, 0.88, 0.74,
  'AWAITING_REVIEW',
  jsonb_build_array('High visual similarity between sighting and case photo', 'Similar clothing (blue uniform)', 'Within configured geographic radius', 'Time interval is relevant'),
  jsonb_build_array('Image quality is moderate', 'Face partially obscured', 'Lighting differs', 'Location accuracy ~12 m'),
  (SELECT id FROM model_versions WHERE version='v1.0.0'), now() - interval '4 hours'
FROM missing_person_cases c, sightings s, evidence e
WHERE c.case_reference='MP-101' AND s.sighting_reference='ST-1001' AND e.sighting_id=s.id;

INSERT INTO potential_matches
  (case_id, sighting_id, evidence_id, overall_score, face_similarity, clothing_similarity,
   accessory_similarity, body_similarity, image_similarity, location_relevance, time_relevance,
   text_similarity, status, explanation, limitations, model_version_id, created_at)
SELECT
  c.id, s.id, e.id,
  round(0.76::numeric, 2), 0.71, 0.74, 0.66, 0.68, 0.72, 0.85, 0.80, 0.69,
  'AWAITING_REVIEW',
  jsonb_build_array('Moderate face similarity (verify carefully)', 'Similar clothing', 'Geographic proximity to last known location'),
  jsonb_build_array('Low image resolution', 'No clear face visible'),
  (SELECT id FROM model_versions WHERE version='v1.0.0'), now() - interval '4 hours'
FROM missing_person_cases c, sightings s, evidence e
WHERE c.case_reference='MP-101' AND s.sighting_reference='ST-1002' AND e.sighting_id=s.id;

INSERT INTO potential_matches
  (case_id, sighting_id, evidence_id, overall_score, face_similarity, clothing_similarity,
   accessory_similarity, body_similarity, image_similarity, location_relevance, time_relevance,
   text_similarity, status, explanation, limitations, model_version_id, created_at)
SELECT
  c.id, s.id, e.id,
  round(0.61::numeric, 2), 0.52, 0.71, 0.62, 0.60, 0.63, 0.80, 0.74, 0.61,
  'AWAITING_REVIEW',
  jsonb_build_array('Similar clothing', 'Within geographic radius'),
  jsonb_build_array('Face not clearly visible', 'Likely duplicate of ST-1001/ST-1002'),
  (SELECT id FROM model_versions WHERE version='v1.0.0'), now() - interval '3 hours'
FROM missing_person_cases c, sightings s, evidence e
WHERE c.case_reference='MP-101' AND s.sighting_reference='ST-1003' AND e.sighting_id=s.id;

INSERT INTO potential_matches
  (case_id, sighting_id, evidence_id, overall_score, face_similarity, clothing_similarity,
   accessory_similarity, body_similarity, image_similarity, location_relevance, time_relevance,
   text_similarity, status, explanation, limitations, model_version_id, created_at)
SELECT
  c.id, s.id, e.id,
  round(0.72::numeric, 2), 0.65, 0.73, 0.68, 0.64, 0.70, 0.88, 0.82, 0.72,
  'AWAITING_REVIEW',
  jsonb_build_array('Moderate face similarity', 'Similar clothing (white kurta)', 'Within geographic radius', 'Time interval relevant'),
  jsonb_build_array('Elderly persons commonly similar', 'Image lighting differs'),
  (SELECT id FROM model_versions WHERE version='v1.0.0'), now() - interval '24 hours'
FROM missing_person_cases c, sightings s, evidence e
WHERE c.case_reference='MP-102' AND s.sighting_reference='ST-1004' AND e.sighting_id=s.id;

INSERT INTO potential_matches
  (case_id, sighting_id, evidence_id, overall_score, face_similarity, clothing_similarity,
   accessory_similarity, body_similarity, image_similarity, location_relevance, time_relevance,
   text_similarity, status, explanation, limitations, model_version_id, created_at)
SELECT
  c.id, s.id, e.id,
  round(0.88::numeric, 2), 0.86, 0.80, 0.72, 0.78, 0.85, 0.93, 0.90, 0.78,
  'ACCEPTED',
  jsonb_build_array('High visual similarity', 'Similar clothing and accessories', 'Very close to last known area', 'Time interval relevant'),
  jsonb_build_array('Low sample count (single photo)'),
  (SELECT id FROM model_versions WHERE version='v1.0.0'), now() - interval '21 hours'
FROM missing_person_cases c, sightings s, evidence e
WHERE c.case_reference='MP-102' AND s.sighting_reference='ST-1005' AND e.sighting_id=s.id;

INSERT INTO potential_matches
  (case_id, sighting_id, evidence_id, overall_score, face_similarity, clothing_similarity,
   accessory_similarity, body_similarity, image_similarity, location_relevance, time_relevance,
   text_similarity, status, explanation, limitations, model_version_id, created_at)
SELECT
  c.id, s.id, e.id,
  round(0.55::numeric, 2), 0.42, 0.65, 0.55, 0.58, 0.60, 0.79, 0.71, 0.58,
  'REJECTED',
  jsonb_build_array('Low face similarity', 'Generic clothing match only'),
  jsonb_build_array('Low confidence signal', 'Poor image quality'),
  (SELECT id FROM model_versions WHERE version='v1.0.0'), now() - interval '19 hours'
FROM missing_person_cases c, sightings s, evidence e
WHERE c.case_reference='MP-102' AND s.sighting_reference='ST-1006' AND e.sighting_id=s.id;

INSERT INTO potential_matches
  (case_id, sighting_id, evidence_id, overall_score, face_similarity, clothing_similarity,
   accessory_similarity, body_similarity, image_similarity, location_relevance, time_relevance,
   text_similarity, status, explanation, limitations, model_version_id, created_at)
SELECT
  c.id, s.id, e.id,
  round(0.91::numeric, 2), 0.89, 0.82, 0.78, 0.80, 0.87, 0.90, 0.86, 0.80,
  'AWAITING_REVIEW',
  jsonb_build_array('High face similarity', 'High clothing similarity (denim jacket)', 'Accessory match (beige tote)', 'Within geographic radius', 'Time interval relevant'),
  jsonb_build_array('High quality image', 'Human review still required'),
  (SELECT id FROM model_versions WHERE version='v1.0.0'), now() - interval '46 hours'
FROM missing_person_cases c, sightings s, evidence e
WHERE c.case_reference='MP-103' AND s.sighting_reference='ST-1007' AND e.sighting_id=s.id;

INSERT INTO potential_matches
  (case_id, sighting_id, evidence_id, overall_score, face_similarity, clothing_similarity,
   accessory_similarity, body_similarity, image_similarity, location_relevance, time_relevance,
   text_similarity, status, explanation, limitations, model_version_id, created_at)
SELECT
  c.id, s.id, e.id,
  round(0.67::numeric, 2), 0.58, 0.74, 0.70, 0.66, 0.69, 0.84, 0.79, 0.65,
  'MORE_INFO',
  jsonb_build_array('Similar clothing', 'Similar accessories'),
  jsonb_build_array('Face not visible', 'Requested additional angle/photo'),
  (SELECT id FROM model_versions WHERE version='v1.0.0'), now() - interval '42 hours'
FROM missing_person_cases c, sightings s, evidence e
WHERE c.case_reference='MP-103' AND s.sighting_reference='ST-1008' AND e.sighting_id=s.id;

INSERT INTO potential_matches
  (case_id, sighting_id, evidence_id, overall_score, face_similarity, clothing_similarity,
   accessory_similarity, body_similarity, image_similarity, location_relevance, time_relevance,
   text_similarity, status, explanation, limitations, model_version_id, created_at)
SELECT
  c.id, s.id, e.id,
  round(0.83::numeric, 2), 0.79, 0.78, 0.72, 0.76, 0.80, 0.87, 0.83, 0.73,
  'AWAITING_REVIEW',
  jsonb_build_array('High visual similarity', 'Similar clothing', 'Near last known area'),
  jsonb_build_array('CCTV-style lower resolution', 'Angle differs from case photo'),
  (SELECT id FROM model_versions WHERE version='v1.0.0'), now() - interval '8 hours'
FROM missing_person_cases c, sightings s, evidence e
WHERE c.case_reference='MP-106' AND s.sighting_reference='ST-1014' AND e.sighting_id=s.id;

INSERT INTO potential_matches
  (case_id, sighting_id, evidence_id, overall_score, face_similarity, clothing_similarity,
   accessory_similarity, body_similarity, image_similarity, location_relevance, time_relevance,
   text_similarity, status, explanation, limitations, model_version_id, created_at)
SELECT
  c.id, s.id, e.id,
  round(0.78::numeric, 2), 0.74, 0.76, 0.69, 0.72, 0.76, 0.86, 0.81, 0.71,
  'AWAITING_REVIEW',
  jsonb_build_array('Moderate face similarity', 'Similar clothing (red polo)', 'Geographic proximity'),
  jsonb_build_array('Lighting differs', 'Backpack not clearly visible'),
  (SELECT id FROM model_versions WHERE version='v1.0.0'), now() - interval '7 hours'
FROM missing_person_cases c, sightings s, evidence e
WHERE c.case_reference='MP-106' AND s.sighting_reference='ST-1015' AND e.sighting_id=s.id;

INSERT INTO potential_matches
  (case_id, sighting_id, evidence_id, overall_score, face_similarity, clothing_similarity,
   accessory_similarity, body_similarity, image_similarity, location_relevance, time_relevance,
   text_similarity, status, explanation, limitations, model_version_id, created_at)
SELECT
  c.id, s.id, e.id,
  round(0.86::numeric, 2), 0.83, 0.80, 0.74, 0.77, 0.83, 0.92, 0.89, 0.77,
  'ACCEPTED',
  jsonb_build_array('High visual similarity', 'Similar clothing (teal top)', 'Near verified route', 'Time interval relevant'),
  jsonb_build_array('Human-verified', 'Follow-up recommended'),
  (SELECT id FROM model_versions WHERE version='v1.0.0'), now() - interval '29 hours'
FROM missing_person_cases c, sightings s, evidence e
WHERE c.case_reference='MP-109' AND s.sighting_reference='ST-1029' AND e.sighting_id=s.id;

-- ------------------------------------------------------------
-- Verification records (matching the accepted/rejected/more_info)
-- ------------------------------------------------------------
INSERT INTO verification_records (potential_match_id, reviewer_id, decision, notes, created_at)
SELECT pm.id, (SELECT id FROM users WHERE email='investigator@missinglink.demo'),
       'ACCEPT', 'Confirmed via follow-up interview; clothing and description match. Sent to field team.', now() - interval '20 hours'
FROM potential_matches pm
JOIN sightings s ON s.id = pm.sighting_id
WHERE s.sighting_reference='ST-1005';

INSERT INTO verification_records (potential_match_id, reviewer_id, decision, notes, created_at)
SELECT pm.id, (SELECT id FROM users WHERE email='investigator@missinglink.demo'),
       'REJECT', 'Person identified as a different local resident; no match.', now() - interval '18 hours'
FROM potential_matches pm
JOIN sightings s ON s.id = pm.sighting_id
WHERE s.sighting_reference='ST-1006';

INSERT INTO verification_records (potential_match_id, reviewer_id, decision, notes, created_at)
SELECT pm.id, (SELECT id FROM users WHERE email='investigator@missinglink.demo'),
       'MORE_INFO', 'Requesting sharper photograph or timestamp from reporter.', now() - interval '40 hours'
FROM potential_matches pm
JOIN sightings s ON s.id = pm.sighting_id
WHERE s.sighting_reference='ST-1008';

INSERT INTO verification_records (potential_match_id, reviewer_id, decision, notes, created_at)
SELECT pm.id, (SELECT id FROM users WHERE email='investigator@missinglink.demo'),
       'ACCEPT', 'Strong match; alerting field team for interview.', now() - interval '28 hours'
FROM potential_matches pm
JOIN sightings s ON s.id = pm.sighting_id
WHERE s.sighting_reference='ST-1029';

-- ------------------------------------------------------------
-- Locations (geo intelligence)
-- ------------------------------------------------------------
INSERT INTO locations (case_id, geom, label, location_type, accuracy_meters, occurred_at)
SELECT c.id, ST_SetSRID(ST_MakePoint(c.last_known_lng, c.last_known_lat), 4326), c.last_known_place, 'LAST_KNOWN', 50, c.last_known_at
FROM missing_person_cases c;

INSERT INTO locations (sighting_id, case_id, geom, label, location_type, accuracy_meters, occurred_at)
SELECT s.id, s.case_id, ST_SetSRID(ST_MakePoint(s.lng, s.lat), 4326), s.location_name, 'SIGHTING',
       COALESCE((s.metadata->>'gps_accuracy_m')::int, 25), s.captured_at
FROM sightings s WHERE s.lat IS NOT NULL AND s.status <> 'REJECTED';

-- ------------------------------------------------------------
-- Search zones (AI-assisted, requires investigator review)
-- ------------------------------------------------------------
INSERT INTO search_zones (case_id, zone_type, priority, radius_km, geom, rationale, ai_generated, reviewed)
SELECT c.id, 'HIGH_PRIORITY', 1, 2.5,
       ST_Buffer(ST_SetSRID(ST_MakePoint(c.last_known_lng, c.last_known_lat), 4326)::geography, 2500)::geometry,
       'Within walking distance of last known location; high concentration of sightings.', TRUE, FALSE
FROM missing_person_cases c WHERE c.case_reference='MP-101';

INSERT INTO search_zones (case_id, zone_type, priority, radius_km, geom, rationale, ai_generated, reviewed)
SELECT c.id, 'MEDIUM_PRIORITY', 2, 6.0,
       ST_Buffer(ST_SetSRID(ST_MakePoint(c.last_known_lng, c.last_known_lat), 4326)::geography, 6000)::geometry,
       'Public-transport reachable range given elapsed time.', TRUE, FALSE
FROM missing_person_cases c WHERE c.case_reference='MP-101';

INSERT INTO search_zones (case_id, zone_type, priority, radius_km, geom, rationale, ai_generated, reviewed)
SELECT c.id, 'LEAD_CLUSTER', 1, 1.0,
       ST_Buffer(ST_SetSRID(ST_MakePoint(77.6380, 12.9701), 4326)::geography, 1000)::geometry,
       'Evidence cluster #24 — repeated sightings at bus stop.', TRUE, FALSE
FROM missing_person_cases c WHERE c.case_reference='MP-101';

INSERT INTO search_zones (case_id, zone_type, priority, radius_km, geom, rationale, ai_generated, reviewed)
SELECT c.id, 'HIGH_PRIORITY', 1, 3.0,
       ST_Buffer(ST_SetSRID(ST_MakePoint(c.last_known_lng, c.last_known_lat), 4326)::geography, 3000)::geometry,
       'Verified sighting cluster near temple; high confidence.', TRUE, TRUE
FROM missing_person_cases c WHERE c.case_reference='MP-102';

-- ------------------------------------------------------------
-- Case timeline
-- ------------------------------------------------------------
INSERT INTO case_timeline (case_id, actor_id, event_type, description, payload, created_at)
SELECT c.id, c.reporter_id, 'CASE_CREATED', 'Case reported by family member.', '{}'::jsonb, c.created_at
FROM missing_person_cases c;

INSERT INTO case_timeline (case_id, actor_id, event_type, description, payload, created_at)
SELECT c.id, u.id, 'SIGHTING_REPORTED', 'New potential sighting ' || s.sighting_reference || ' reported.', jsonb_build_object('sightingRef', s.sighting_reference), s.reported_at
FROM missing_person_cases c, sightings s, users u
WHERE s.case_id = c.id AND s.status <> 'REJECTED' AND u.email='investigator@missinglink.demo'
  AND s.sighting_reference IN ('ST-1001','ST-1004','ST-1007','ST-1014');

INSERT INTO case_timeline (case_id, actor_id, event_type, description, payload, created_at)
SELECT c.id, u.id, 'AI_ANALYSIS', 'AI similarity analysis completed; potential match queued for review.', jsonb_build_object('score', 0.84), now() - interval '4 hours'
FROM missing_person_cases c, users u WHERE c.case_reference='MP-101' AND u.email='investigator@missinglink.demo';

INSERT INTO case_timeline (case_id, actor_id, event_type, description, payload, created_at)
SELECT c.id, u.id, 'INVESTIGATOR_VERIFICATION', 'Investigator verified sighting ' || s.sighting_reference || '.', jsonb_build_object('decision','ACCEPT'), now() - interval '20 hours'
FROM missing_person_cases c, sightings s, users u
WHERE c.case_reference='MP-102' AND s.sighting_reference='ST-1005' AND u.email='investigator@missinglink.demo';

INSERT INTO case_timeline (case_id, actor_id, event_type, description, payload, created_at)
SELECT c.id, u.id, 'STATUS_CHANGED', 'Case marked LOCATED.', jsonb_build_object('status','LOCATED'), now() - interval '12 days'
FROM missing_person_cases c, users u WHERE c.case_reference='MP-110' AND u.email='investigator@missinglink.demo';
