---
name: sustainability-and-energy
description: Sustainability and energy practice — LEED v4.1, WELL v2, IECC + ASHRAE 90.1, passive design, embodied carbon, daylight, IAQ. Invoke when the project pursues a rating system, faces an energy code path decision, needs embodied carbon analysis, or has IAQ/daylight goals.
---

# Sustainability + Energy Skill

The energy + carbon side of commercial architecture. Apply when
choosing a code path, pursuing a rating system, or making
envelope/systems tradeoffs.

---

## Energy codes (the floor)

| Code | Edition (typical) | Scope |
|---|---|---|
| **IECC** | 2021 / 2024 | Residential + commercial; many state-adopted |
| **ASHRAE 90.1** | 2019 / 2022 | Commercial; LEED references |
| **Title 24** | 2022 | California; the toughest |
| **Stretch codes** | varies | NYStretch, NY Local Law 97, etc. — beyond IECC |

Confirm which code + edition the AHJ uses BEFORE designing the envelope.

---

## Compliance paths

### Prescriptive
- Meet each table: R-value, U-factor, SHGC, LPD (Lighting Power
  Density), etc.
- Simple; predictable.
- No tradeoffs allowed.

### Performance / Whole-building
- Model the design + a baseline.
- Design must be ≤ baseline energy cost.
- Allows tradeoffs (more glass + less wall, if the model still works).
- Requires energy modeling software (eQUEST, IES, TRACE, EnergyPlus).

### Total UA
- For envelope-only: sum UA of all envelope assemblies; ≤ baseline UA.
- Middle-ground option in IECC.

### ASHRAE 90.1 Appendix G
- Performance path with a standardized baseline + proposed.
- LEED Energy + Atmosphere EA Optimize Energy Performance is keyed off
  Appendix G.

---

## LEED v4.1 (BD+C: New Construction)

### Certification levels
- Certified: 40-49 points
- Silver: 50-59
- Gold: 60-79
- Platinum: 80+

### High-leverage credits (most points per effort)

**Sustainable Sites**
- SS Credit: Open Space (1 pt)
- SS Credit: Heat Island Reduction (2 pts)
- SS Credit: Light Pollution Reduction (1 pt)

**Water Efficiency**
- WE Prereq: Indoor Water Use Reduction (mandatory; 20% below baseline)
- WE Credit: Indoor Water Use Reduction (1-6 pts; up to 50% reduction)
- WE Credit: Outdoor Water Use Reduction (1-2 pts)

**Energy + Atmosphere** (the big one)
- EA Prereq: Min Energy Performance (ASHRAE 90.1 baseline or better)
- EA Credit: Optimize Energy Performance (1-18 pts — biggest LEED
  point pile)
- EA Credit: Renewable Energy (1-5 pts)
- EA Credit: Enhanced Commissioning (2-6 pts)
- EA Credit: Demand Response (1-2 pts)

**Materials + Resources**
- MR Credit: Building Product Disclosure + Optimization — EPDs (1-2)
- MR Credit: BPDO — Sourcing of Raw Materials (1-2)
- MR Credit: BPDO — Material Ingredients (1-2)
- MR Credit: Construction + Demolition Waste Management (1-2)

**Indoor Environmental Quality**
- IEQ Prereq: Min IAQ Performance (ASHRAE 62.1)
- IEQ Credit: Enhanced IAQ Strategies (1-2)
- IEQ Credit: Low-Emitting Materials (1-3)
- IEQ Credit: Daylight (1-3)
- IEQ Credit: Quality Views (1)
- IEQ Credit: Acoustic Performance (1)

**Innovation**
- IN Credit: Innovation (1-5 pts) — pursue 1-2 always.

---

## WELL v2 (occupant health)

| Concept | Sample credits |
|---|---|
| **Air** | A03 Ventilation Effectiveness; A05 Enhanced Air Quality |
| **Water** | W01 Water Quality Indicators; W02 Drinking Water Quality |
| **Nourishment** | N01 Fruit + Vegetables (food access in cafeteria) |
| **Light** | L02 Visual Lighting Design; L03 Circadian Lighting Design |
| **Movement** | V01 Active Buildings + Communities; V05 Site Planning |
| **Thermal Comfort** | T01 Thermal Performance; T02 Enhanced Thermal Performance |
| **Sound** | S01 Sound Mapping; S02 Maximum Noise Levels |
| **Materials** | X01 Material Restrictions; X05 Enhanced Material Precaution |
| **Mind** | M01 Mental Health Promotion; M07 Restorative Spaces |
| **Community** | C01 Health + Wellness Awareness; C02 Integrative Design |

WELL is performance-based (post-occupancy testing required). Expect to
pay for IWBI registration + certification.

---

## Energy modeling — what + when

### Concept-level (SD)
- Box model in eQUEST or IES.
- Compare 2-3 envelope / system options.
- Output: rough % savings vs baseline.
- Cost: 8-20 engineer-hours.

### Design Development model
- Detailed geometry + systems.
- Run baseline + proposed.
- Output: EUI (Energy Use Intensity), % savings, system tradeoffs.
- Inputs the EA Optimize Energy Performance credit calculation.
- Cost: 40-80 engineer-hours.

### CD-level / submittal
- Validate final design assumptions.
- Used for LEED submittal + energy code documentation.
- Output: official LEED EA EnergyPro tables.

### Post-occupancy M&V
- Compare modeled vs metered.
- 12-month review minimum.
- Tune model + identify operational issues.

---

## Embodied carbon

### Why it matters
- Operational carbon: 28% of US emissions; HVAC + lighting + plug load.
- Embodied carbon: 11% of US emissions; concrete + steel + aluminum
  + insulation.
- Operational carbon trends down (grid decarbonizes); embodied is fixed
  at construction.

### Where to focus
| Material | Typical % of building EC | Lever |
|---|---|---|
| Concrete | 30-50% | SCM (slag, fly ash); reduce strength where allowable |
| Steel | 15-30% | Recycled content; domestic mill |
| Insulation | 5-15% | Mineral wool > XPS for GWP |
| Glazing | 5-15% | Less glazing; thinner IGUs |
| Aluminum | 5-15% | Less anodized aluminum; specify recycled |
| Wood (mass timber) | -50% (carbon sink) | Substitute for steel/concrete where structure allows |

### Tools
- **EC3 (Embodied Carbon in Construction Calculator)** — free; product-
  level data.
- **One Click LCA** — paid; LEED-compatible.
- **Tally** — Revit plug-in.

### Targets
- Office EUI baseline: 500-800 kgCO2e/m². Aim for 300 with good
  decisions; 200 is aggressive.
- LEED v4.1 MR Credit: Building Life-Cycle Impact Reduction (3 pts max).

---

## Envelope strategy by climate zone (ASHRAE 169)

| Zone | Climate | Key strategy |
|---|---|---|
| 1-2 | Hot / very hot | Shade; reduce SHGC; high cooling efficiency |
| 3 | Warm | Balanced; passive cooling; moderate insulation |
| 4 | Mixed | Balanced heating + cooling; air-tight |
| 5-6 | Cool / cold | High insulation; high SHGC south-facing; air-tight |
| 7-8 | Very cold | Maximum insulation; small openings; air-tight; vapor control |

### Envelope rules of thumb (cool / cold zones)
- Roof: R-30 to R-49 continuous.
- Wall: R-20 to R-30 with continuous insulation.
- Below grade: R-10 to R-15.
- Glazing: U ≤ 0.30; SHGC tuned to orientation.
- Air tightness: ≤ 0.40 cfm/sf at 75 Pa (PHIUS target ≤ 0.08).

---

## Passive design strategies

### Solar control
- **South-facing**: horizontal shading (overhang); higher SHGC for
  winter gain.
- **East / west**: vertical fins or operable shades for low-angle sun.
- **North**: daylight without glare; less glazing for energy.

### Thermal mass
- Concrete or masonry interior surfaces store + release heat.
- Best in cool climates with diurnal temp swing (mountain west).

### Natural ventilation
- Cross-ventilation: openings on opposite sides; min 4-6 ACH.
- Stack ventilation: tall central atrium; openings high + low.
- Mixed-mode: HVAC + operable windows; users adjust per comfort.

### Daylight
- 15-20% glazing ratio gives sufficient daylight without overheating.
- Sidelighting: depth penetrates ~1.5× window-head height.
- Toplighting (skylights, clerestories): more even; 2-3% roof area.
- Light shelves: bounce light deeper into space; shade direct sun.

---

## IAQ practice

### Ventilation
- ASHRAE 62.1 minimums (in mep-mechanical-hvac skill).
- LEED IEQ Enhanced Strategies: 30% above 62.1.

### Filtration
- MERV 13 for LEED IEQ credit.
- MERV 16+ for healthcare / lab.
- HEPA for clean rooms / isolation.

### Materials (Low-VOC)
- CDPH 01350 (California 01350) standard.
- Paints + sealants: < 50 g/L VOC.
- Adhesives: SCAQMD Rule 1168.
- Flooring: CRI Green Label Plus or FloorScore.
- Composite wood: ULEF or NAF.

### Construction IAQ
- During construction: protect HVAC equipment from dust.
- After construction: flush-out (14,000 cf OA per sf, 60°F+ supply) or
  IAQ testing.

---

## When to invoke

- Choosing energy code compliance path
- Setting LEED / WELL targets
- Envelope vs HVAC tradeoff decisions
- Embodied carbon analysis at structural option study
- Daylight modeling + glare studies
- Specifying low-VOC materials
- Post-occupancy energy performance review
