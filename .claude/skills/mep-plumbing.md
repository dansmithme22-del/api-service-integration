---
name: mep-plumbing
description: 15-year plumbing perspective — fixture units, pipe sizing, hot water sizing, IPC code, drainage slope, vent stack sizing, backflow prevention. Invoke when the project involves plumbing fixture layouts, sizing, or coordinating with the P-series drawings.
---

# Plumbing Skill

What an architect needs to know to coordinate plumbing and read P-series
drawings. Apply when fixture counts, riser layouts, hot water, or
backflow show up.

---

## Fixture count (IPC Table 422.1 / IBC Table 2902.1)

Required fixtures per occupancy:

| Use group | Water closets | Lavatories | Drinking |
|---|---|---|---|
| **Office (B)** | 1 per 25 occ (first 50) | 1 per 40 occ | 1 per 100 occ |
| **Restaurant (A-2)** | 1 per 75 (men), 1 per 75 (women) | 1 per 200 | 1 per 400 |
| **Retail (M)** | 1 per 500 (men), 1 per 500 (women) | 1 per 750 | 1 per 1000 |
| **Educational (E)** | 1 per 50 (children) | 1 per 50 | 1 per 100 |
| **Assembly (A-3)** | 1 per 75 (men), 1 per 75 (women) | 1 per 200 | 1 per 500 |
| **Warehouse (S)** | 1 per 100 | 1 per 100 | 1 per 1000 |

Always check the current IPC + local amendments. Counts vary by edition.

Some jurisdictions require all-gender fixtures + accessible accommodations.

---

## Fixture units (DFU + WSFU)

Plumbing pipe sizing uses **Drainage Fixture Units (DFU)** for sanitary
and **Water Supply Fixture Units (WSFU)** for supply.

### Common fixture DFUs (IPC Table 709.1)

| Fixture | DFU | Trap size |
|---|---|---|
| Water closet (flushometer) | 6 | 4" |
| Water closet (gravity tank) | 4 | 4" |
| Lavatory | 1 | 1¼" |
| Bathtub | 2 | 1½" |
| Shower | 2 | 2" |
| Kitchen sink | 2 | 1½" |
| Floor drain | 2 | 2" |
| Service sink | 3 | 2" |
| Drinking fountain | 0.5 | 1¼" |

### Common fixture WSFUs (IPC Table 604.3 / E103)

| Fixture | WSFU (private) | WSFU (public) |
|---|---|---|
| Water closet (flushometer) | 6 | 10 |
| Water closet (tank) | 2.2 | 5 |
| Lavatory | 1 | 1.5 |
| Bathtub / shower | 4 | — |
| Kitchen sink | 1.5 | 3 |
| Service sink | — | 4 |
| Wall hydrant | — | 4 |

The engineer sums fixture units and looks up pipe size from IPC tables.
Architect needs to know roughly: 50 WSFU = 1¼" supply; 200 WSFU = 2".

---

## Drainage system

### Slope (IPC §704)
- 2" pipe and smaller: ¼" per foot (2%).
- 3" pipe: ⅛" per foot (1%).
- 4" pipe and larger: ⅛" per foot (1%).

Translates to plenum depth: a 100' horizontal run at ¼"/ft drops 25"
(2 ft). The plumbing engineer's lowest fixture sets the plenum.

### Cleanouts (IPC §708)
- At base of every soil/waste stack.
- At every change in direction > 45° in horizontal runs.
- Every 100' in horizontal runs.
- Accessible (not buried under cabinets).

### Pipe materials
- **Underground**: PVC (DWV) or cast iron.
- **Above grade vent / waste**: cast iron (preferred for sound + fire),
  PVC, or galvanized.
- **Hub-and-spigot CI**: traditional; quieter; more expensive.
- **No-hub CI**: faster install; gasket-and-band couplings.

---

## Vent system

Every fixture needs a vent to:
1. Prevent trap siphonage (loss of water seal → sewer gas in space).
2. Equalize drain pressure.
3. Discharge sewer gas above roof.

### Vent stack sizing (IPC §906)
- Sized off DFUs and developed length.
- Minimum 1¼" anywhere.
- Stack vents through roof: minimum 4" through roof (frost protection
  in cold climates).

### Vent types
- **Stack vent**: vertical pipe above the highest fixture branch.
- **Vent stack**: separate riser tied to soil/waste below all fixtures.
- **Loop vent**: islanded fixtures (kitchen island sink).
- **Air admittance valve (AAV)**: code-allowed alternative; check local.

---

## Hot water

### Sizing (rule of thumb)
- Office: 0.5 gph/person.
- Restaurant: 2.5-5 gph/seat.
- Hotel: 30-50 gph/room.
- Lab: 5-10 gph/sink.

The engineer runs IAPMO / ASPE method for actual sizing.

### Hot water systems
- **Central tank**: gas or electric; common for low-rise / hospitality.
- **Tankless / instantaneous**: gas; saves space; better for low
  simultaneous demand.
- **Heat pump water heater**: efficient; condenser dumps cool air
  (consider where).
- **Solar pre-heat**: rooftop collectors + storage tank; rebates in
  some markets.

### Recirculation
- Required if longest run > 50' from heater to fixture (per code).
- Pump + return loop maintains hot water at fixtures.
- Energy penalty (continuous loop) vs convenience.

---

## Backflow prevention

Required at any potable-water connection that could be contaminated.

### Devices (lowest to highest hazard)
- **Air gap**: visible separation; absolute prevention; sink fill.
- **AVB / SVB**: atmospheric / pressure vacuum breaker; hose bibs.
- **DCVA**: double-check valve assembly; low-hazard cross-connections.
- **RPZ**: reduced-pressure backflow preventer; high-hazard
  cross-connections (boiler feed, cooling tower, irrigation, fire
  suppression).

### Testing
- RPZ + DCVA: annual testing by certified tester required by water
  utility.
- Locate accessibly (door above), with drain (RPZ dumps water on
  failure).

---

## Drains + traps

### Floor drains
- **Cast iron with brass strainer**: standard mechanical room.
- **Floor sink**: indirect drains (HVAC condensate, kitchen
  equipment).
- **Funnel drain / hub drain**: open visible receipt.

### Trap primers
- Floor drains need traps; traps dry out if unused.
- **Trap primer valve**: hooks to lavatory supply; periodic re-fill.
- **Electronic timer primer**: time-based fill.

### Grease traps / interceptors
- Required at any kitchen with cooking grease.
- Sized per peak flow + retention time (DEP requirements).
- Located outside building or in dedicated room.

---

## Architect-side coordination

### Plumbing wall thickness
- Standard interior partition: 4-6" wide. NOT enough for vent + supply
  + waste stack at toilet wall.
- **Wet wall**: 8-10" thick to accept 4" waste stack + 2" vent +
  hot/cold supply.
- Back-to-back toilets share the wet wall.

### Floor penetrations
- Every floor penetration of a soil/waste pipe needs a fire collar
  if the floor is rated.
- Per code: use UL-listed firestopping per the wall/floor assembly.

### Pipe routing
- Soil + waste want gravity → slope → outlet to building drain.
- Don't run waste over occupied space (leaks above sensitive uses).
- Coordinate with structure (avoid coring beams).

### Backflow + meter pit
- Water service entry: backflow assembly + master meter.
- Locate in dedicated room with floor drain.
- Door access for testing.

---

## When to invoke

- Counting fixtures for a use group
- Sizing wet walls + chases
- Hot water system selection + sizing
- Coordinating P-series drawings with arch/struct
- Reading owner's process water requirements
- Specifying backflow prevention
- Designing washdown / kitchen / lab plumbing
