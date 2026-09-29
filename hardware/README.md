# Hardware

**Nothing here has been built.** No aircraft exists. This directory holds the
specification the pitch refers to when it says *"a specified bill of materials,
not a flown platform"*, so that the claim can be checked rather than taken on
trust.

Every mass below is a manufacturer figure or a catalogue figure. **Nothing has
been weighed, assembled, powered or flown.**

## Bill of materials

| | Part | Mass |
|---|---|---:|
| Airframe | Holybro X500 V2 ARF — frame, motors, ESCs, propellers | 610 g |
| Battery | 4S 5000 mAh LiPo | ~480 g |
| Companion computer | Qualcomm QCS6490 class (Dragonwing RB3 Gen 2 is the board benchmarked) | ~100 g |
| Flight controller | Pixhawk 6C | 35 g |
| GNSS | GNSS module | ~30 g |
| RGB camera | Camera module | ~30 g |
| Telemetry | RFD868x pair | 14 g |
| Thermal camera | FLIR Lepton 3.5 | ~10 g |
| | **Itemised total** | **1,309 g** |

The deck quotes **~1.4 kg all-up**. The difference is wiring, mounts,
fasteners and the camera gimbal plate, which are not itemised here because they
have not been chosen. Treat 1.4 kg as the figure to design against and 1,309 g
as what is actually accounted for.

## Why the weight is the point

Under India's DGCA rules an all-up weight below 2 kg puts the aircraft in the
**Micro** category: registration and a remote pilot certificate, no type
certification. That is the difference between a student team being able to fly
this and not. The margin from 1.4 kg to the 2 kg ceiling is 600 g, and it is
the constraint every later choice has to respect.

## Why the radio link is on this list

865–868 MHz is licence-exempt in India (see [WPC](http://wpc.gov.in/)), which
is why the RFD868x is specified rather than a 2.4 GHz link. The link carries
**records, not video** — roughly 22 kbps against the ~3,000 kbps a video feed
would need, and a whole mission's report is 2.7 KB. That is a consequence of
running detection on the aircraft, and it is what makes the system work with
the network down.

## What has actually been measured, and on what

The **on-device benchmark is real** and was run on real silicon — a hosted
Dragonwing RB3 Gen 2 through Qualcomm AI Hub, not an estimate and not this
airframe. INT8 at 960 px: 209.5 ms per frame, 489 of 489 layers on the Hexagon
NPU. See [`../experiments/QUALCOMM_BENCHMARK.md`](../experiments/QUALCOMM_BENCHMARK.md).

A dev kit on a bench supply is not a flight computer in a vibrating airframe on
battery power. The figure transfers to the extent that the silicon is the same
and no further.

## What this specification does not prove

- **In-flight power draw.** AI Hub reports latency, not watts. Nothing here
  establishes how long the aircraft actually stays up with the payload running.
- **Thermal behaviour.** A companion computer in still air on a bench is not
  one in a sealed bay.
- **Endurance.** Holybro rate the X500 V2 at roughly 18 minutes hovering
  unloaded on 5 Ah. This payload cuts into that, and a larger battery buys time
  at the cost of pushing the all-up weight toward the 2 kg ceiling. That
  trade-off is the real constraint on the platform, and it is unresolved.
- **Vibration, EMI, mounting, camera calibration.** None considered.

## Still to do, in order

1. Weigh a real build and replace every `~` in the table above.
2. Power draw on battery, with detection running.
3. Endurance with the payload fitted.
4. CAD, camera mount, electrical architecture, wiring diagrams.
5. Flight testing.

## Status

📋 **Specification only.** Hardware work begins after the software prototype is
validated. The pitch says so, the dashboard shows no telemetry because there is
none to show, and this file exists so that the specification can be audited
rather than assumed.
