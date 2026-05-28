---
name: ibc-code-analysis
description: International Building Code (2021) — use group classifications, occupant load calculation, egress minimums, fire-rated assemblies, accessibility. Invoke ONLY when the task is permit-grade — code analysis, occupancy classification, egress diagrams, fire-rating callouts, building-code review. This is permit-mode logic; for schematic work or design exploration, do not invoke.
---

# IBC Code Analysis Skill

The International Building Code is the legal framework for what's permittable. Invoke this skill only at permit-grade work — code analysis sheets, egress diagrams, fire-rating callouts, occupancy classifications. It is **not** the right tool for schematic design or programming.

Authoritative reference: `config/ibc_use_groups.json`. Source: 2021 IBC, IBC Table 1004.5 (occupancy loads), IBC Table 1017.2 (travel distance), IBC Chapter 7 (fire-resistance ratings), IBC Chapter 10 (means of egress).

---

## Permit-mode gate

This skill produces results that go in front of an Authority Having Jurisdiction (AHJ). Two non-negotiable rules:

1. **Always verify against the official IBC and any local amendments before submitting**. Numbers in this skill are the unmodified IBC base values.
2. Output should call out IBC section references inline so the reviewer can audit.

---

## Use group classifications (IBC §302)

| Code | Name | NSF / occupant | Examples |
|---|---|---|---|
| **A-1** | Assembly — fixed seating | 7 | Theaters, concert halls |
| **A-2** | Assembly — food/drink | 15 | Restaurants, bars |
| **A-3** | Assembly — worship/library/museum | 15 | Churches, libraries, community halls |
| **A-4** | Assembly — indoor sports | 15 | Arenas, indoor pools |
| **A-5** | Assembly — outdoor | 15 | Stadiums, grandstands |
| **B** | Business | **150** | **Offices, vet clinics, banks, outpatient** |
| **E** | Educational (K-12, day-care ≤ 2.5 yr) | 20 | Schools |
| **F-1** | Factory — moderate hazard | 100 | Manufacturing |
| **F-2** | Factory — low hazard | 100 | Beverage production |
| **H-1** | High hazard — detonation | permit-review | Explosives |
| **I-1** | Institutional — supervised personal care | 200 | Assisted living |
| **I-2** | Institutional — medical care | 240 | Hospitals, surgery w/ overnight |
| **I-3** | Institutional — restrained | — | Jails, prisons |
| **I-4** | Institutional — day-care (adult or child > 2.5yr) | 35 | Day-care centers |
| **M** | Mercantile | 60 (sales) / 300 (storage) | Retail |
| **R-1** | Residential — transient | 200 | Hotels |
| **R-2** | Residential — multi-family | 200 | Apartments, dorms |
| **R-3** | Residential — 1-2 family | 200 | Houses, townhomes |
| **S-1** | Storage — moderate hazard | 300 | Warehouses (combustible) |
| **S-2** | Storage — low hazard | 200 (parking) / 300 (storage) | Parking, non-combustible warehouse |
| **U** | Utility / Miscellaneous | 300 | Sheds, towers, detached garages |

### Picking a use group

Default mappings for common project types:

- **Veterinary clinic** → **B** (Business). Even though there are animals, the IBC classifies vet practices as Business unless overnight medical care is provided (then I-2).
- **Office** → **B**.
- **Childcare with kids > 2.5 years** → **E** (Educational).
- **Childcare with kids ≤ 2.5 years** → **I-4** (Institutional — day-care).
- **Retail** → **M** (Mercantile).
- **Community center** → typically **A-3** (Assembly — worship/library/museum).

---

## Occupant load calculation

```
occupant_load = floor_area_NSF / nsf_per_occupant
```

Where `nsf_per_occupant` is from the table above.

Example: A 1,500 NSF office (B occupancy) = 1500 / 150 = **10 occupants**.

If occupant load ≥ 50, plan requires **two means of egress** (IBC §1006.2.1). Many other code requirements scale at the 50-occupant threshold.

If occupant load ≥ 1000, additional measures kick in (sprinklers, emergency power, panic hardware).

---

## Egress minimums (IBC Chapter 10)

| Dimension | Minimum | IBC reference |
|---|---|---|
| Two exits required threshold | occupant load ≥ 50 | §1006.2.1 |
| Corridor width (< 50 occupants) | 36" | §1020.2 |
| Corridor width (≥ 50 occupants) | 44" | §1020.2 |
| Door opening width | 32" clear (any single door) | §1010.1.1 |
| Aisle width (< 50 occupants) | 36" | §1018.3 |
| Aisle width (≥ 50 occupants) | 44" | §1018.3 |
| Ceiling height (egress path) | 88" minimum | §1003.2 |
| Maximum travel distance — Group B sprinklered | 300 ft | Table 1017.2 |
| Maximum travel distance — Group B non-sprinklered | 200 ft | Table 1017.2 |
| Maximum travel distance — Group A,E,I,M,R,S sprinklered | 250 ft | Table 1017.2 |

### Travel-distance calculation

Travel distance is measured along the **path an occupant would actually walk**, not straight-line, from any point in the building to the nearest exit. Common-path-of-egress-travel (CPET) limits are also separate (§1006.2.1).

---

## Fire-resistance ratings (IBC Chapter 7)

| Rating | Typical assembly | Common application |
|---|---|---|
| **1HR** | 5/8" Type X GWB each side of 2x4/3-5/8" stud | Corridor walls in Group B; demising walls |
| **2HR** | 2 layers 5/8" Type X each side, or 8" CMU | Exit enclosures; shaft walls |
| **3HR** | 8" CMU + 1-hour rated finish | Area separation walls |
| **4HR** | Special concrete or CMU assemblies | Hi-rise stair shafts |
| **Smoke partition** | Sealed to deck, 20-min door, no fire rating | Group I-2 corridors |

### When you need fire ratings

- **Corridor walls** in Group B/I → 1HR.
- **Exit enclosures** (stair shafts) → 2HR minimum (more for high-rise).
- **Shaft walls** (elevator, mechanical) → 2HR.
- **Demising walls** between tenant spaces → 1HR (varies by occupancy).
- **Area separation walls** → 2HR or 3HR depending on Type of Construction.

Always verify against IBC Table 601 (Type of Construction) for the specific project.

---

## Accessibility (ANSI A117.1 / 2010 ADA)

| Element | Requirement |
|---|---|
| Clear door opening | 32" minimum |
| Pull-side door clearance | 18" minimum |
| Push-side door clearance | 12" with closer + latch |
| Wheelchair turning radius | 60" minimum (or 60"×60" T-turn) |
| Toilet stall (single-user) | 60" wide × 56" deep minimum |
| Grab bar mounting height | 33-36" |
| Toilet centerline from wall | 18" from sidewall |
| Reach range (forward) | 15-48" |
| Reach range (side) | 15-48" with knee clearance |
| Ramp slope | ≤ 1:12 (8.33%) |
| Ramp landing | 60" minimum at top and bottom |

---

## Output format for code-analysis sheets

A code-analysis sheet typically includes:

1. **Project info box** — name, address, designer of record.
2. **Use group classification** — primary + accessory.
3. **Construction type** (Type I, II, III, IV, V; A or B subdivision).
4. **Occupant load table** — by room, summed.
5. **Means-of-egress diagram** — every required exit, dashed paths with travel distances, dead-end markers.
6. **Fire-rated assemblies** — wall types with ratings, labeled.
7. **Plumbing fixture count** — per IPC Chapter 4 (separate code).
8. **Code references** — citations for every claim.

---

## When NOT to invoke

- Schematic design / programming → not yet permit-grade
- Conceptual studies → use schematic skills
- Test fits / space planning → use space-planning skills
- Renderings → use rendering skills

Invoke `ibc-code-analysis` only when the deliverable is in front of a code official.

---

## Provenance

Numbers in this skill are 2021 IBC base values without local amendments. Always verify against:

1. The current IBC at icc-safe.org
2. State amendments
3. Local jurisdiction amendments
4. Project-specific code analysis approved by AHJ
