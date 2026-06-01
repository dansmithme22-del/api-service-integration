---
name: mep-mechanical-hvac
description: 15-year HVAC mechanical perspective — equipment selection, ductwork, air balancing, controls, energy code. Invoke when the project involves heating/cooling/ventilation design, mechanical room sizing, plenum coordination, or interpreting M-series drawings.
---

# Mechanical / HVAC Skill

What an architect needs to know to coordinate with mechanical, and
what to flag in a mech engineer's drawings. Apply when sizing
mechanical rooms, coordinating ductwork, or interpreting M-series
drawings.

---

## HVAC system types (when to use which)

| System | Typical size | Strengths | Weaknesses |
|---|---|---|---|
| **Split system / RTU + ductwork** | < 50,000 sf | Cheapest; common | Less controllable; less efficient |
| **VRF / VRV (variable refrigerant flow)** | 10K-200K sf | Quiet; flexible; zoning | High capex; refrigerant compliance |
| **Chilled water + AHU** | > 30K sf | Best efficiency at scale; central plant | Footprint; piping cost |
| **Hydronic radiant** | Any | Comfort; quiet; energy | Slow response; flooring constraints |
| **Geothermal heat pump** | Any with land | High efficiency; long life | High capex; well field |

90% of typical commercial under 100K sf is RTU + VAV or VRF. Above
100K sf, chilled water becomes economical.

---

## Architect-side coordination essentials

### Mechanical room sizing
- Boiler / chiller room: 1-3% of building area as a rough check.
- Required clearances: code-driven; check IMC + manufacturer.
- Service path: equipment must be removable / replaceable (often a
  knock-out wall is the answer).
- Floor drain + housekeeping pad: required at all wet equipment.

### Roof equipment (RTUs)
- Weight: 5-15 lb per CFM typical; structure must carry.
- Curbs: insulated, code-compliant; coordinate with roofer.
- Roof access: ladder + walking surface; required by OSHA for service.
- Clearances: 3' minimum perimeter; 5' between units typical.

### Mechanical shafts
- Vertical air shafts and pipe shafts run floor-to-floor.
- Size: 4'×6' typical for a mid-rise air shaft; 2'×4' for pipe.
- Fire-rated walls; rated dampers at floor penetrations.

### Plenum vs ducted ceiling
- **Plenum return**: ceiling cavity is the return air path; cheaper;
  requires plenum-rated wiring + insulation.
- **Ducted return**: separate return ducts back to AHU; more flexible;
  cleaner.

### Floor-to-floor heights
- Office with VAV: 13-14' typical floor-to-floor (10' clear ceiling +
  3' plenum + structure).
- Office with radiant: 11-12' floor-to-floor (no plenum needed).
- Industrial / warehouse: clear-height-driven; structure picks up roof
  drainage.

---

## Loads (rule of thumb only)

| Building type | Cooling load | Heating load |
|---|---|---|
| Office (open plan) | 300-500 sf/ton | 25-35 BTU/sf |
| Office (private) | 250-350 sf/ton | 25-35 BTU/sf |
| Retail | 200-300 sf/ton | 30-40 BTU/sf |
| Restaurant | 100-200 sf/ton (high) | 40-60 BTU/sf |
| Warehouse (unconditioned) | n/a | 15-25 BTU/sf |
| Lab / clean room | 100 sf/ton or less | 50+ BTU/sf |
| Data center | < 100 sf/ton | typically 0 (rejected from servers) |

These are NOT design loads. The mech engineer runs a Manual N / TRACE
load. Use these only for early square-footage sanity-checks.

---

## Ductwork

### Sizing
- Velocity targets:
  - Main ducts: 1500-2000 fpm
  - Branches: 800-1500 fpm
  - Diffusers: 400-700 fpm at neck

- Aspect ratio: ≤ 4:1 (1:1 is best; 6:1 is bad).

### Materials
- **Galvanized sheet metal**: standard.
- **Spiral round**: lower pressure drop; nicer look in exposed
  applications; more expensive.
- **Internally-lined**: for sound attenuation near rooftop equipment.
- **Flex duct**: for last 5-10' to diffusers only; never as a main run.

### Dampers
- Fire dampers: at rated wall penetrations (UL-listed).
- Smoke dampers: at smoke barrier penetrations.
- Combination fire/smoke dampers: code-driven; check IBC + IMC.
- Backdraft / VAV dampers: per air-balancing.

---

## Ventilation rates (ASHRAE 62.1 Table 6-1)

| Space | OA cfm/person | OA cfm/sf |
|---|---|---|
| Office | 5 | 0.06 |
| Conference room | 5 | 0.06 |
| Classroom | 10 | 0.12 |
| Lecture hall | 7.5 | 0.06 |
| Lobby | 5 | 0.06 |
| Cafeteria | 7.5 | 0.18 |
| Kitchen (commercial) | 7.5 | 0.12 |
| Locker / toilet | required exhaust |
| Storage | 0 | 0.12 |

These are the per-person + per-area minimums. Most spaces are
people-dominated; restaurants + warehouses are area-dominated.

---

## Exhaust requirements (selected)

| Space | Exhaust rate |
|---|---|
| Toilet rooms | 50 cfm per WC fixture (continuous) |
| Janitor closets | 50-100 cfm continuous |
| Kitchen hood | per CFM/linear foot of hood — UL listing |
| Garage / repair | 1.5 cfm/sf (or per IMC) |
| Spray paint booth | per NFPA + manufacturer |
| Battery rooms | dilution rate for hydrogen |
| Smoking lounges | 60 cfm/person |

---

## Controls (BAS)

### Sequence-of-operations matters
- Programmed in the controls subcontractor's PLC / DDC.
- Written into specs (Division 23 §0900); MEP engineer authors.
- Commissioning agent verifies after install.

### Common sequences
- **VAV cooling-only**: terminal damper modulates to maintain setpoint;
  reheat off; air handler delivers cold deck.
- **VAV cooling + reheat**: terminal modulates to minimum, then reheat
  comes on. Energy waste if minimum is set too high.
- **Demand-controlled ventilation (DCV)**: CO2 sensors modulate OA
  intake based on occupancy.

### Setpoints (rule of thumb)
- Cooling: 75°F dry-bulb summer, 50-60% RH.
- Heating: 70°F dry-bulb winter, no RH control typical.
- Setback: 5-10°F off-hours.

---

## Code paths

### Energy code (IECC + ASHRAE 90.1)
- **Prescriptive path**: meet R-value, U-factor, lighting power density
  tables. Strict but predictable.
- **Performance path**: model whole-building performance ≤ baseline.
  Trades envelope for HVAC etc.; required if any prescriptive item
  fails.

### Refrigerant codes
- Phase-down of high-GWP refrigerants (R-410A, R-407C) under AIM Act.
- New systems trend to R-32, R-454B, R-1234yf (low-GWP).
- Verify locally-allowed refrigerants — UL2856 charge limits in some
  jurisdictions.

### Air quality / IAQ
- ASHRAE 62.1 ventilation rates.
- MERV 13 filtration for LEED IEQ credit.
- Construction IAQ management plan (LEED).

---

## When to invoke

- Sizing a mechanical room
- Coordinating ductwork with plenum / structure
- Reviewing M-series drawings
- Picking an HVAC system type at SD
- Specifying ventilation rates / IAQ targets
- Coordinating roof equipment with structure + roofing
- Reading owner's process loads for capacity sizing
