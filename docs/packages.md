# First-party package catalog

Every title release includes the nine packages below, disabled by default.
The title's [mods guide](https://github.com/ReRevvedRecomp/rerevved/blob/main/docs/mods.md) covers enabling them. Each
package has a manifest and a single Lua declaration under `src/<id>/`.

## Bundled packages

| Package | ID | Declared gameplay change |
|---|---|---|
| Cataphracts Defense | `cataphracts-defense` | Roman Cataphracts gain +1 base Defense. |
| Chinese Library Gold | `chinese-library-gold` | Chinese-owned Libraries add +1 to final city Gold, preserving native Science. |
| Founding Militia | `founding-militia` | Each newly founded human or AI city gets an extra Militia with Loyalty. |
| Hills Production | `hills-production` | Hills gain +1 base Production for every player. Requires ReRevved 0.5.0 or newer. |
| Hoplite Loyalty | `hoplite-loyalty` | Newly created Greek Hoplites receive Loyalty; the cost rule uses -30 percentage points. |
| Jaguar Woodsman | `jaguar-woodsman` | Aztec Jaguar Warriors gain 50 percentage points of Attack and Defense when the defender's battle tile is Forest. |
| Keshik Movement | `keshik-movement` | Mongolian Keshiks gain +1 ordinary effective Movement. |
| Mongol Horseback | `mongol-horseback` | The Mongolian Ancient ability becomes Knowledge of Horseback Riding. |
| Stonehenge Religion | `stonehenge-religion` | Newly completing Stonehenge grants Religion if the owner does not already have it, without replacing native Culture. |

## Editable values

Edit the local values in `src/<id>/main.lua`, not generated output, then
[build the package](development.md#build-packages) and install it as a
[custom copy](https://github.com/ReRevvedRecomp/rerevved/blob/main/docs/mods.md#install-or-customize-a-package).

| Package | Local value or declaration | Text maintenance |
|---|---|---|
| Cataphracts Defense | `defense_bonus = 1` | Nation Select text uses the same value. |
| Chinese Library Gold | `building_yield` with `gold_addition = 1` | No Nation Select text rule. |
| Hills Production | `production_bonus = 1` | No Nation Select text rule. |
| Hoplite Loyalty | `production_delta = -30` | The `10 Production` text is authored separately; update and verify it after a cost edit. |
| Jaguar Woodsman | `forest_bonus = 50` | Both combat deltas and Nation Select text use this value. |
| Keshik Movement | `movement_bonus = 1` | Nation Select text uses the same value. |
| Mongol Horseback | `era_technology_ability` with `technology = 'horseback_riding'` | Keep the ability selector and its text consistent. |
| Stonehenge Religion | `wonder_completion_technology` with `wonder = 'stonehenge'`, `technology = 'religion'` | No Nation Select text rule. |
| Founding Militia | `city_founding_unit` with `unit = 'militia'`, `upgrades = {'loyalty'}` | No Nation Select text rule. |

The title's [Lua contract](https://github.com/ReRevvedRecomp/rerevved/blob/main/docs/modding-api.md#lua-rules-contract-1)
defines numeric ranges, IDs, selectors, and rejected combinations. Package
assembly checks source and metadata, not the values returned by executing Lua.
Do not treat every syntactically valid number as a supported gameplay value.

## Save-state and testing notes

- Founding Militia grants the unit only when a city is founded, not when one is
  captured or a save is loaded.

- Hoplite's default cost is 10 ordinary undiscounted Production. The title
  applies the percentage after native discounts and before its army factor;
  the authored text is not a calculation for every production context.
- Jaguar's Forest test uses the defender's battle tile for both Attack and
  Defense, not simply the attacker's starting terrain.
- Keshik's ordinary effective-movement rule does not establish coverage of
  special movement paths, movement budgets, command costs, AI, or presentation.
- Mongol Horseback's granted technology remains ordinary saved state after
  the package is disabled. Test the starting grant in a fresh game.
- Stonehenge does not grant Religion on load, activation, or city capture.
  Already acquired Religion is not removed when the package is disabled.
- Chinese Library Gold applies to existing Libraries as well as new ones.
  Previously credited Gold is not undone by disabling the package. Signed
  amounts and overflow handling follow the title's
  [effect contracts](https://github.com/ReRevvedRecomp/rerevved/blob/main/docs/building-wonder-effects.md#v2-adjustable-amounts).

Keep backups when testing. For each change, distinguish what the source
requests, what F2 accepts, and what was observed in the game.
