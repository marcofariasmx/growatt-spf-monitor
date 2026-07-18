# Battery Charge Tuning for LiFePO4 Longevity

How to apply an "EV-style" charge limit (the equivalent of "charge to 80%")
on a Growatt SPF inverter with LiFePO4 batteries, and why it works
differently than in a car.

Researched 2026-07 against a Growatt SPF 3000TL LVM-48P paired with
Growatt ARK 2.5L-A1 (LiFePO4, 16S, 51.2V nominal) modules. Most of it
generalizes to any 48V (16S) LiFePO4 pack on an SPF inverter.

## The short version

There is **no SOC-percentage charge ceiling** on these inverters. EVs
limit charging by state-of-charge ("stop at 80%"); the SPF only exposes
**voltage setpoints**. But LiFePO4's charge curve makes a voltage cap a
perfectly good proxy: the last few percent of charge live in a steep
voltage rise at the top of the curve, so lowering the charge voltage
ceiling cuts off exactly that most-stressful top slice.

Lowering `BulkChargeVolt`/`FloatChargeVolt` from the factory 56.8V to
~55.2/54.4V trades roughly 2-5% of usable capacity for a substantially
longer cell life, and is the standard practice in the DIY solar
community for stationary LiFePO4 packs.

## Why 56.8V is the stressful default

- 56.8V across 16 cells = **3.55V/cell** -- the very top of the ARK's
  documented operating range (47.2-56.8V). It's a "get it full, fast"
  setting.
- LiFePO4 cell wear concentrates at high state of charge and high cell
  voltage. Community rule of thumb from DIY Solar Forum threads:
  anything above ~3.425-3.45V/cell buys almost no extra capacity but
  adds real stress -- the charge curve is so flat that 3.45V/cell
  already reaches ~98-99% of true capacity.
- Floating *continuously* at 3.55V/cell is the worst of it: the pack
  sits pinned at maximum voltage whenever the sun is out.

## Community-consensus voltage table (16S LiFePO4)

| Per cell | Pack (16S) | Approx SOC reached | Notes |
|---|---|---|---|
| 3.65V | 58.4V | 100% (absolute max) | Cell spec limit; never use as a daily setpoint |
| 3.55V | 56.8V | ~100% | ARK factory ceiling; fine occasionally, stressful daily |
| 3.50V | 56.0V | ~99-100% | Common "full charge" setting |
| 3.45V | 55.2V | ~98-99% | Popular bulk/absorb for longevity; also lets BMS balance |
| 3.40V | 54.4V | ~95-97% | Common float; gentle |
| 3.375V | 54.0V | ~90% | Conservative float |
| 3.35V | 53.6V | ~85-90% | Very conservative float |

(The SOC column is approximate and settles lower after surface charge
dissipates -- LiFePO4 resting voltage is famously flat between 20-90%.)

Common recipes seen across DIY Solar Forum:

- **Balanced (recommended here):** Bulk/absorb 55.2V, float 54.4V.
  Still reaches ~98% so the BMS gets regular balancing opportunities,
  while eliminating time spent at 3.55V/cell.
- **Longevity-first:** Bulk 54.4V, float 53.6V. Tops out around ~95%;
  give the pack an occasional full charge to let the BMS balance cells.
- **Factory:** Bulk/float 56.8V. Maximum capacity per day, most wear.

## Where these live on the SPF

Two equivalent surfaces -- LCD programs on the unit, or Modbus holding
registers over the same RS485/USB link this repo already uses:

| Setting | LCD program* | Holding register | Unit | Range |
|---|---|---|---|---|
| Max charge current (total) | 02 | 34 | 1A | model-dependent |
| Bulk/absorption (CV) voltage | 19 | 35 | 0.1V | 500-640 |
| Float voltage | 20 | 36 | 0.1V | 500-560 |
| Battery type | 05 | 39 | enum | 0 AGM / 1 FLD / 2 USE / 3 Li / 4 USE2 |

\* Program numbers vary slightly between SPF sub-models; check your
manual. Register numbers are from the official OffGrid Modbus RTU
protocol (V0.11 in `docs/SPF_PROTOCOL_OFFICIAL.md`; the V0.14 revision
adds the 5-value battery-type enum and wider ranges).

Notes for Modbus writes (function 0x06):

- Registers 35/36 are plain 0.1V-scaled writes (55.2V → 552).
- Register 39 (battery type) is documented "can be set at standby state
  only" -- don't change it live. Voltage registers 34-38 carry no such
  annotation and are routinely changed at runtime by the LCD anyway.
- Only one process can hold the serial port: stop `growatt-gateway`
  before a write session, or add the write path to the gateway itself
  (see `docs/GATEWAY.md`).
- Read the value back after writing, and confirm on the LCD if you're
  on-site. Some firmware quietly clamps out-of-range values.

## BMS communication (vs. voltage-controlled mode)

The ARK LV series speaks **CAN** using Growatt's own protocol (LCD:
battery type "Li", then protocol **L51**; Pylontech-compatible packs use
L52). With BMS comms active, the *battery* dictates charge voltage and
current (`BMS_ConstantVolt`, `BMS_MaxCurr` -- input registers 90-101
populate), the SOC display becomes authoritative, and several LCD
programs switch from volts to percent.

Without comms (battery type "Li"/USE but no cable/protocol match), the
inverter runs **voltage-controlled**: it applies its own
`BulkChargeVolt`/`FloatChargeVolt` and estimates SOC from voltage. You
can tell which mode you're in by reading input registers 90-101: all
zeros means no BMS link.

Two implications:

- In voltage-controlled mode, the tuning above is fully in your hands --
  the inverter will do exactly what registers 35/36 say.
- With BMS comms active, the BMS's requested CV voltage generally wins;
  tuning registers 35/36 may have little effect. (The ARK BMS still
  protects the pack either way -- comms or not -- by disconnecting on
  cell over/under-voltage; that's a last-resort protection, not a
  charge-management strategy.)

Note the charge/discharge current limits stack with parallel modules
(ARK 2.5L-A1: 25A per module -- 2 modules = 50A, up to 100A at 4+).
Keep `MaxChargeCurr` at or below the pack's aggregate limit.

## Sources

- Growatt ARK LV datasheet (2.5L-A1: LiFePO4 16S, 51.2V nominal,
  47.2-56.8V operating, 25A/module, CAN BMS, 6000+ cycles):
  [pvo-int.com datasheet PDF](https://www.pvo-int.com/wp-content/uploads/2022/03/Datasheet-Growatt-ARK-LV-2.5L-25.6L-Battery-System-EU%EF%BC%88V1.0.pdf)
- Official OffGrid SPF Modbus protocol V0.14 (battery-type enum, register
  ranges): [amosplanet.org PDF](https://www.amosplanet.org/wp-content/uploads/2022/05/OffGrid-Modbus-RS485RS232-RTU-Protocol-V0.14-20210420.pdf)
- Growatt lithium commissioning guide (Li + L51/L52 protocol selection):
  [amosplanet.org](https://www.amosplanet.org/how-to-commission-the-communication-between-lithium-ion-battery-and-spf-3500-5000es/)
- DIY Solar Forum voltage-setting threads:
  [charge/float/absorb voltages by brand](https://diysolarforum.com/threads/lifepo4-charge-float-and-absorb-voltages-for-different-brands-of-batteries.34175/),
  [48V float voltage poll](https://diysolarforum.com/threads/poll-where-do-you-set-your-float-voltage-48v-lifepo4-systems.117767/),
  [16S bulk/float settings](https://diysolarforum.com/threads/16s-lifepo4-48v-bulk-float-settings.34190/),
  [SPF 3000TL LVM optimal settings](https://diysolarforum.com/threads/growatt-spf-3000tl-lvm-es-with-48v-battery-optimal-settings.64742/)
- LiFePO4 voltage/SOC chart reference:
  [cleversolarpower.com](https://cleversolarpower.com/lifepo4-voltage-chart/)
