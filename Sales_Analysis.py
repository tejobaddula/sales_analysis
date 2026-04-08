import streamlit as st
import pandas as pd
import plotly.express as px
import json
import requests
import snowflake.connector

# -------------------------
# PAGE CONFIG
# -------------------------
st.set_page_config(page_title="Zipline Sales Dashboard", layout="wide")

# -------------------------
# CORTEX ANALYST CONFIG
# -------------------------
SEMANTIC_MODEL_PATH = "@ORDERS_DB.ANALYTICS.ORDERS_STAGE/orders_semantic_model.yaml"
SNOWFLAKE_ACCOUNT   = st.secrets["snowflake"]["account"]
SNOWFLAKE_USER      = st.secrets["snowflake"]["user"]
SNOWFLAKE_PASSWORD  = st.secrets["snowflake"]["password"]

# -------------------------
# STYLES
# -------------------------
st.markdown('''
<style>
.center-title{
    text-align:center;
    font-size:40px;
    font-weight:bold;
    color:#D32F2F; 
    margin-bottom:20px;
}
.kpi-card {
    padding:25px;
    border-radius:12px;
    color:white;
    text-align:center;
    font-family:sans-serif;
    box-shadow:0px 4px 10px rgba(0,0,0,0.15);
    background:#D32F2F;
    margin-bottom:15px;
}
.kpi-title{ font-size:18px; opacity:0.9; }
.kpi-value{ font-size:40px; font-weight:bold; }
.stButton>button {
    background-color: #ffffff;
    color: #D32F2F;
    border: 3px solid #D32F2F;
    border-radius: 12px;
    padding: 15px 25px;
    font-size: 20px;
    font-weight: bold;
    width: 100%;
    transition: 0.3s;
    display: block;
    margin: 10px 0;
}
.stButton>button:hover {
    background-color: #ffe5e5;
    color: #B71C1C;
    border-color: #B71C1C;
}
</style>
''', unsafe_allow_html=True)

# -------------------------
# SNOWFLAKE CONNECTION
# -------------------------
@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        user=st.secrets["snowflake"]["user"],
        password=st.secrets["snowflake"]["password"],
        account=st.secrets["snowflake"]["account"],
        warehouse=st.secrets["snowflake"]["warehouse"],
        database=st.secrets["snowflake"]["database"],
        schema=st.secrets["snowflake"]["schema"]
    )

# -------------------------
# LOAD DATA
# -------------------------
@st.cache_data(ttl=3600)
def load_data():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM ORDERS", conn)
    df.columns = [c.lower().replace(' ', '_') for c in df.columns]
    df.rename(columns={
        'order_datetime': 'order datetime',
        'delivery_datetime': 'delivery datetime'
    }, inplace=True)
    df['net_revenue'] = round((df['subtotal'] * df['commission_rate']) + df['fees'] - df['promotion'], 2)
    df['order datetime'] = pd.to_datetime(df['order datetime'])
    df['delivery datetime'] = pd.to_datetime(df['delivery datetime'])
    df['delivery_date'] = df['order datetime'].dt.date
    df['delivery_minutes'] = ((df['delivery datetime'] - df['order datetime']).dt.total_seconds() / 60).round(2)
    return df

orders = load_data()

# -------------------------
# KPI VALUES
# -------------------------
total_net_revenue   = orders['net_revenue'].sum().round(2)
total_orders        = orders['order_id'].nunique()
total_success       = len(orders[orders['order_status'] == "Successful"])
total_cancellations = total_orders - total_success
all_merchants       = sorted(orders['merchant'].dropna().unique().tolist())

# -------------------------
# SESSION STATE
# -------------------------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "selected_merchants" not in st.session_state:
    st.session_state.selected_merchants = all_merchants


# -------------------------
# SHARED FILTER COMPONENT
# -------------------------
def render_filters(page_key: str):
    col_back, col_spacer, col_date = st.columns([2, 3, 2])

    with col_back:
        if st.button("⬅ Back to Dashboard", key=f"back_{page_key}"):
            st.session_state.page = "home"
            st.rerun()

    with col_date:
        st.markdown('<p style="color:#D32F2F; font-weight:bold; margin-bottom:2px;">Select Date Range</p>', unsafe_allow_html=True)
        start_date, end_date = st.date_input(
            "",
            [orders['order datetime'].min().date(), orders['order datetime'].max().date()],
            key=f"date_{page_key}"
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<p style="color:#D32F2F; font-weight:bold; margin-bottom:2px;">Select Merchant(s)</p>', unsafe_allow_html=True)

    dropdown_options = ["✅ All Merchants"] + all_merchants

    if set(st.session_state.selected_merchants) == set(all_merchants):
        default_selection = ["✅ All Merchants"] + all_merchants
    else:
        default_selection = st.session_state.selected_merchants

    raw_selection = st.multiselect(
        "",
        options=dropdown_options,
        default=default_selection,
        key=f"merchants_{page_key}",
        placeholder="Choose merchants...",
    )

    if "✅ All Merchants" in raw_selection:
        selected_merchants = all_merchants
        st.session_state.selected_merchants = all_merchants
    else:
        selected_merchants = [m for m in raw_selection if m != "✅ All Merchants"]
        st.session_state.selected_merchants = selected_merchants

    st.markdown("---")
    return start_date, end_date, selected_merchants


def apply_filters(start_date, end_date, selected_merchants):
    filtered = orders[
        (orders['order datetime'].dt.date >= start_date) &
        (orders['order datetime'].dt.date <= end_date)
    ]
    if selected_merchants:
        filtered = filtered[filtered['merchant'].isin(selected_merchants)]
    return filtered.copy()


# -------------------------
# CUSTOMER EXPERIENCE DASHBOARD
# -------------------------
def customer_experience_page():
    start_date, end_date, selected_merchants = render_filters("cx")
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("Customer Experience Dashboard")
    filtered_orders = apply_filters(start_date, end_date, selected_merchants)

    if filtered_orders.empty:
        st.warning("No data available for the selected filters.")
        return

    avg_delivery  = filtered_orders['delivery_minutes'].mean().round(2)
    avg_nps       = filtered_orders['nps'].mean().round(2)
    avg_attempts  = filtered_orders['delivery_attempts'].median()
    cancelled     = len(filtered_orders[filtered_orders['order_status'] != "Successful"])
    cancel_rate   = round(cancelled / len(filtered_orders), 3) if len(filtered_orders) > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="kpi-card"><div class="kpi-title">Avg Delivery Time</div><div class="kpi-value">{avg_delivery}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card"><div class="kpi-title">Avg NPS</div><div class="kpi-value">{avg_nps}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card"><div class="kpi-title">Avg Delivery Attempts</div><div class="kpi-value">{avg_attempts}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi-card"><div class="kpi-title">Cancellation Rate</div><div class="kpi-value">{cancel_rate*100:.1f}%</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    delivery_trend = filtered_orders.groupby('delivery_date')['delivery_minutes'].mean().reset_index()
    fig1 = px.line(delivery_trend, x='delivery_date', y='delivery_minutes',
                   title='Trend of Average Delivery Time per Day', markers=True,
                   color_discrete_sequence=['#FF4500'],
                   hover_data={'delivery_date': True, 'delivery_minutes': ':.2f'})
    fig1.update_layout(xaxis_title='Date', yaxis_title='Average Delivery Time (minutes)',
                       xaxis=dict(tickformat="%b %d", tickangle=45))
    st.plotly_chart(fig1, use_container_width=True)

    filtered_orders['order_hour'] = filtered_orders['order datetime'].dt.hour
    fig2 = px.histogram(filtered_orders, x='order_hour', nbins=24,
                        title='Order Time Distribution by Hour',
                        labels={'order_hour': 'Hour of Day', 'count': 'Order Count'},
                        color_discrete_sequence=['#FF4500'])
    fig2.update_layout(xaxis_title='Hour of Day', yaxis_title='Order Count',
                       xaxis=dict(tickmode='linear', tick0=0, dtick=1))

    cancellation_counts = filtered_orders['cancellation_reason'].dropna().value_counts().reset_index()
    cancellation_counts.columns = ['Cancellation Reason', 'Count']

    col1, col2 = st.columns(2)
    col1.plotly_chart(fig2, use_container_width=True)

    if len(cancellation_counts) > 0:
        fig_pie = px.pie(cancellation_counts, names='Cancellation Reason', values='Count',
                         color='Cancellation Reason',
                         color_discrete_sequence=['#FF9C00','#FE8800','#FF5503','#CE0A18','#E12426'],
                         title='Cancellation Reasons Distribution')
        fig_pie.update_traces(textinfo='percent', marker=dict(line=dict(color='white', width=2)))
        fig_pie.update_layout(template='plotly_white')
        col2.plotly_chart(fig_pie, use_container_width=True)
    else:
        col2.info("No cancellation reasons available for the selected filters.")


# -------------------------
# CUSTOMER GROWTH DASHBOARD
# -------------------------
def customer_growth_page():
    start_date, end_date, selected_merchants = render_filters("growth")
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("Customer Growth Dashboard")
    filtered_orders = apply_filters(start_date, end_date, selected_merchants)

    if filtered_orders.empty:
        st.warning("No data available for the selected filters.")
        return

    total_customers        = filtered_orders['user_id'].nunique()
    avg_orders_per_customer = round(len(filtered_orders) / total_customers, 2) if total_customers > 0 else 0
    orders_per_customer    = filtered_orders.groupby('user_id').size()
    repeat_customers       = (orders_per_customer > 1).sum()
    repeat_purchase_rate   = round((repeat_customers / total_customers) * 100, 2) if total_customers > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="kpi-card"><div class="kpi-title">Total Customers</div><div class="kpi-value">{total_customers}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card"><div class="kpi-title">Avg Orders per Customer</div><div class="kpi-value">{avg_orders_per_customer}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card"><div class="kpi-title">Repeat Purchase Rate</div><div class="kpi-value">{repeat_purchase_rate}%</div></div>', unsafe_allow_html=True)

    filtered_orders['order_week'] = filtered_orders['order datetime'].dt.to_period('W').apply(lambda r: r.start_time)
    wau = filtered_orders.groupby('order_week')['user_id'].nunique().reset_index(name='weekly_active_users')
    wau['WoW_growth_rate'] = wau['weekly_active_users'].pct_change() * 100
    growth_vis = wau[wau['WoW_growth_rate'].notna()].copy()

    fig1 = px.line(wau, x='order_week', y='weekly_active_users', title='Weekly Active Users',
                   markers=True, color_discrete_sequence=['#FF4500'])
    fig1.update_layout(xaxis_title='Week', yaxis_title='Weekly Active Users')

    fig2 = px.bar(growth_vis, x='order_week', y='WoW_growth_rate',
                  title='Week-over-Week Growth Rate (%)', color_discrete_sequence=['#FF4500'])
    fig2.update_layout(xaxis_title='Week', yaxis_title='WoW Growth Rate (%)')

    st.plotly_chart(fig1, use_container_width=True)
    st.plotly_chart(fig2, use_container_width=True)


# -------------------------
# FINANCIAL RESULTS DASHBOARD
# -------------------------
def financial_results_page():
    start_date, end_date, selected_merchants = render_filters("financial")
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("Financial Results Dashboard")
    filtered_orders = apply_filters(start_date, end_date, selected_merchants)

    if filtered_orders.empty:
        st.warning("No data available for the selected filters.")
        return

    total_net_revenue  = filtered_orders['net_revenue'].sum().round(2)
    total_orders       = filtered_orders['order_id'].nunique()
    total_customers    = filtered_orders['user_id'].nunique()
    aov                = round(total_net_revenue / total_orders, 2) if total_orders > 0 else 0
    revenue_per_customer = round(total_net_revenue / total_customers, 2) if total_customers > 0 else 0
    promotion_rate     = round(filtered_orders['promotion'].sum() / filtered_orders['subtotal'].sum(), 2) if filtered_orders['subtotal'].sum() > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="kpi-card"><div class="kpi-title">Total Net Revenue</div><div class="kpi-value">${total_net_revenue}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card"><div class="kpi-title">Average Order Value</div><div class="kpi-value">${aov}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card"><div class="kpi-title">Revenue Per Customer</div><div class="kpi-value">${revenue_per_customer}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi-card"><div class="kpi-title">Promotion Rate</div><div class="kpi-value">{promotion_rate*100:.1f}%</div></div>', unsafe_allow_html=True)

    filtered_orders['order_date'] = filtered_orders['order datetime'].dt.date
    daily_revenue = filtered_orders.groupby('order_date')['net_revenue'].sum().reset_index()
    fig1 = px.line(daily_revenue, x='order_date', y='net_revenue', title='Daily Revenue Trend',
                   markers=True, color_discrete_sequence=['#FF4500'])
    fig1.update_layout(xaxis_title='Date', yaxis_title='Revenue ($)')
    st.plotly_chart(fig1, use_container_width=True)

    filtered_orders['promo_flag'] = filtered_orders['promotion'].apply(lambda x: 'With Promo' if x > 0 else 'No Promo')
    promo_summary = filtered_orders.groupby('promo_flag').agg(
        total_orders=('order_id', 'nunique'), total_revenue=('net_revenue', 'sum')).reset_index()
    promo_melt = promo_summary.melt(id_vars='promo_flag',
                                    value_vars=['total_orders', 'total_revenue'],
                                    var_name='metric', value_name='value')
    fig2 = px.bar(promo_melt, x='metric', y='value', color='promo_flag',
                  color_discrete_sequence=['#FF9C9C', '#FF3333'], barmode='group',
                  title='Orders and Revenue: Promo vs No Promo',
                  labels={'metric': 'Metric', 'value': 'Value', 'promo_flag': 'Promotion Type'})
    st.plotly_chart(fig2, use_container_width=True)


# -------------------------
# MERCHANT PERFORMANCE PAGE
# -------------------------
def merchant_performance_page():
    start_date, end_date, selected_merchants = render_filters("merchant")
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("Merchant Performance Dashboard")
    filtered_orders = apply_filters(start_date, end_date, selected_merchants)

    if filtered_orders.empty:
        st.warning("No data available for the selected filters.")
        return

    def cancellation_rate(x):
        return (x != 'Successful').mean()

    report_card = filtered_orders.groupby('merchant').agg(
        orders_per_merchant=('order_id', 'count'),
        net_revenue_per_merchant=('net_revenue', 'sum'),
        avg_delivery_time_per_merchant=('delivery_minutes', 'mean'),
        cancellation_rate_per_merchant=('order_status', cancellation_rate),
        avg_NPS_per_merchant=('nps', 'mean')
    ).reset_index()

    report_card[['net_revenue_per_merchant', 'avg_delivery_time_per_merchant',
                 'cancellation_rate_per_merchant', 'avg_NPS_per_merchant']] = report_card[[
        'net_revenue_per_merchant', 'avg_delivery_time_per_merchant',
        'cancellation_rate_per_merchant', 'avg_NPS_per_merchant']].round(2)

    report_card.rename(columns={
        'merchant': 'Merchant',
        'orders_per_merchant': 'Orders per Merchant',
        'net_revenue_per_merchant': 'Net Revenue per Merchant',
        'avg_delivery_time_per_merchant': 'Avg Delivery Time',
        'cancellation_rate_per_merchant': 'Cancellation Rate',
        'avg_NPS_per_merchant': 'Avg NPS'
    }, inplace=True)

    st.subheader("Merchant Performance: Delivery Time vs NPS")
    fig_scatter = px.scatter(report_card, x='Avg Delivery Time', y='Avg NPS',
                             size='Orders per Merchant', color='Merchant', hover_name='Merchant',
                             title='Delivery Time vs Customer Satisfaction by Merchant')
    fig_scatter.add_vline(x=report_card['Avg Delivery Time'].mean(), line_dash="dash", line_color="red")
    fig_scatter.add_hline(y=report_card['Avg NPS'].mean(), line_dash="dash", line_color="red")
    fig_scatter.update_layout(xaxis_title='Average Delivery Time (minutes)',
                               yaxis_title='Average NPS', legend_title='Merchant')
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.subheader("Merchant Performance Table")
    st.dataframe(
        report_card.style
            .format({"Net Revenue per Merchant": "{:.2f}", "Avg Delivery Time": "{:.2f}",
                     "Cancellation Rate": "{:.2f}", "Avg NPS": "{:.2f}"})
            .set_table_styles([{'selector': 'th', 'props': [
                ('border', '2px solid black'), ('background-color', '#D32F2F'), ('color', 'white')]}]),
        use_container_width=True
    )


# -------------------------
# CORTEX ANALYST PAGE
# -------------------------
@st.cache_data(ttl=1800)
def get_snowflake_token():
    """Get a JWT token for Snowflake REST API authentication."""
    import snowflake.connector
    conn = snowflake.connector.connect(
        user=st.secrets["snowflake"]["user"],
        password=st.secrets["snowflake"]["password"],
        account=st.secrets["snowflake"]["account"],
        warehouse=st.secrets["snowflake"]["warehouse"],
        database=st.secrets["snowflake"]["database"],
        schema=st.secrets["snowflake"]["schema"]
    )
    token = conn.rest.token
    conn.close()
    return token


def call_cortex_analyst(user_message: str) -> dict:
    """Call Cortex Analyst via Snowflake REST API using username/password auth."""
    try:
        account = SNOWFLAKE_ACCOUNT.replace("_", "-").lower()

        # Step 1: Get a Bearer token via Snowflake login endpoint
        login_url = f"https://{account}.snowflakecomputing.com/session/v1/login-request"
        login_payload = {
            "data": {
                "LOGIN_NAME": SNOWFLAKE_USER,
                "PASSWORD": SNOWFLAKE_PASSWORD,
                "ACCOUNT_NAME": SNOWFLAKE_ACCOUNT,
            }
        }
        login_response = requests.post(login_url, json=login_payload, timeout=15)

        if login_response.status_code != 200:
            return {"success": False, "error": f"Auth failed: {login_response.text}"}

        token = login_response.json().get("data", {}).get("token")
        if not token:
            return {"success": False, "error": "Could not retrieve session token from Snowflake."}

        # Step 2: Call Cortex Analyst with Bearer token
        url = f"https://{account}.snowflakecomputing.com/api/v2/cortex/analyst/message"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Snowflake-Authorization-Token-Type": "OAUTH"
        }
        payload = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": user_message}]}],
            "semantic_model_file": SEMANTIC_MODEL_PATH,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code < 400:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"API error {response.status_code}: {response.text}"}
    except Exception as e:
        return {"success": False, "error": f"Connection error: {str(e)}"}


def run_sql(sql: str) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql(sql, conn)


def render_analyst_response(response_data: dict):
    for block in response_data.get("message", {}).get("content", []):
        block_type = block.get("type")
        if block_type == "text":
            st.markdown(block["text"])
        elif block_type == "sql":
            sql = block["statement"]
            with st.expander("🔍 View generated SQL", expanded=False):
                st.code(sql, language="sql")
            with st.spinner("Running query…"):
                try:
                    df = run_sql(sql)
                    st.success(f"✅ {len(df):,} row(s) returned")
                    st.dataframe(df, use_container_width=True)
                    num_cols  = df.select_dtypes(include="number").columns.tolist()
                    str_cols  = df.select_dtypes(include="object").columns.tolist()
                    date_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
                    if str_cols and num_cols and len(df) <= 50:
                        with st.expander("📊 Chart", expanded=True):
                            fig = px.bar(df, x=str_cols[0], y=num_cols[0],
                                         color_discrete_sequence=["#D32F2F"])
                            st.plotly_chart(fig, use_container_width=True)
                    elif date_cols and num_cols:
                        with st.expander("📈 Trend", expanded=True):
                            fig = px.line(df, x=date_cols[0], y=num_cols[0],
                                          markers=True, color_discrete_sequence=["#FF4500"])
                            st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"SQL error: {e}")
        elif block_type == "suggestions":
            st.markdown("**💡 You might also ask:**")
            for s in block.get("suggestions", []):
                if st.button(f"› {s}", key=f"sug_{s[:40]}"):
                    handle_cortex_input(s)
        elif block_type == "message":
            st.info(block.get("text", ""))


def handle_cortex_input(user_input: str):
    st.session_state.cortex_messages.append({"role": "user", "content": user_input})
    with st.spinner("Thinking…"):
        result = call_cortex_analyst(user_input)
    if result["success"]:
        st.session_state.cortex_messages.append(
            {"role": "assistant", "content": result["data"], "type": "analyst_response"})
    else:
        st.session_state.cortex_messages.append(
            {"role": "assistant", "content": result["error"], "type": "error"})


def cortex_analyst_page():
    if "cortex_messages" not in st.session_state:
        st.session_state.cortex_messages = []

    col_left, col_right = st.columns([4, 1])
    with col_left:
        if st.button("⬅ Back to Dashboard", key="back_cortex"):
            st.session_state.page = "home"
            st.rerun()
    with col_right:
        if st.button("🗑️ Clear Chat", key="clear_cortex"):
            st.session_state.cortex_messages = []
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("🧠 AI Analyst")
    st.caption("Ask questions about your orders data in plain English.")

    st.markdown("**💡 Try asking:**")
    sample_questions = [
        "What is the total net revenue?",
        "Which merchant has the highest cancellation rate?",
        "Show daily order volume for January 2023",
        "What is the average NPS by merchant?",
        "Which merchants have the longest delivery times?",
    ]
    cols = st.columns(len(sample_questions))
    for i, q in enumerate(sample_questions):
        with cols[i]:
            if st.button(q, key=f"sample_{i}"):
                handle_cortex_input(q)
                st.rerun()

    st.markdown("---")

    for msg in st.session_state.cortex_messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            elif msg.get("type") == "analyst_response":
                render_analyst_response(msg["content"])
            elif msg.get("type") == "error":
                st.error(msg["content"])

    if user_input := st.chat_input("Ask a question about your orders data…"):
        handle_cortex_input(user_input)
        st.rerun()


# -------------------------
# HOME PAGE
# -------------------------
if st.session_state.page == "home":

    st.markdown('<div class="center-title">Zipline Sales Dashboard</div><br>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="kpi-card"><div class="kpi-title">Total Net Revenue</div><div class="kpi-value">${total_net_revenue}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card"><div class="kpi-title">Total Orders</div><div class="kpi-value">{total_orders}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card"><div class="kpi-title">Total Deliveries</div><div class="kpi-value">{total_success}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi-card"><div class="kpi-title">Total Cancellations</div><div class="kpi-value">{total_cancellations}</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    left_col, right_col = st.columns([1.2, 1.3])

    with left_col:
        pad_col, content_col = st.columns([0.25, 0.75])
        with content_col:
            st.subheader("Navigate to Dashboard Sections")
            if st.button("Customer Experience", key="nav_cx"):
                st.session_state.page = "cx"
                st.rerun()
            if st.button("Customer Growth", key="nav_growth"):
                st.session_state.page = "growth"
                st.rerun()
            if st.button("Financial Results", key="nav_financial"):
                st.session_state.page = "financial"
                st.rerun()
            if st.button("Merchant Performance", key="nav_merchant"):
                st.session_state.page = "merchant"
                st.rerun()
            if st.button("🧠 AI Analyst", key="nav_cortex"):
                st.session_state.page = "cortex"
                st.rerun()

    with right_col:
        img_left, img_center, img_right = st.columns([0.10, 0.95, 0.10])
        with img_center:
            st.image("Image.png", use_container_width=True)

elif st.session_state.page == "cx":
    customer_experience_page()
elif st.session_state.page == "growth":
    customer_growth_page()
elif st.session_state.page == "financial":
    financial_results_page()
elif st.session_state.page == "merchant":
    merchant_performance_page()
elif st.session_state.page == "cortex":
    cortex_analyst_page()
