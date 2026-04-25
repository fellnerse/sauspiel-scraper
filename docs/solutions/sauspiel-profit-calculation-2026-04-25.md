# Sauspiel Profit Calculation Logic

This document captures the institutional knowledge regarding how Sauspiel.de game results are parsed and calculated, following a bug investigation where statistics were significantly skewed.

## 🎴 Domain Knowledge: Roles and Shares

The primary source of truth for game results is the "Wert" (value) field and the "Spielprotokoll" (protocol).

### Roles
- **Spieler:** The primary declarer (Soloist in Solo, or the caller in Sauspiel).
- **Mitspieler:** The partner of the declarer in Sauspiel/Hochzeit. *Critical: Historically misidentified as "Partner" in the codebase.*
- **Gegenspieler:** The opponents (2 in Sauspiel, 3 in Solo).

### Profit Scaling (The "Wert" Field)
The `wert` field in the Sauspiel HTML represents the **total amount the declarer side wins or loses**.

| Game Type | Winners | Losers | Calculation for Declarer Side | Calculation for Opponent Side |
| :--- | :--- | :--- | :--- | :--- |
| **Sauspiel** (2 vs 2) | 2 | 2 | Each gets full `wert` | Each pays full `wert` |
| **Solo / Wenz** (1 vs 3) | 1 | 3 | Soloist gets full `wert` | Each pays `wert / 3` |

*Note: In Solo games, the `wert` is always a multiple of 3 (e.g., P 150, P 300, P 420), reflecting the 3x multiplier the soloist receives/pays.*

## 🐛 Identified Bugs

1.  **The "Mitspieler" Flip:** The code previously only recognized the role "Partner". Since Sauspiel uses "Mitspieler", all partner wins were being recorded as losses (and vice-versa).
2.  **Double/Triple Accounting:**
    *   In Sauspiels, the code was mistakenly dividing the `wert` by 2, under-counting profits.
    *   In Solos, the code was giving opponents the full `wert` instead of 1/3, over-counting losses/wins by 3x.

## 🛠️ Implementation Pattern

When processing games, use the following logic to determine the `net_profit_cents` for the user `me`:

```python
is_solo = any(s in game_type for s in ["solo", "wenz", "geier", "bettel"])
is_me_declarer_side = role in ["Spieler", "Mitspieler", "Partner"]

if is_me_declarer_side:
    is_my_win = is_declarer_win
    net_profit_cents = value if is_my_win else -value
else:
    is_my_win = not is_declarer_win
    if is_solo:
        net_profit_cents = (-value if is_declarer_win else value) // 3
    else:
        net_profit_cents = -value if is_declarer_win else value
```

## 🧪 Verification
Always verify changes against real game IDs.
- **Sauspiel Win (Opponent):** `1558055578` (should result in +`wert`)
- **Wenz Loss (Declarer):** `1559888792` (should result in -`wert`)
