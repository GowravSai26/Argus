-- Schema
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id      TEXT PRIMARY KEY,
    card_id             TEXT NOT NULL,
    merchant_id         TEXT NOT NULL,
    amount              NUMERIC(12, 2) NOT NULL,
    merchant_category   TEXT NOT NULL,
    merchant_country    TEXT NOT NULL,
    merchant_city       TEXT NOT NULL,
    cardholder_country  TEXT NOT NULL,
    timestamp           TIMESTAMPTZ NOT NULL,
    is_online           BOOLEAN NOT NULL DEFAULT FALSE,
    is_fraud            BOOLEAN NOT NULL DEFAULT FALSE,
    device_fingerprint  TEXT
);

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id             TEXT PRIMARY KEY,
    merchant_name           TEXT NOT NULL,
    category                TEXT NOT NULL,
    country                 TEXT NOT NULL,
    fraud_rate              NUMERIC(6, 4) NOT NULL DEFAULT 0.01,
    chargeback_rate         NUMERIC(6, 4) NOT NULL DEFAULT 0.005,
    is_high_risk            BOOLEAN NOT NULL DEFAULT FALSE,
    days_since_first_seen   INT NOT NULL DEFAULT 365
);

INSERT INTO merchants (merchant_id, merchant_name, category, country, fraud_rate, chargeback_rate, is_high_risk, days_since_first_seen)
SELECT DISTINCT ON (merchant_id)
    merchant_id, merchant_id, merchant_category, merchant_country,
    CASE WHEN merchant_category IN ('Electronics','Jewelry','Gift Cards','Crypto Exchange','Wire Transfer','Gambling','Adult Entertainment') THEN 0.07 ELSE 0.01 END,
    CASE WHEN merchant_category IN ('Electronics','Jewelry','Gift Cards','Crypto Exchange','Wire Transfer','Gambling','Adult Entertainment') THEN 0.04 ELSE 0.005 END,
    merchant_category IN ('Electronics','Jewelry','Gift Cards','Crypto Exchange','Wire Transfer','Gambling','Adult Entertainment'),
    365
FROM transactions ON CONFLICT DO NOTHING;

-- Schema
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id      TEXT PRIMARY KEY,
    card_id             TEXT NOT NULL,
    merchant_id         TEXT NOT NULL,
    amount              NUMERIC(12, 2) NOT NULL,
    merchant_category   TEXT NOT NULL,
    merchant_country    TEXT NOT NULL,
    merchant_city       TEXT NOT NULL,
    cardholder_country  TEXT NOT NULL,
    timestamp           TIMESTAMPTZ NOT NULL,
    is_online           BOOLEAN NOT NULL DEFAULT FALSE,
    is_fraud            BOOLEAN NOT NULL DEFAULT FALSE,
    device_fingerprint  TEXT
);

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id             TEXT PRIMARY KEY,
    merchant_name           TEXT NOT NULL,
    category                TEXT NOT NULL,
    country                 TEXT NOT NULL,
    fraud_rate              NUMERIC(6, 4) NOT NULL DEFAULT 0.01,
    chargeback_rate         NUMERIC(6, 4) NOT NULL DEFAULT 0.005,
    is_high_risk            BOOLEAN NOT NULL DEFAULT FALSE,
    days_since_first_seen   INT NOT NULL DEFAULT 365
);

INSERT INTO merchants (merchant_id, merchant_name, category, country, fraud_rate, chargeback_rate, is_high_risk, days_since_first_seen)
SELECT DISTINCT ON (merchant_id)
    merchant_id, merchant_id, merchant_category, merchant_country,
    CASE WHEN merchant_category IN ('Electronics','Jewelry','Gift Cards','Crypto Exchange','Wire Transfer','Gambling','Adult Entertainment') THEN 0.07 ELSE 0.01 END,
    CASE WHEN merchant_category IN ('Electronics','Jewelry','Gift Cards','Crypto Exchange','Wire Transfer','Gambling','Adult Entertainment') THEN 0.04 ELSE 0.005 END,
    merchant_category IN ('Electronics','Jewelry','Gift Cards','Crypto Exchange','Wire Transfer','Gambling','Adult Entertainment'),
    365
FROM transactions ON CONFLICT DO NOTHING;

-- Schema
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id      TEXT PRIMARY KEY,
    card_id             TEXT NOT NULL,
    merchant_id         TEXT NOT NULL,
    amount              NUMERIC(12, 2) NOT NULL,
    merchant_category   TEXT NOT NULL,
    merchant_country    TEXT NOT NULL,
    merchant_city       TEXT NOT NULL,
    cardholder_country  TEXT NOT NULL,
    timestamp           TIMESTAMPTZ NOT NULL,
    is_online           BOOLEAN NOT NULL DEFAULT FALSE,
    is_fraud            BOOLEAN NOT NULL DEFAULT FALSE,
    device_fingerprint  TEXT
);

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id             TEXT PRIMARY KEY,
    merchant_name           TEXT NOT NULL,
    category                TEXT NOT NULL,
    country                 TEXT NOT NULL,
    fraud_rate              NUMERIC(6, 4) NOT NULL DEFAULT 0.01,
    chargeback_rate         NUMERIC(6, 4) NOT NULL DEFAULT 0.005,
    is_high_risk            BOOLEAN NOT NULL DEFAULT FALSE,
    days_since_first_seen   INT NOT NULL DEFAULT 365
);

INSERT INTO merchants (merchant_id, merchant_name, category, country, fraud_rate, chargeback_rate, is_high_risk, days_since_first_seen)
SELECT DISTINCT ON (merchant_id)
    merchant_id, merchant_id, merchant_category, merchant_country,
    CASE WHEN merchant_category IN ('Electronics','Jewelry','Gift Cards','Crypto Exchange','Wire Transfer','Gambling','Adult Entertainment') THEN 0.07 ELSE 0.01 END,
    CASE WHEN merchant_category IN ('Electronics','Jewelry','Gift Cards','Crypto Exchange','Wire Transfer','Gambling','Adult Entertainment') THEN 0.04 ELSE 0.005 END,
    merchant_category IN ('Electronics','Jewelry','Gift Cards','Crypto Exchange','Wire Transfer','Gambling','Adult Entertainment'),
    365
FROM transactions ON CONFLICT DO NOTHING;

-- Auto-generated by data/generate.py
-- Do not edit manually

INSERT INTO transactions (
    transaction_id, card_id, merchant_id, amount,
    merchant_category, merchant_country, merchant_city,
    cardholder_country, timestamp, is_online, is_fraud, device_fingerprint
) VALUES
    ('txn_1b1b20de', 'card_dcc2a732', 'merch_d06ed5', 260.77, 'Clothing', 'AU', 'North Christinaland', 'AU', '2026-04-12T04:11:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_5782f6fd', 'card_ea5c47ea', 'merch_dc97fa', 126.52, 'Coffee Shop', 'GB', 'Kramerfurt', 'GB', '2026-04-05T17:41:53.679667+00:00', TRUE, FALSE, '43a8fa6c046749acb454c5a644e87a5b'),
    ('txn_f164152a', 'card_bf54a0ec', 'merch_64382f', 157.42, 'Pharmacy', 'AU', 'Lake Jasmin', 'AU', '2026-04-01T00:18:53.679667+00:00', TRUE, FALSE, '3529ac0d8c7a43f49bfa9084d28c8621'),
    ('txn_11f930f4', 'card_fa961563', 'merch_408866', 75.48, 'Grocery', 'JP', 'Moorebury', 'JP', '2026-03-21T22:22:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_60d31ed5', 'card_6a3dc2dc', 'merch_7ddd84', 110.59, 'Restaurant', 'GB', 'Danielchester', 'GB', '2026-03-25T06:25:53.679667+00:00', TRUE, FALSE, '88aa4625b9524b82b4f78ed6b1235206'),
    ('txn_1afd07a7', 'card_34b019a1', 'merch_dc97fa', 409.05, 'Coffee Shop', 'CA', 'Kramerfurt', 'CA', '2026-03-20T05:00:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_96345913', 'card_fd9c3b1c', 'merch_47d43c', 294.17, 'Gas Station', 'JP', 'West Mason', 'JP', '2026-03-23T17:17:53.679667+00:00', TRUE, FALSE, 'b1f7df870f23413eb72876a2f6a9b373'),
    ('txn_cae24774', 'card_2ee67105', 'merch_b59371', 128.84, 'Coffee Shop', 'AU', 'South Erinville', 'AU', '2026-04-10T17:17:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_bbc5dea5', 'card_aea25809', 'merch_e4756c', 97.96, 'Clothing', 'GB', 'Port Veronicaburgh', 'GB', '2026-04-10T04:09:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_67c8763c', 'card_513252aa', 'merch_e9518b', 187.35, 'Utilities', 'FR', 'Brownberg', 'FR', '2026-04-11T16:19:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_6ca8989c', 'card_ac7c594a', 'merch_e30eb4', 437.47, 'Gift Cards', 'JP', 'Goodwintown', 'JP', '2026-03-29T07:50:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_e3db0ea3', 'card_db26edc7', 'merch_5d5697', 111.64, 'Gas Station', 'JP', 'Lake Valeriefort', 'JP', '2026-03-20T06:00:53.679667+00:00', TRUE, FALSE, 'dc9664f5516f44819df61d05dc3a3e12'),
    ('txn_aebf5ad3', 'card_eb5ea5a9', 'merch_d0e067', 84.84, 'Utilities', 'AU', 'Port Jacqueline', 'AU', '2026-04-01T21:30:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_a4f93751', 'card_5f6ac5ec', 'merch_06cac5', 218.61, 'Restaurant', 'US', 'South Danielview', 'US', '2026-03-17T04:01:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_4d02f0c1', 'card_3c33b92f', 'merch_e9518b', 109.75, 'Utilities', 'JP', 'Brownberg', 'JP', '2026-03-14T23:43:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_e68309fd', 'card_21aaf908', 'merch_2abc8d', 213.36, 'Pharmacy', 'DE', 'Joshuafurt', 'DE', '2026-04-06T15:35:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_c8211255', 'card_5f045535', 'merch_b015a0', 40.77, 'Jewelry', 'DE', 'Lake Travis', 'DE', '2026-03-23T20:44:53.679667+00:00', TRUE, FALSE, 'b7162416f46c42859878fe1c7426eccf'),
    ('txn_9d7e3c91', 'card_434e19d2', 'merch_5d5697', 188.6, 'Gas Station', 'FR', 'Lake Valeriefort', 'FR', '2026-04-05T18:59:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_ce01d09e', 'card_ca840d9d', 'merch_8fc425', 80.81, 'Jewelry', 'JP', 'Kimmouth', 'JP', '2026-03-19T06:06:53.679667+00:00', TRUE, FALSE, 'acd766acf0f542cbbff53c1b2fdd394f'),
    ('txn_cb4bd58c', 'card_1d4ef56f', 'merch_8fc425', 161.05, 'Jewelry', 'CA', 'Kimmouth', 'CA', '2026-03-31T22:07:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_73d1a450', 'card_7b0b59fa', 'merch_619f3a', 159.27, 'Restaurant', 'FR', 'Bridgesberg', 'FR', '2026-03-29T08:04:53.679667+00:00', TRUE, FALSE, '52354d393b1a443fa7a4a8041b82104b'),
    ('txn_1365b0b7', 'card_a72fb3a7', 'merch_19f2c2', 47.02, 'Pharmacy', 'CA', 'New Joshua', 'CA', '2026-04-12T07:31:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_86182af8', 'card_af2cd7ae', 'merch_9227c0', 173.08, 'Healthcare', 'DE', 'Kevinside', 'DE', '2026-03-17T22:04:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_918df682', 'card_b03d8538', 'merch_9e3d8e', 124.12, 'Coffee Shop', 'US', 'South Brianstad', 'US', '2026-03-28T19:51:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_9df90883', 'card_b427e612', 'merch_7b1e16', 221.59, 'Healthcare', 'GB', 'Warrenville', 'GB', '2026-03-23T15:44:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_771f8d79', 'card_eb5ea5a9', 'merch_10fa4b', 74.4, 'Clothing', 'AU', 'Frankstad', 'AU', '2026-03-25T17:53:53.679667+00:00', TRUE, FALSE, '57cb69502a36464581224969cd4da556'),
    ('txn_10a3772b', 'card_c826c181', 'merch_430874', 73.4, 'Pharmacy', 'GB', 'West Deborah', 'GB', '2026-03-19T20:08:53.679667+00:00', TRUE, FALSE, '1b94594ae5e349b28be4b63f705a6cf5'),
    ('txn_93743b3d', 'card_d8d9cafd', 'merch_31e0ac', 80.41, 'Coffee Shop', 'FR', 'Savageville', 'FR', '2026-03-27T06:14:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_078de691', 'card_ac02ae1d', 'merch_49cccb', 143.16, 'Pharmacy', 'CA', 'New Valerie', 'CA', '2026-03-19T02:26:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_eed9a124', 'card_0a4b3255', 'merch_9227c0', 39.77, 'Healthcare', 'AU', 'Kevinside', 'AU', '2026-04-09T16:07:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_3b38062a', 'card_43d0ff27', 'merch_e4cb83', 360.65, 'Healthcare', 'FR', 'South Stephaniemouth', 'FR', '2026-03-26T22:34:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_74bb656a', 'card_ab0c4d21', 'merch_924fc5', 60.33, 'Utilities', 'US', 'East Michaelfurt', 'US', '2026-04-07T18:21:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_c52bf10a', 'card_5a3c7e4d', 'merch_e4756c', 190.51, 'Clothing', 'AU', 'Port Veronicaburgh', 'AU', '2026-03-21T21:23:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_86f57487', 'card_f592a753', 'merch_db8c65', 3190.03, 'Restaurant', 'ID', 'Patelchester', 'DE', '2026-03-22T08:21:53.679667+00:00', FALSE, TRUE, NULL),
    ('txn_d3be52a9', 'card_2a4da482', 'merch_775b07', 137.44, 'Adult Entertainment', 'JP', 'New Anna', 'JP', '2026-03-15T19:51:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_975e0aa4', 'card_860cfb26', 'merch_6238d2', 193.16, 'Adult Entertainment', 'AU', 'Hannahview', 'AU', '2026-04-03T01:34:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_2088f44a', 'card_02819373', 'merch_9b6e9e', 245.86, 'Utilities', 'AU', 'North Pamelaberg', 'AU', '2026-03-22T16:54:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_346c8c0c', 'card_d3c87f90', 'merch_ad2f3c', 192.1, 'Grocery', 'DE', 'West Ronaldport', 'DE', '2026-03-29T16:41:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_80d4f901', 'card_d8d9cafd', 'merch_4cbbe5', 88.3, 'Wire Transfer', 'FR', 'Munozside', 'FR', '2026-03-27T19:38:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_ad7de1cd', 'card_ac02ae1d', 'merch_e9518b', 79.32, 'Utilities', 'CA', 'Brownberg', 'CA', '2026-03-23T20:10:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_6caa5f04', 'card_1d02d5b7', 'merch_9ca163', 456.92, 'Grocery', 'AU', 'South Pennyberg', 'AU', '2026-03-19T03:34:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_ca955487', 'card_eb5ea5a9', 'merch_7b9b33', 41.46, 'Pharmacy', 'AU', 'Smithtown', 'AU', '2026-03-25T17:53:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_aaea1d16', 'card_2dc545d0', 'merch_3e1291', 2197.26, 'Crypto Exchange', 'PK', 'Lake Alex', 'JP', '2026-04-10T11:31:53.679667+00:00', TRUE, TRUE, 'bcfe8264eebd478b88f093df8e2f12e7'),
    ('txn_ba58a7fa', 'card_5301584a', 'merch_ff328e', 164.82, 'Clothing', 'DE', 'West Christopherville', 'DE', '2026-04-11T01:38:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_504dec6e', 'card_dcb9fbb4', 'merch_b0d46b', 228.58, 'Pharmacy', 'FR', 'New Samanthafort', 'FR', '2026-04-08T07:17:53.679667+00:00', TRUE, FALSE, '1cf4a40124774ebc8527a7429f934df4'),
    ('txn_e727fcd0', 'card_e205d97d', 'merch_408866', 91.74, 'Grocery', 'FR', 'Moorebury', 'FR', '2026-04-01T02:08:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_e4d444be', 'card_94f9dc29', 'merch_49cccb', 193.94, 'Pharmacy', 'GB', 'New Valerie', 'GB', '2026-03-26T08:15:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_d807339b', 'card_dd9cc0c9', 'merch_945725', 359.12, 'Gift Cards', 'CA', 'Johnsonchester', 'CA', '2026-04-10T02:17:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_4d78ee67', 'card_98cbd4d0', 'merch_8fc425', 42.47, 'Jewelry', 'AU', 'Kimmouth', 'AU', '2026-04-06T19:20:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_5ee29ec7', 'card_41a5bc96', 'merch_62ed6e', 236.87, 'Healthcare', 'US', 'Leonardbury', 'US', '2026-03-18T21:40:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_efe0ae59', 'card_831a2b9d', 'merch_49cccb', 112.97, 'Pharmacy', 'JP', 'New Valerie', 'JP', '2026-04-14T01:35:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_af3d8cd7', 'card_9abaffe3', 'merch_9e3d8e', 299.67, 'Coffee Shop', 'FR', 'South Brianstad', 'FR', '2026-03-20T02:29:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_79e94811', 'card_45516476', 'merch_c0f621', 82.65, 'Gas Station', 'US', 'West Williamport', 'US', '2026-04-03T16:52:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_464d303a', 'card_78284422', 'merch_19f2c2', 324.04, 'Pharmacy', 'CA', 'New Joshua', 'CA', '2026-03-27T20:12:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_80dd2569', 'card_998ac112', 'merch_6238d2', 1179.63, 'Adult Entertainment', 'RO', 'Hannahview', 'US', '2026-03-25T10:58:53.679667+00:00', TRUE, TRUE, '884eb199ce4140d1b207bb9da7c54fb4'),
    ('txn_fdb0a840', 'card_4d4b8fe8', 'merch_4cbbe5', 317.5, 'Wire Transfer', 'DE', 'Munozside', 'DE', '2026-03-14T15:53:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_d404b056', 'card_6330f1e7', 'merch_0d70fd', 2882.38, 'Electronics', 'UA', 'Lake Frank', 'FR', '2026-03-23T09:51:53.679667+00:00', TRUE, TRUE, '6f23b810edd44306801b9b58adfcc7aa'),
    ('txn_31318d66', 'card_65be8ea8', 'merch_25ef11', 366.7, 'Restaurant', 'AU', 'Thompsonville', 'AU', '2026-04-12T18:52:53.679667+00:00', TRUE, FALSE, 'bb95497e087d4ca985728a6d70a8d66d'),
    ('txn_70d390ed', 'card_5099adaa', 'merch_b37ef0', 136.23, 'Grocery', 'DE', 'Denniston', 'DE', '2026-03-23T03:24:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_c6516676', 'card_0d4c1ca2', 'merch_4b33d5', 82.78, 'Restaurant', 'DE', 'Stevenbury', 'DE', '2026-03-23T18:00:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_6a83c94f', 'card_c8d3b7f8', 'merch_d4795e', 2323.75, 'Restaurant', 'VN', 'Beststad', 'GB', '2026-03-16T05:19:53.679667+00:00', TRUE, TRUE, '66002eeed3a14b8f92fdc2a085c335b1'),
    ('txn_099afe0c', 'card_b95e7439', 'merch_5ea0f6', 295.96, 'Pharmacy', 'DE', 'Maryport', 'DE', '2026-03-24T19:16:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_6271acb6', 'card_9bb5a457', 'merch_c3ca92', 283.18, 'Pharmacy', 'CA', 'South Michael', 'CA', '2026-04-02T06:36:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_a72b6a34', 'card_416886fe', 'merch_19f2c2', 139.55, 'Pharmacy', 'FR', 'New Joshua', 'FR', '2026-04-04T16:30:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_aa012e8c', 'card_f097c4b0', 'merch_76a024', 228.78, 'Utilities', 'CA', 'Hahnview', 'CA', '2026-04-06T04:18:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_2e7d3e7e', 'card_e51df855', 'merch_e4cb83', 122.92, 'Healthcare', 'GB', 'South Stephaniemouth', 'GB', '2026-03-27T01:43:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_1a98ee60', 'card_ac8ac658', 'merch_ad2f3c', 273.84, 'Grocery', 'JP', 'West Ronaldport', 'JP', '2026-03-31T02:22:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_45b943d7', 'card_f592a753', 'merch_b92e84', 38.63, 'Clothing', 'DE', 'North Michael', 'DE', '2026-04-03T04:08:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_89fc762b', 'card_0672430f', 'merch_bd47ce', 122.75, 'Clothing', 'JP', 'West Jasmineville', 'JP', '2026-03-22T02:54:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_b7cb051b', 'card_ac02ae1d', 'merch_b92e84', 93.94, 'Clothing', 'CA', 'North Michael', 'CA', '2026-04-08T01:10:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_fd2bef89', 'card_7b0b59fa', 'merch_d0e067', 1705.87, 'Utilities', 'VN', 'Port Jacqueline', 'FR', '2026-04-03T14:06:53.679667+00:00', TRUE, TRUE, '37d3ca1f5642488f8be6636c4a40678f'),
    ('txn_01b55188', 'card_6a9867e0', 'merch_7587bb', 73.9, 'Pharmacy', 'DE', 'New Hollymouth', 'DE', '2026-03-29T03:07:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_4c17a882', 'card_7956a9b5', 'merch_a066e5', 114.25, 'Utilities', 'GB', 'New Victoria', 'GB', '2026-04-01T07:45:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_53e04687', 'card_48b5f749', 'merch_bd47ce', 212.43, 'Clothing', 'US', 'West Jasmineville', 'US', '2026-04-09T02:14:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_e3baa53c', 'card_dd673255', 'merch_adbf0f', 108.14, 'Pharmacy', 'DE', 'Port Kathyfurt', 'DE', '2026-04-11T22:55:53.679667+00:00', TRUE, FALSE, 'c606e8b21cd546b89e0f7af8e9f169b4'),
    ('txn_a72f5397', 'card_aadbae04', 'merch_5ea0f6', 46.35, 'Pharmacy', 'CA', 'Maryport', 'CA', '2026-03-23T06:28:53.679667+00:00', TRUE, FALSE, '6ded8161f62d4e57959a631b615e7cfa'),
    ('txn_340616e0', 'card_8b840045', 'merch_5ea0f6', 82.95, 'Pharmacy', 'AU', 'Maryport', 'AU', '2026-03-17T02:35:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_ce8128ea', 'card_7b0b59fa', 'merch_c0f621', 114.39, 'Gas Station', 'FR', 'West Williamport', 'FR', '2026-03-17T19:38:53.679667+00:00', TRUE, FALSE, 'f4f6f147c4c34a3687d25f194886be4b'),
    ('txn_481399d2', 'card_62daa61c', 'merch_0ee1c4', 89.54, 'Gas Station', 'JP', 'Port Kaylamouth', 'JP', '2026-03-25T05:40:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_da03bdf8', 'card_fdcece07', 'merch_64382f', 82.08, 'Pharmacy', 'AU', 'Lake Jasmin', 'AU', '2026-04-13T21:49:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_f5c75ea8', 'card_f097c4b0', 'merch_684564', 350.71, 'Grocery', 'CA', 'West Stephenstad', 'CA', '2026-04-06T06:55:53.679667+00:00', TRUE, FALSE, 'ba7d0ae1279f45f3bb6f05838e3654b3'),
    ('txn_fff225ee', 'card_e205d97d', 'merch_42cf7f', 302.38, 'Restaurant', 'FR', 'West Timothyfurt', 'FR', '2026-03-17T21:56:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_3fc0b470', 'card_a08605a7', 'merch_e9518b', 134.21, 'Utilities', 'CA', 'Brownberg', 'CA', '2026-03-28T21:47:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_7bcfe58f', 'card_860cfb26', 'merch_e58181', 4315.05, 'Crypto Exchange', 'VN', 'Lake Samuel', 'AU', '2026-03-19T05:38:53.679667+00:00', TRUE, TRUE, '6aaf0f9177404aa0b7abc293de1f2906'),
    ('txn_63fa9a67', 'card_c22fc07e', 'merch_f11bca', 140.55, 'Wire Transfer', 'DE', 'West Amandaton', 'DE', '2026-03-17T05:57:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_1819af46', 'card_2da3dbb2', 'merch_d47d95', 97.08, 'Utilities', 'AU', 'Lake Rachelberg', 'AU', '2026-04-06T04:53:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_542b3dd3', 'card_ae262f82', 'merch_b015a0', 235.14, 'Jewelry', 'JP', 'Lake Travis', 'JP', '2026-04-12T17:25:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_bc0f015c', 'card_2ee67105', 'merch_090d29', 171.5, 'Gas Station', 'AU', 'Melissashire', 'AU', '2026-03-16T04:07:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_a425f58f', 'card_57ee0c3d', 'merch_b92e84', 49.38, 'Clothing', 'DE', 'North Michael', 'DE', '2026-04-07T07:54:53.679667+00:00', TRUE, FALSE, '7eed2a884dca4a2ea56efa7e6a98f71f'),
    ('txn_9938cae3', 'card_61da8f58', 'merch_e58181', 199.22, 'Crypto Exchange', 'GB', 'Lake Samuel', 'GB', '2026-04-08T07:28:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_d540abef', 'card_ea5c47ea', 'merch_bd47ce', 128.16, 'Clothing', 'GB', 'West Jasmineville', 'GB', '2026-03-16T19:12:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_06c89380', 'card_ab3f1ed6', 'merch_9b6e9e', 67.66, 'Utilities', 'DE', 'North Pamelaberg', 'DE', '2026-03-31T06:41:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_4ef18532', 'card_fd9c3b1c', 'merch_446350', 272.85, 'Clothing', 'JP', 'Lake Steveport', 'JP', '2026-03-23T17:10:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_6a697e40', 'card_ad7556c0', 'merch_2c126c', 2043.85, 'Wire Transfer', 'NG', 'New Johnny', 'CA', '2026-03-20T08:34:53.679667+00:00', TRUE, TRUE, 'aca7001741fb479bad719dec4ce7e36d'),
    ('txn_4048af76', 'card_746740f4', 'merch_684564', 49.81, 'Grocery', 'JP', 'West Stephenstad', 'JP', '2026-03-28T23:10:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_12a6c303', 'card_b3bc60da', 'merch_ad705a', 136.83, 'Coffee Shop', 'US', 'North Marioville', 'US', '2026-03-14T21:47:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_788dc915', 'card_d3c87f90', 'merch_b4273e', 211.81, 'Restaurant', 'DE', 'Meganburgh', 'DE', '2026-04-07T17:55:53.679667+00:00', TRUE, FALSE, '52a897b5bc114e66a3361dd3ce607eb8'),
    ('txn_569d5f24', 'card_48b5f749', 'merch_9227c0', 132.99, 'Healthcare', 'US', 'Kevinside', 'US', '2026-03-23T06:52:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_b558b921', 'card_4d4b8fe8', 'merch_7587bb', 218.87, 'Pharmacy', 'DE', 'New Hollymouth', 'DE', '2026-03-26T03:13:53.679667+00:00', FALSE, FALSE, NULL),
    ('txn_1db8541b', 'card_ab0c4d21', 'merch_6c3798', 170.55, 'Gift Cards', 'US', 'Welchshire', 'US', '2026-04-12T18:02:53.679667+00:00', FALSE, FALSE, NULL);