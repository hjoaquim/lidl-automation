# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas", "openpyxl", "matplotlib"]
# ///
"""Generate charts from the Excel exports in data/ into charts/. Run: uv run charts.py"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

DATA = Path("data")
OUT = Path("charts")
OUT.mkdir(exist_ok=True)

WEEK, NAME = "Woche T03", "Unnamed: 2"
KPI = "Stückleistung Filiale (Stk./h) (1104048.01)"
DELTA_PLAN = "Stückleistung Filiale (Stk./h) ∆ Plan Filiale (1104048.45)"
DELTA_VJ = "Stückleistung Filiale (Stk./h) ∆ VJ Woche (1104048.05)"
HOURS, HOURS_PLAN = "Nettostunden (1104004.46)", "Nettostunden Filiale Plan Filiale"
HOURS_DELTA_PLAN = "Nettostunden delta PLAN"
SALES, SALES_DELTA_VJ = (
    "Abverkauf Filiale Gesamt (Stk./kg) (1403053.01)",
    "Abverkauf Filiale Gesamt ∆ VJ Woche % (1403053.11)",
)

# Business rules.
TREND_WEEKS = 52  # weeks shown in the trend charts
TOP_N = 10  # stores per side in Top/Flop
MIN_STUECKLEISTUNG = 0  # stores at or below this (no data or closed) are excluded from Top/Flop


def save(name, caption):
    """Write charts/<name>.png plus charts/<name>.txt with the caption for the slide."""
    plt.savefig(OUT / f"{name}.png", dpi=150, bbox_inches="tight", pad_inches=0.05)  # crop to content
    plt.close()
    (OUT / f"{name}.txt").write_text(caption + "\n")


def load(file, columns):
    """Read an export and stop with a clear message if its format changed."""
    df = pd.read_excel(DATA / file)
    if missing := [c for c in columns if c not in df.columns]:
        raise SystemExit(f"{file}: unexpected format, missing columns: {missing}")
    return df


def short(name):
    return name.split(" - ")[-1]  # "LOU - Loures" -> "Loures"


# Gesellschaft-level export. Each week has one row per Gesellschaft plus a "Gesamt" (total) row.
# Weeks are "YYYY KW NN" (zero-padded), so string sort == chronological sort.
df = load(
    "Input stuckleistung_daredata.xlsx",
    [WEEK, NAME, KPI, DELTA_PLAN, DELTA_VJ, HOURS, HOURS_PLAN, HOURS_DELTA_PLAN, SALES, SALES_DELTA_VJ],
)
df = df[df[WEEK] != "Gesamt"]  # drop the grand total over all weeks
df[NAME] = df[NAME].fillna("Gesamt")
weeks = sorted(df[WEEK].unique())[-TREND_WEEKS:]
df = df[df[WEEK].isin(weeks)].sort_values(WEEK, kind="stable")  # export is newest-first
latest = weeks[-1]
regions, total = df[df[NAME] != "Gesamt"], df[df[NAME] == "Gesamt"].set_index(WEEK)
now = df[df[WEEK] == latest].set_index(NAME)  # latest week, one row per Gesellschaft + "Gesamt"
tot = now.loc["Gesamt"]
reg = now.drop("Gesamt")

# 1) Weekly Stückleistung per Gesellschaft over the trend window.
ax = regions.pivot(index=WEEK, columns=NAME, values=KPI).plot(
    figsize=(12, 5), title=f"Stückleistung (Stk./h) per Gesellschaft, last {TREND_WEEKS} weeks"
)
ax.set_xlabel("")
ax.set_ylabel("Stk./h")
ax.legend(title=None)
avg = total[KPI].mean()
save(
    "1_stueckleistung_trend",
    f"In {latest}, overall Stückleistung reached {tot[KPI]:.1f} Stk./h, {tot[KPI] - avg:+.1f} vs the {TREND_WEEKS}-week "
    f"average of {avg:.1f}. {short(reg[KPI].idxmax())} led with {reg[KPI].max():.1f} Stk./h; "
    f"{short(reg[KPI].idxmin())} trailed with {reg[KPI].min():.1f}.",
)

# 2) Top/Flop stores vs plan, latest week.
tf = load("Input stuckleistung_daredata_top_flop.xlsx", [WEEK, NAME, KPI, DELTA_PLAN])
tf = tf[(tf[WEEK] == latest) & tf[NAME].notna() & (tf[KPI] > MIN_STUECKLEISTUNG)]
tf = tf.dropna(subset=[DELTA_PLAN]).sort_values(DELTA_PLAN)
top_flop = pd.concat([tf.head(TOP_N), tf.tail(TOP_N)])

fig, ax = plt.subplots(figsize=(10, 7))
ax.barh(top_flop[NAME], top_flop[DELTA_PLAN], color=["tab:red" if v < 0 else "tab:green" for v in top_flop[DELTA_PLAN]])
ax.axvline(0, color="black", linewidth=0.8)
ax.set_title(f"Top/Flop {TOP_N} stores: Stückleistung Δ Plan (Stk./h), {latest}")
best, worst = tf.iloc[-1], tf.iloc[0]
save(
    "2_top_flop",
    f"{(tf[DELTA_PLAN] > 0).sum()} of {len(tf)} stores beat their Stückleistung plan in {latest}. "
    f"Best: {best[NAME]} ({best[DELTA_PLAN]:+.1f} Stk./h); worst: {worst[NAME]} ({worst[DELTA_PLAN]:+.1f} Stk./h).",
)

# 3) Stückleistung vs plan and vs last year per Gesellschaft, latest week.
ax = (
    now[[DELTA_PLAN, DELTA_VJ]]
    .set_axis(["Δ Plan", "Δ Vorjahr (Woche)"], axis=1)
    .plot.bar(figsize=(10, 5), rot=0, title=f"Stückleistung Δ (Stk./h) per Gesellschaft, {latest}")
)
ax.axhline(0, color="black", linewidth=0.8)
ax.set_xlabel("")
ax.set_ylabel("Stk./h")
lagging = [short(n) for n in reg.index[(reg[DELTA_PLAN] < 0) & (reg[DELTA_VJ] < 0)]]
save(
    "3_delta_per_gesellschaft",
    f"{(reg[DELTA_PLAN] > 0).sum()} of {len(reg)} Gesellschaften are above plan in {latest}; overall "
    f"{tot[DELTA_PLAN]:+.1f} Stk./h vs plan and {tot[DELTA_VJ]:+.1f} vs the same week last year."
    + (f" Below both plan and last year: {', '.join(lagging)}." if lagging else ""),
)

# 4) Net hours actual vs plan, all Gesellschaften, over the trend window.
ax = (
    total[[HOURS, HOURS_PLAN]]
    .set_axis(["Ist", "Plan"], axis=1)
    .plot(figsize=(12, 5), title=f"Nettostunden Ist vs Plan (Gesamt), last {TREND_WEEKS} weeks")
)
ax.set_xlabel("")
ax.set_ylabel("Stunden")
ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
save(
    "4_nettostunden_ist_vs_plan",
    f"Net hours in {latest}: {tot[HOURS]:,.0f} vs a plan of {tot[HOURS_PLAN]:,.0f} ({tot[HOURS_DELTA_PLAN]:+.1f}%). "
    f"Actual hours exceeded plan in {(total[HOURS] > total[HOURS_PLAN]).sum()} of the last {len(total)} weeks.",
)

# 5) KPI summary table, latest week.
cols = {
    NAME: ("Gesellschaft", "{}"),
    KPI: ("Stückleistung\n(Stk./h)", "{:.1f}"),
    DELTA_PLAN: ("Δ Plan\n(Stk./h)", "{:+.1f}"),
    DELTA_VJ: ("Δ VJ Woche\n(Stk./h)", "{:+.1f}"),
    HOURS: ("Nettostunden", "{:,.0f}"),
    HOURS_DELTA_PLAN: ("Nettostunden\nΔ Plan", "{:+.1f}%"),
    SALES: ("Abverkauf\n(Stk./kg)", "{:,.0f}"),
    SALES_DELTA_VJ: ("Abverkauf\nΔ VJ Woche", "{:+.1f}%"),
}
table = df[df[WEEK] == latest][list(cols)]
cells = [[fmt.format(v) for v, (_, fmt) in zip(row, cols.values())] for row in table.itertuples(index=False)]

fig, ax = plt.subplots(figsize=(2, 3))  # narrow axes: the table overflows it, so the crop fits the table
ax.axis("off")
ax.set_title(f"KPI summary, {latest}")
t = ax.table(cellText=cells, colLabels=[label for label, _ in cols.values()], loc="center", cellLoc="right")
t.auto_set_font_size(False)
t.set_fontsize(10)
t.auto_set_column_width(range(len(cols)))
for (r, c), cell in t.get_celld().items():
    cell.set_height(0.24 if r == 0 else 0.12)
    if c == 0:
        cell.set_text_props(ha="left")
    if r == 0 or cells[r - 1][0] == "Gesamt":
        cell.set_text_props(weight="bold")
save(
    "5_kpi_table",
    f"Overall Stückleistung of {tot[KPI]:.1f} Stk./h ({tot[DELTA_PLAN]:+.1f} vs plan, {tot[DELTA_VJ]:+.1f} vs last year) "
    f"on Abverkauf of {tot[SALES]:,.0f} Stk./kg ({tot[SALES_DELTA_VJ]:+.1f}% vs last year), "
    f"with net hours {tot[HOURS_DELTA_PLAN]:+.1f}% vs plan.",
)

print(f"Charts written to {OUT}/")
