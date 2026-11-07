# WORLD WAR REBIRTH — Feature Checklist

## Working (tested or implemented end-to-end)
- [x] Independent SQLite DB + schema bootstrap
- [x] Country/group seed (seed_ng.json)
- [x] UN ownership for OWNER_ID
- [x] /start private vs group
- [x] Compact categorized main menu + Nav home/back
- [x] Country claim (atomic)
- [x] Official shop catalog + purchase + inventory
- [x] Daily income (auto + owner force)
- [x] Donations submit/review/stats
- [x] Alliances: create/join/leave/dissolve/deposit
- [x] Peace treaties propose/list/break
- [x] Combat attack with inventory consumption, defense coverage, loot, HP, cooldown
- [x] P2P market list/create/buy/cancel
- [x] Legendary catalog buy + inventory (player-bound)
- [x] Workshop research jobs (abstract)
- [x] Referral codes + rewards
- [x] Forced membership config (owner)
- [x] Owner panel: war toggle, daily, players, world, donations, membership
- [x] Rankings + activity news feed
- [x] Connection/handler logging (no token)

## Partial / needs live Bale verification
- [ ] Forced membership live API check (requires bot admin in channels)
- [ ] Legendary timed effect application in combat paths
- [ ] Alliance capacity upgrades UI
- [ ] Full owner economy tools (give/take money, set HP, ban)
- [ ] Nuclear fiction item purchase path parity with legacy
- [ ] Media cache for legendary photos
- [ ] Multi-page player search in owner panel

## Tests
- test_rebirth_core: claim, buy, empty schema
- test_rebirth_systems: alliance, market, combat, legendary, referral
