import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Dialog Finance: Customer Profiling", layout="wide")

ORDER = ["Platinum", "Gold", "Silver", "Bronze", "Black"]
COLORS = {"Platinum": "#4a5a8a", "Gold": "#d4a72c", "Silver": "#9aa0a6", "Bronze": "#b0693a", "Black": "#4b4b4b"}

@st.cache_data
def load():
    return pd.read_csv("customers_tiered.csv")

df = load()

# ---------- Sidebar filters ----------
st.sidebar.header("Filters")
active = st.sidebar.radio("Customer status", ["All", "Active", "Inactive"])
tiers = st.sidebar.multiselect("Tier", ORDER, default=ORDER)
province = st.sidebar.multiselect("Province", sorted(df["Province"].unique()))
employ = st.sidebar.multiselect("Employment status", sorted(df["Employment Status"].unique()))

f = df[df["Tier"].isin(tiers)]
if active != "All":
    f = f[f["Active"] == active]
if province:
    f = f[f["Province"].isin(province)]
if employ:
    f = f[f["Employment Status"].isin(employ)]

st.title("Customer Profiling Dashboard")
st.caption("Dialog Finance PLC · 1,000 cleaned customer records · 5-tier scoring model")

if f.empty:
    st.warning("No customers match these filters.")
    st.stop()

# ---------- KPIs ----------
plat = f[f["Tier"] == "Platinum"]
below = f[f["Tier"] != "Platinum"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Customers", f"{len(f):,}")
c2.metric("Active %", f"{(f['Active'] == 'Active').mean() * 100:.0f}%")
c3.metric("Platinum customers", f"{len(plat):,}", f"{(plat['Platinum_Status'] == 'In decline').sum()} in decline", delta_color="inverse")
c4.metric("Quick wins (within 3 pts of next tier)", f"{(below['Gap_Points'] <= 3).sum():,}")

tab1, tab2, tab3, tab4 = st.tabs(["Tier overview", "Moving customers up", "Platinum retention", "Customer list"])

# ---------- Tab 1 ----------
with tab1:
    a, b = st.columns(2)
    cnt = f["Tier"].value_counts().reindex(ORDER).fillna(0).reset_index()
    cnt.columns = ["Tier", "Customers"]
    a.plotly_chart(px.bar(cnt, x="Tier", y="Customers", color="Tier", color_discrete_map=COLORS,
                          text="Customers", title="Customers by tier"), use_container_width=True)
    b.plotly_chart(px.box(f, x="Tier", y="Score", color="Tier", color_discrete_map=COLORS,
                          category_orders={"Tier": ORDER}, title="Score distribution by tier"), use_container_width=True)

    g = f.groupby("Tier")
    prof = pd.DataFrame({
        "Customers": g.size(),
        "Active %": g["Active"].apply(lambda s: round((s == "Active").mean() * 100)),
        "Median 6M balance (LKR)": g["Avg Balance Last 6 Months (LKR)"].median().round(0),
        "Median FD + investments (LKR)": g["FD_plus_Investment"].median().round(0),
        "Avg products": g["Total Products Held"].mean().round(2),
        "Salary credit %": g["Salary Credit Flag"].apply(lambda s: round((s == "Yes").mean() * 100)),
        "Txn days / month": g["Transaction Days per Month"].median(),
        "App logins / month": g["Mobile App Logins per Month"].median(),
        "Churn-risk flag %": g["Churn Risk Flag"].apply(lambda s: round((s == "Yes").mean() * 100)),
    }).reindex(ORDER).dropna(how="all")
    st.subheader("Tier profile")
    st.dataframe(prof.T, use_container_width=True)

# ---------- Tab 2 ----------
with tab2:
    st.subheader("Biggest barrier to moving up one tier")
    if below.empty:
        st.info("Select at least one tier below Platinum.")
    else:
        bar = below.groupby(["Tier", "Biggest_Barrier"]).size().reset_index(name="Customers")
        st.plotly_chart(px.bar(bar, x="Customers", y="Tier", color="Biggest_Barrier", orientation="h",
                               category_orders={"Tier": ["Gold", "Silver", "Bronze", "Black"]},
                               barmode="relative", title="Customers by biggest barrier"), use_container_width=True)
        s = below.groupby("Tier").agg(Customers=("Score", "size"),
                                      Median_gap_pts=("Gap_Points", "median"),
                                      Quick_wins=("Gap_Points", lambda x: int((x <= 3).sum()))).reindex(["Gold", "Silver", "Bronze", "Black"]).dropna()
        st.dataframe(s, use_container_width=True)
        st.caption("Gap = points needed to reach the next tier's score cut-off. Quick wins are within 3 points.")

# ---------- Tab 3 ----------
with tab3:
    full_plat = df[df["Tier"] == "Platinum"]
    st.subheader(f"Platinum health ({len(full_plat)} customers, before filters)")
    a, b = st.columns(2)
    stt = full_plat["Platinum_Status"].value_counts().reindex(["Stable", "Watch", "In decline"]).reset_index()
    stt.columns = ["Status", "Customers"]
    a.plotly_chart(px.pie(stt, names="Status", values="Customers", hole=0.5, color="Status",
                          color_discrete_map={"Stable": "#2e9e5b", "Watch": "#e0a020", "In decline": "#d64545"}), use_container_width=True)
    sig = {"Unhappy (5+ complaints or NPS ≤ 3)": "Sig_Unhappy", "No transaction 60+ days": "Sig_No_Txn_60d",
           "No app login 90+ days": "Sig_No_Login_90d", "Balance down 25%+": "Sig_Balance_Falling",
           "Balance under LKR 1,000 nine+ times": "Sig_Low_Balance_9x", "Churn-risk flag": "Sig_Churn_Flag"}
    sg = pd.DataFrame({"Signal": list(sig), "% of Platinum": [round(full_plat[c].mean() * 100) for c in sig.values()]})
    b.plotly_chart(px.bar(sg, x="% of Platinum", y="Signal", orientation="h", title="Warning signals"), use_container_width=True)
    st.subheader("Watchlist (Watch + In decline)")
    wl = full_plat[full_plat["Platinum_Status"] != "Stable"].sort_values(["Platinum_Signals", "Avg Balance Last 6 Months (LKR)"], ascending=False)
    st.dataframe(wl[["Customer ID", "Score", "Platinum_Signals", "Platinum_Status", "Avg Balance Last 6 Months (LKR)", "Preferred Contact Channel"]],
                 use_container_width=True, hide_index=True)

# ---------- Tab 4 ----------
with tab4:
    cols = ["Customer ID", "Tier", "Score", "Active", "Age", "Province", "Employment Status", "Avg Balance Last 6 Months (LKR)",
            "Total Products Held", "Biggest_Barrier", "Gap_Points"]
    st.dataframe(f[cols].sort_values("Score", ascending=False), use_container_width=True, hide_index=True)
    st.download_button("Download filtered customers (CSV)", f.to_csv(index=False), "filtered_customers.csv", "text/csv")

with st.expander("Method notes"):
    st.markdown("""
**Active** = transacted in the last 90 days AND (8+ transaction days a month OR app login in the last 60 days).
The bank's Dormancy Flag was not used because it contradicts recent transactions for 142 customers.

**Score (0-100)** = Balance & wealth 30% · Activity 25% · Product depth 15% · Digital 15% · Salary 10% · Loyalty 5%, less risk deductions.
Platinum = top 10% by score and must be Active; Gold next 20%; Silver next 30%; Bronze next 25%; Black bottom 15%.
""")
