# Optional: capacity / expansion planning

**5.7.3 version guide: native acceptance and publication status are established by CI records and Release attachments for the corresponding commit; this guide does not assert a pass.** Older version-labelled examples, screenshots and pass counts below are historical evidence, not a fresh 5.7.3 run. [Release status](../verification/5.7.3-release-acceptance.md).

A known_subtotal is not complete demand and must not be represented as available supply capacity. Identify current and expansion demands separately and complete operating-condition/boundary evidence before judging capacity. Show N−1 separately from normal operation and review simultaneous remaining supply and common-cause failures.

[繁體中文](capacity.md) · [Beginner workbench](workbench.en.md) · [Offline guide](../tutorial/README.md)

In the full workbench, select Capacity / expansion planning. The separate Capacity / expansion / alternatives window screens ELECTRIC (kW), CHW/PCW (LPM) and EXHAUST (CMH). It is an independent plan, not an automatic appendix to the main workspace.

1. Enter plan name, complete service scope, additional margin and its basis. Leave unknown data blank; enter 0 only for confirmed zero demand.
1. On Existing / expansion demand, choose a system and Add row. Enter row ID, physical asset/source ID, service boundary, quantity and summer/winter per-unit values. Use current for existing loads and expansion for additions. Apply coincidence only if not already included in the per-unit value. Source-included margin is recorded, not multiplied again.
1. On Conditions and source, enter the relevant electrical voltage/phases/frequency, fluid/supply/return/properties, or exhaust type/temperature/absolute pressure/static pressure. Add document and revision references. Preserve unresolved tasks in Pending and notes. Confirm complete demand only after checking that it is more than a known subtotal.
1. On Supply capacity, add same-boundary, same-condition per-unit ratings, quantity and derating. Different panels, circuits, exhaust types or conditions remain separate and cannot offset a deficit. Do not duplicate a physical asset under different row IDs.
1. Without alternatives, all rows are evaluated. To compare alternatives, select the full demand and supply rows on both tabs, then use Save the selected rows from both tabs as an alternative. Include every current/expansion demand for that alternative. Alternatives are compared, not added.
1. Confirm scope, complete register and N−1 assumptions only after review, then Recalculate. Check normal and N−1 capacity, headroom, deficits and pending data separately. A numerical result is not a pass.
1. Save plan as stores an independent JSON reopened from this window; Export report saves TXT. **Save workspace does not save this capacity plan**, and a capacity JSON is not a main-workspace JSON.

## Starting from the demand ledger

Capture from demand summary creates a source snapshot, not a complete facility register or supply-capacity list. Save the current plan before replacing it by a capture. Resolve source tasks and conditions, then add complete demands and supplies. Main/source edits or switching projects can make the capture stale. Recapture and review; recalculation alone cannot refresh an old source snapshot. Manually edited captured values also need updated source documents/revisions.

**Capacity export rechecks inputs but can export a report marked data/review required.** Stale sources, missing values and incomplete confirmation do not become adequate capacity. Unlike invalid direct-lighting results, such reports are not all blocked from export; read their status.

## Synthetic arithmetic example

For one panel and identical conditions: existing 100 kW + expansion 60 kW, coincidence 1 each, plus 10% additional margin gives demand 176 kW. Three 100 kW units, each derated to 0.9, provide 270 kW normally. N−1 removes the largest single derated unit (90 kW), leaving 180 kW. Headroom is 94/4 kW. Sum each summer/winter case before comparing peaks; do not add individual peaks from different seasons.

N−1 only removes the largest single derated unit and assumes the others can supply simultaneously. It does not verify common-cause failure, changeover, electrical kVA/starting/short-circuit/protection, full hydraulic head or fan curves. Screening capacity adequate is not complete FEED or engineering approval. Never clear unresolved tasks merely to obtain a pass.
