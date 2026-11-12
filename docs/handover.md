# Handover - Automating the Stückleistung section

**Python (pandas) vs. Google Apps Script**
Version: 2026-11-12 · Scope: *Stückleistung* section of the weekly report (7 slides)

---

## 1. Goal

The team drops the files exported from the MIS into a Google Drive folder. The files always have the same format. From there, the section's slides are generated automatically. Their tables and charts must show **at least the same information** as today's slides, with a similar look.

This document describes the same pipeline in two versions:

- **Python:** the prototype in this repository ([`charts.py`](../charts.py) and [`slides.py`](../slides.py)), used as the reference.
- **Apps Script:** the target version, running inside the client's Google Workspace.

---

## 2. Inputs (data contract)

| File | Content | Granularity |
|---|---|---|
| `Input stuckleistung_daredata.xlsx` | Stückleistung, units sold and hours, with deltas vs. VJ (prior year), PEP and Plan | Week × Region (SAN, TON, LOU, PAL + Gesamt) |
| `Input stuckleistung_daredata_top_flop.xlsx` | Stückleistung, Δ VJ and Δ Plan | Week × Store (~316 stores) |

Facts validated against the data:

- **Store-level Δ VJ and Δ Plan:** absolute differences in units/hour, not percentages.
- **New stores:** Δ VJ equals the value itself (empty VJ). Show it as "n/a".
- **Stores with no data:** a store at 0 units/hour in a week has no data or was closed that week; it is excluded from Top/Flop.
- **Revisions:** values for recent weeks are revised afterwards, mainly the hours.
- **Check against the original deck:** for weeks KW 24-26, 28 of 36 values match. The other 8 are all hours figures, off by at most 0.9%.

---

## 3. The pipeline, step by step

| # | Step | Python (prototype) | Apps Script (target) |
|---|---|---|---|
| 1 | **Trigger** | Someone runs `charts.py` then `slides.py` (laptop), or a scheduled job on Cloud Run | Time-driven trigger that polls the folder (e.g. every 10 min on Monday morning), or a "Generate" button |
| 2 | **Read files** | `pandas.read_excel` on local copies in `data/` | Convert each XLSX to a Google Sheet and paste the values into a fixed `Data` tab of the "engine" Sheet |
| 3 | **Validate format** | Check the expected headers; stop with a message naming the missing columns | Same: the script compares the header row; if it fails, nothing is generated and an email alert is sent |
| 4 | **Pick the week** | Most recent week in the data | A `Week` cell in a `Config` tab, auto-filled with the most recent week |
| 5 | **Calculations** | pandas: filter the week, rank Top/Flop, exclude stores without data | **Sheets formulas** (`FILTER`, `SORTN`, `QUERY`), one tab per slide. The script does no calculations |
| 6 | **Business rules** | Constants at the top of `charts.py` (trend window, Top/Flop size, exclusion threshold) | `Config` tab (Top/Flop exclusion threshold, number of stores, regions), editable by the team |
| 7 | **Colours (green/red)** | Set in code | Conditional formatting in Sheets |
| 8 | **Charts** | Rendered as images (matplotlib) and inserted into the deck; not editable in Slides | Chart built **once** in Sheets and linked into the deck; the script only refreshes it |
| 9 | **Tables** | Rendered as an image | Tables linked from Sheets, or filled by the script from each slide's tab (see section 6) |
| 10 | **Draft comments** | Sentences from simple rules (e.g. "regions below both plan and last year"), placed under each chart | Text formulas in Sheets, copied into the slide by the script |
| 11 | **Output** | Slides inserted directly into the Google Slides deck; a re-run replaces them | Copy of a Google Slides **template deck**, named after the week, in an output folder |
| 12 | **Notification** | Console message | Email or message to the team: "Section generated" (with link) or "Failed because…" |

**The key difference:** in Python, the logic lives in the code. In Apps Script, the logic lives in the "engine" Sheet, where anyone can see and edit it. The code only imports data and refreshes the deck, so there is little code to maintain.

---

## 4. Components of the Apps Script version

Everything sits in a **shared drive** owned by the team (recommended). The fallback is the client contact person's account.

1. **`Input` folder:** where the team drops the XLSX files.
2. **`Output` folder:** where the generated decks are saved.
3. **"Engine" Sheet:**
   - a raw `Data` tab for each file;
   - a `Config` tab for rules and the week;
   - one tab per slide, holding the calculations and charts.
4. **Template deck (Google Slides):** matches the look of the current slides, with charts and tables linked to the Sheet tabs.
5. **Script (Apps Script):** import, validate, refresh links, copy the deck, notify.

---

## 5. Coverage per slide (with the current files)

| Slide | Python (prototype) | Apps Script | Missing for full coverage |
|---|---|---|---|
| Cumulative view | ✘ not built yet (cumulative columns are in the export) | ✔ almost all | Month-to-date value; Δ vs. Plan year-to-date |
| Week overview | ✔ partly (KPI table) | ✔ partly | Daily values |
| Week in context | ✔ (Stückleistung and net-hours trends) | ✔ | - |
| By region | ✔ (with draft comments) | ✔ | - |
| Top / Flop stores | ✔ | ✔ | Confirm exclusion rules |
| Top Sales - Flop Performance | ✘ | ✘ | Export with sales per store and region |
| Cover and notes | Manual | Manual | - |

The gaps are about **data, not technology**. To meet the requirement of showing the same information as today, these extra exports must be available from the MIS.

---

## 6. To test before building

1. **Linked tables:** check whether the script can refresh Sheets-linked tables in Slides. Linked charts can be refreshed.
   - If tables can't, there are two alternatives: use a Sheets "table chart" (refreshable, but with limited formatting), or have the script fill the template tables with the values from each tab.
2. **XLSX → Sheets conversion:** check with a real file, including accented characters and decimal numbers.
3. **Look:** check that the template deck reproduces the current style closely enough for the team.

---

## 7. Summary comparison

| | Python | Apps Script |
|---|---|---|
| Runs on | Laptop, or Cloud Run (GCP) | Google servers (client's Workspace) |
| Installation | Python with [uv](https://docs.astral.sh/uv/) | None |
| Prerequisites | GCP project with the Slides and Drive APIs enabled | None |
| Automatic trigger | Needs a server (e.g. Cloud Run + Cloud Scheduler) | Native triggers or a button |
| Output | Native Google Slides, with charts and tables as images | Native Google Slides, with linked charts and tables |
| Where the logic lives | In the code | In the "engine" Sheet (visible) |
| Who changes rules | A developer | The team, in the `Config` tab |
| Initial effort | Low (prototype exists) | Medium (template, formulas, links) |
| Maintenance | Python code | Little code; mostly formulas and template |
| Limits | Chart images are shared by link on Drive for the few seconds it takes to insert them | 6 min per execution (enough for current volume) |

**Recommendation:** use the Python prototype to validate figures and rules with the team (session 1). Then build the Apps Script version as the long-term solution, reusing the rules already agreed.

---

## 8. Responsibilities

- **Solution owner:** the client contact person. Triggers run under their account; if the account changes, they must be re-enabled.
- **Team:** export the files from the MIS and drop them in the folder; review the generated deck and complete the comments.
- **Us:** build, documentation and support.

---

## 9. Open questions

- Where should the automation run: Apps Script, or Python on Cloud Run?
- What are the exact rules for excluding stores from Top/Flop?
- Is the "Δ Plan %" on the Top/Flop slide actually a difference in units/hour?
- Is Monday-morning data provisional? When does it become final?
- Can the MIS export daily values, month-to-date values, Δ vs. Plan year-to-date, and sales per store?
- Does a shared team drive exist, or can one be created?

---

## Glossary

- **Stückleistung:** units sold per hour worked (store productivity).
- **LJ / VJ:** current year / prior year (*laufendes Jahr* / *Vorjahr*).
- **PEP:** staff deployment plan (*Personaleinsatzplanung*).
- **KW:** calendar week (*Kalenderwoche*).
- **GJ:** fiscal year (*Geschäftsjahr*).
- **Gesamt:** total (all regions).
