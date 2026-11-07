"""Create REBIRTH schema — empty independent database."""
from __future__ import annotations

SCHEMA_SQL = [
"""CREATE TABLE IF NOT EXISTS world_meta (
    id INTEGER PRIMARY KEY CHECK (id=1),
    started_at TEXT NOT NULL,
    war_enabled INTEGER NOT NULL DEFAULT 1,
    nuclear_enabled INTEGER NOT NULL DEFAULT 0,
    last_daily_date TEXT,
    log_flags_json TEXT,
    main_group_id TEXT,
    reset_count INTEGER NOT NULL DEFAULT 0,
    bot_version TEXT
)""",
"""CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    username TEXT,
    display_name TEXT,
    country_code TEXT,
    is_banned INTEGER NOT NULL DEFAULT 0,
    ban_reason TEXT,
    destroy_cooldown_until TEXT,
    created_at TEXT,
    last_seen_at TEXT
)""",
"""CREATE TABLE IF NOT EXISTS countries (
    country_code TEXT PRIMARY KEY,
    name_fa TEXT NOT NULL,
    name_en TEXT,
    flag TEXT,
    capital_fa TEXT,
    leader_fa TEXT,
    leader_title_fa TEXT,
    currency_code TEXT,
    currency_name_fa TEXT,
    npt_member INTEGER NOT NULL DEFAULT 0,
    owner_player_id INTEGER,
    treasury REAL NOT NULL DEFAULT 0,
    daily_income REAL NOT NULL DEFAULT 0,
    daily_expense REAL NOT NULL DEFAULT 0,
    hp REAL NOT NULL DEFAULT 1000,
    max_hp REAL NOT NULL DEFAULT 1000,
    is_destroyed INTEGER NOT NULL DEFAULT 0,
    entity_type TEXT NOT NULL DEFAULT 'country',
    double_hp INTEGER NOT NULL DEFAULT 0,
    claimed_at TEXT,
    peace_penalty_until TEXT
)""",
"""CREATE TABLE IF NOT EXISTS inventory (
    country_code TEXT NOT NULL,
    item_code TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (country_code, item_code)
)""",
"""CREATE TABLE IF NOT EXISTS shop_catalog (
    item_code TEXT PRIMARY KEY,
    category TEXT,
    name_fa TEXT,
    description_fa TEXT,
    unit_price REAL,
    max_per_order INTEGER,
    power_score REAL,
    damage REAL,
    defense REAL,
    accuracy REAL,
    technology_level INTEGER,
    consumption_type TEXT,
    daily_income REAL,
    maintenance REAL,
    is_building INTEGER
)""",
"""CREATE TABLE IF NOT EXISTS cart (
    player_id INTEGER NOT NULL,
    item_code TEXT NOT NULL,
    quantity REAL NOT NULL,
    PRIMARY KEY (player_id, item_code)
)""",
"""CREATE TABLE IF NOT EXISTS market (
    id INTEGER PRIMARY KEY,
    seller_code TEXT,
    item_code TEXT,
    quantity REAL,
    unit_price REAL,
    active INTEGER DEFAULT 1,
    created_at TEXT
)""",
"""CREATE TABLE IF NOT EXISTS daily_payouts (
    country_code TEXT NOT NULL,
    payout_date TEXT NOT NULL,
    amount REAL NOT NULL,
    PRIMARY KEY (country_code, payout_date)
)""",
"""CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT,
    message TEXT,
    country_code TEXT,
    player_id INTEGER,
    created_at TEXT
)""",
"""CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT
)""",
"""CREATE TABLE IF NOT EXISTS alliances (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    founder_code TEXT NOT NULL,
    owner_code TEXT NOT NULL,
    member_cap INTEGER NOT NULL DEFAULT 5,
    treasury_cap REAL NOT NULL DEFAULT 100000000,
    treasury REAL NOT NULL DEFAULT 0,
    created_at TEXT,
    dissolved INTEGER NOT NULL DEFAULT 0
)""",
"""CREATE TABLE IF NOT EXISTS alliance_members (
    alliance_id INTEGER NOT NULL,
    country_code TEXT NOT NULL,
    role TEXT DEFAULT 'member',
    joined_at TEXT,
    PRIMARY KEY (alliance_id, country_code)
)""",
"""CREATE TABLE IF NOT EXISTS wars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attacker TEXT,
    defender TEXT,
    status TEXT,
    created_at TEXT,
    report TEXT
)""",
"""CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY,
    player_id INTEGER NOT NULL,
    username TEXT,
    display_name TEXT,
    amount REAL NOT NULL,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by INTEGER,
    show_name INTEGER NOT NULL DEFAULT 1
)""",
"""CREATE TABLE IF NOT EXISTS legendary_items (
    player_id INTEGER NOT NULL,
    item_code TEXT NOT NULL,
    uses_left INTEGER NOT NULL DEFAULT 20,
    PRIMARY KEY (player_id, item_code)
)""",
"""CREATE TABLE IF NOT EXISTS player_wallet (
    player_id INTEGER PRIMARY KEY,
    balance REAL NOT NULL DEFAULT 0
)""",
"""CREATE TABLE IF NOT EXISTS owner_inbox (
    id INTEGER PRIMARY KEY,
    kind TEXT,
    ref_id INTEGER,
    title TEXT,
    body TEXT,
    created_at TEXT,
    delivered INTEGER DEFAULT 0
)""",
"""CREATE TABLE IF NOT EXISTS peace_treaties (
    id INTEGER PRIMARY KEY,
    country_a TEXT,
    country_b TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT
)""",
"""CREATE TABLE IF NOT EXISTS country_control (
    country_code TEXT PRIMARY KEY,
    base_daily_income REAL,
    internet_on INTEGER DEFAULT 1,
    flights_open INTEGER DEFAULT 1,
    sea_open INTEGER DEFAULT 1,
    satisfaction REAL DEFAULT 70
)""",
"""CREATE TABLE IF NOT EXISTS laws (
    id INTEGER PRIMARY KEY,
    country_code TEXT,
    player_id INTEGER,
    title TEXT,
    body TEXT,
    status TEXT DEFAULT 'pending',
    income_bonus REAL DEFAULT 0,
    created_at TEXT,
    reviewed_at TEXT,
    reviewed_by INTEGER
)""",
"""CREATE TABLE IF NOT EXISTS referrals (
    invitee_id INTEGER PRIMARY KEY,
    inviter_id INTEGER NOT NULL,
    code TEXT,
    paid INTEGER DEFAULT 0,
    created_at TEXT
)""",
"""CREATE TABLE IF NOT EXISTS nav_state (
    player_id INTEGER PRIMARY KEY,
    stack_json TEXT,
    updated_at TEXT
)""",
]

async def apply_schema(db) -> None:
    for sql in SCHEMA_SQL:
        await db.execute(sql)

# Additional REBIRTH tables
SCHEMA_SQL.extend([
"""CREATE TABLE IF NOT EXISTS alliance_tx (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alliance_id INTEGER NOT NULL,
    country_code TEXT,
    amount REAL,
    kind TEXT,
    created_at TEXT
)""",
"""CREATE TABLE IF NOT EXISTS market_listings (
    id INTEGER PRIMARY KEY,
    seller_code TEXT NOT NULL,
    seller_pid INTEGER NOT NULL,
    item_code TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit_price REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT
)""",
"""CREATE TABLE IF NOT EXISTS market_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER,
    buyer_code TEXT,
    buyer_pid INTEGER,
    quantity REAL,
    total_price REAL,
    created_at TEXT
)""",
"""CREATE TABLE IF NOT EXISTS attack_cooldowns (
    country_code TEXT PRIMARY KEY,
    until_ts TEXT
)""",
"""CREATE TABLE IF NOT EXISTS defense_hits (
    country_code TEXT PRIMARY KEY,
    hits INTEGER NOT NULL DEFAULT 0,
    break_at INTEGER NOT NULL DEFAULT 25
)""",
"""CREATE TABLE IF NOT EXISTS workshop (
    country_code TEXT PRIMARY KEY,
    level INTEGER NOT NULL DEFAULT 1,
    uranium REAL NOT NULL DEFAULT 0,
    tech_level INTEGER NOT NULL DEFAULT 0
)""",
"""CREATE TABLE IF NOT EXISTS workshop_jobs (
    id INTEGER PRIMARY KEY,
    country_code TEXT NOT NULL,
    job_type TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    target REAL NOT NULL DEFAULT 100,
    cost_paid REAL,
    started_at TEXT,
    finishes_at TEXT,
    completed INTEGER NOT NULL DEFAULT 0
)""",
"""CREATE TABLE IF NOT EXISTS referral_codes (
    player_id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    created_at TEXT
)""",
"""CREATE TABLE IF NOT EXISTS force_membership (
    id INTEGER PRIMARY KEY,
    chat_id TEXT NOT NULL,
    title TEXT,
    invite_link TEXT,
    active INTEGER NOT NULL DEFAULT 1
)""",
"""CREATE TABLE IF NOT EXISTS legendary_defs (
    item_code TEXT PRIMARY KEY,
    name_fa TEXT,
    description_fa TEXT,
    price REAL,
    uses_per_unit INTEGER DEFAULT 20,
    effect_type TEXT,
    duration_sec INTEGER DEFAULT 0,
    image_path TEXT,
    active INTEGER DEFAULT 1
)""",
"""CREATE TABLE IF NOT EXISTS player_legendary (
    id INTEGER PRIMARY KEY,
    player_id INTEGER NOT NULL,
    item_code TEXT NOT NULL,
    uses_left INTEGER NOT NULL,
    acquired_at TEXT
)""",
"""CREATE TABLE IF NOT EXISTS legendary_effects (
    id INTEGER PRIMARY KEY,
    item_code TEXT,
    source_player INTEGER,
    target_country TEXT,
    effect_type TEXT,
    expires_at TEXT,
    meta_json TEXT
)""",
"""CREATE INDEX IF NOT EXISTS idx_countries_owner ON countries(owner_player_id)""",
"""CREATE INDEX IF NOT EXISTS idx_inventory_country ON inventory(country_code)""",
"""CREATE INDEX IF NOT EXISTS idx_market_active ON market_listings(active)""",
])
