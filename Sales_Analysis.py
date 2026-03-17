
import streamlit as st
import pandas as pd
import plotly.express as px

# -------------------------
# PAGE CONFIG
# -------------------------
st.set_page_config(page_title="Zipline Sales Dashboard", layout="wide")

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

.kpi-title{
    font-size:18px;
    opacity:0.9;
}

.kpi-value{
    font-size:40px;
    font-weight:bold;
}

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
# LOAD DATA
# -------------------------
orders = pd.read_csv("Mock_orders_data.csv")
orders['net_revenue'] = round((orders['subtotal'] * orders['Commission Rate']) + orders['fees'] - orders['promotion'], 2)
orders['order datetime'] = pd.to_datetime(orders['order datetime'])
orders['delivery datetime'] = pd.to_datetime(orders['delivery datetime'])
orders['delivery_date'] = orders['order datetime'].dt.date
orders['delivery_minutes'] = ((orders['delivery datetime'] - orders['order datetime']).dt.total_seconds() / 60).round(2)

# -------------------------
# KPI VALUES
# -------------------------
total_net_revenue = orders['net_revenue'].sum().round(2)
total_orders = orders['Order ID'].nunique()
total_success = len(orders[orders['Order Status'] == "Successful"])
total_cancellations = total_orders - total_success

# -------------------------
# SESSION STATE
# -------------------------
if "page" not in st.session_state:
    st.session_state.page = "home"

# -------------------------
# CUSTOMER EXPERIENCE DASHBOARD
# -------------------------
def customer_experience_page():
    col_left, col_right = st.columns([4, 1])

    with col_left:
        if st.button("⬅ Back to Dashboard", key="back_cx"):
            st.session_state.page = "home"
            st.rerun()

    with col_right:
        st.markdown(
            '<p style="color:#D32F2F; font-weight:bold; margin-bottom:5px;">Select Date Range</p>',
            unsafe_allow_html=True
        )
        start_date, end_date = st.date_input(
            "",
            [orders['order datetime'].min().date(), orders['order datetime'].max().date()],
            key="date_cx"
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("Customer Experience Dashboard")

    filtered_orders = orders[
        (orders['order datetime'].dt.date >= start_date) &
        (orders['order datetime'].dt.date <= end_date)
    ].copy()

    avg_delivery = filtered_orders['delivery_minutes'].mean().round(2)
    avg_nps = filtered_orders['NPS'].mean().round(2)
    avg_attempts = filtered_orders['Delivery Attempts'].median()
    cancelled = len(filtered_orders[filtered_orders['Order Status'] != "Successful"])
    cancel_rate = round(cancelled / len(filtered_orders), 3) if len(filtered_orders) > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="kpi-card"><div class="kpi-title">Avg Delivery Time</div><div class="kpi-value">{avg_delivery}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card"><div class="kpi-title">Avg NPS</div><div class="kpi-value">{avg_nps}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card"><div class="kpi-title">Avg Delivery Attempts</div><div class="kpi-value">{avg_attempts}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi-card"><div class="kpi-title">Cancellation Rate</div><div class="kpi-value">{cancel_rate*100:.1f}%</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    delivery_trend = filtered_orders.groupby('delivery_date')['delivery_minutes'].mean().reset_index()
    fig1 = px.line(
        delivery_trend,
        x='delivery_date',
        y='delivery_minutes',
        title='Trend of Average Delivery Time per Day',
        markers=True,
        color_discrete_sequence=['#FF4500'],
        hover_data={'delivery_date': True, 'delivery_minutes': ':.2f'}
    )
    fig1.update_layout(
        xaxis_title='Date',
        yaxis_title='Average Delivery Time (minutes)',
        xaxis=dict(tickformat="%b %d", tickangle=45)
    )
    st.plotly_chart(fig1, use_container_width=True)

    filtered_orders['order_hour'] = filtered_orders['order datetime'].dt.hour
    fig2 = px.histogram(
        filtered_orders,
        x='order_hour',
        nbins=24,
        title='Order Time Distribution by Hour',
        labels={'order_hour': 'Hour of Day', 'count': 'Order Count'},
        color_discrete_sequence=['#FF4500']
    )
    fig2.update_layout(
        xaxis_title='Hour of Day',
        yaxis_title='Order Count',
        xaxis=dict(tickmode='linear', tick0=0, dtick=1)
    )

    cancellation_counts = filtered_orders['Cancellation reason'].dropna().value_counts().reset_index()
    cancellation_counts.columns = ['Cancellation Reason', 'Count']

    col1, col2 = st.columns(2)
    col1.plotly_chart(fig2, use_container_width=True)

    if len(cancellation_counts) > 0:
        colors = ['#FF9C00', '#FE8800', '#FF5503', '#CE0A18', '#E12426']
        fig_pie = px.pie(
            cancellation_counts,
            names='Cancellation Reason',
            values='Count',
            color='Cancellation Reason',
            color_discrete_sequence=colors,
            title='Cancellation Reasons Distribution'
        )
        fig_pie.update_traces(textinfo='percent', marker=dict(line=dict(color='white', width=2)))
        fig_pie.update_layout(template='plotly_white')
        col2.plotly_chart(fig_pie, use_container_width=True)
    else:
        col2.info("No cancellation reasons available for the selected date range.")

# -------------------------
# CUSTOMER GROWTH DASHBOARD
# -------------------------
def customer_growth_page():
    col_left, col_right = st.columns([4, 1])

    with col_left:
        if st.button("⬅ Back to Dashboard", key="back_growth"):
            st.session_state.page = "home"
            st.rerun()

    with col_right:
        st.markdown(
            '<p style="color:#D32F2F; font-weight:bold; margin-bottom:5px;">Select Date Range</p>',
            unsafe_allow_html=True
        )
        start_date, end_date = st.date_input(
            "",
            [orders['order datetime'].min().date(), orders['order datetime'].max().date()],
            key="date_growth"
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("Customer Growth Dashboard")

    filtered_orders = orders[
        (orders['order datetime'].dt.date >= start_date) &
        (orders['order datetime'].dt.date <= end_date)
    ].copy()

    total_customers = filtered_orders['User ID'].nunique()
    avg_orders_per_customer = round(len(filtered_orders) / total_customers, 2) if total_customers > 0 else 0
    orders_per_customer = filtered_orders.groupby('User ID').size()
    repeat_customers = (orders_per_customer > 1).sum()
    repeat_purchase_rate = round((repeat_customers / total_customers) * 100, 2) if total_customers > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="kpi-card"><div class="kpi-title">Total Customers</div><div class="kpi-value">{total_customers}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card"><div class="kpi-title">Avg Orders per Customer</div><div class="kpi-value">{avg_orders_per_customer}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card"><div class="kpi-title">Repeat Purchase Rate</div><div class="kpi-value">{repeat_purchase_rate}%</div></div>', unsafe_allow_html=True)

    filtered_orders['order_week'] = filtered_orders['order datetime'].dt.to_period('W').apply(lambda r: r.start_time)
    wau = filtered_orders.groupby('order_week')['User ID'].nunique().reset_index(name='weekly_active_users')
    wau['WoW_growth_rate'] = wau['weekly_active_users'].pct_change() * 100
    growth_vis = wau[wau['WoW_growth_rate'].notna()].copy()

    fig1 = px.line(
        wau,
        x='order_week',
        y='weekly_active_users',
        title='Weekly Active Users',
        markers=True,
        color_discrete_sequence=['#FF4500']
    )
    fig1.update_layout(xaxis_title='Week', yaxis_title='Weekly Active Users')

    fig2 = px.bar(
        growth_vis,
        x='order_week',
        y='WoW_growth_rate',
        title='Week-over-Week Growth Rate (%)',
        color_discrete_sequence=['#FF4500']
    )
    fig2.update_layout(xaxis_title='Week', yaxis_title='WoW Growth Rate (%)')

    st.plotly_chart(fig1, use_container_width=True)
    st.plotly_chart(fig2, use_container_width=True)

# -------------------------
# FINANCIAL RESULTS DASHBOARD
# -------------------------
def financial_results_page():
    col_left, col_right = st.columns([4, 1])

    with col_left:
        if st.button("⬅ Back to Dashboard", key="back_financial"):
            st.session_state.page = "home"
            st.rerun()

    with col_right:
        st.markdown(
            '<p style="color:#D32F2F; font-weight:bold; margin-bottom:5px;">Select Date Range</p>',
            unsafe_allow_html=True
        )
        start_date, end_date = st.date_input(
            "",
            [orders['order datetime'].min().date(), orders['order datetime'].max().date()],
            key="date_financial"
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("Financial Results Dashboard")

    filtered_orders = orders[
        (orders['order datetime'].dt.date >= start_date) &
        (orders['order datetime'].dt.date <= end_date)
    ].copy()

    total_net_revenue = filtered_orders['net_revenue'].sum().round(2)
    total_orders = filtered_orders['Order ID'].nunique()
    total_customers = filtered_orders['User ID'].nunique()
    aov = round(total_net_revenue / total_orders, 2) if total_orders > 0 else 0
    revenue_per_customer = round(total_net_revenue / total_customers, 2) if total_customers > 0 else 0
    promotion_rate = round(filtered_orders['promotion'].sum() / filtered_orders['subtotal'].sum(), 2) if filtered_orders['subtotal'].sum() > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="kpi-card"><div class="kpi-title">Total Net Revenue</div><div class="kpi-value">${total_net_revenue}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card"><div class="kpi-title">Average Order Value</div><div class="kpi-value">${aov}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card"><div class="kpi-title">Revenue Per Customer</div><div class="kpi-value">${revenue_per_customer}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="kpi-card"><div class="kpi-title">Promotion Rate</div><div class="kpi-value">{promotion_rate*100:.1f}%</div></div>', unsafe_allow_html=True)

    filtered_orders['order_date'] = filtered_orders['order datetime'].dt.date
    daily_revenue = filtered_orders.groupby('order_date')['net_revenue'].sum().reset_index()
    fig1 = px.line(
        daily_revenue,
        x='order_date',
        y='net_revenue',
        title='Daily Revenue Trend',
        markers=True,
        color_discrete_sequence=['#FF4500']
    )
    fig1.update_layout(xaxis_title='Date', yaxis_title='Revenue ($)')
    st.plotly_chart(fig1, use_container_width=True)

    filtered_orders['promo_flag'] = filtered_orders['promotion'].apply(lambda x: 'With Promo' if x > 0 else 'No Promo')
    promo_summary = filtered_orders.groupby('promo_flag').agg(
        total_orders=('Order ID', 'nunique'),
        total_revenue=('net_revenue', 'sum')
    ).reset_index()

    promo_melt = promo_summary.melt(
        id_vars='promo_flag',
        value_vars=['total_orders', 'total_revenue'],
        var_name='metric',
        value_name='value'
    )

    red_shades = ['#FF9C9C', '#FF3333']
    fig2 = px.bar(
        promo_melt,
        x='metric',
        y='value',
        color='promo_flag',
        color_discrete_sequence=red_shades,
        barmode='group',
        title='Orders and Revenue: Promo vs No Promo',
        labels={'metric': 'Metric', 'value': 'Value', 'promo_flag': 'Promotion Type'}
    )
    st.plotly_chart(fig2, use_container_width=True)

# -------------------------
# MERCHANT PERFORMANCE PAGE
# -------------------------
def merchant_performance_page():
    col_left, col_right = st.columns([4, 1])

    with col_left:
        if st.button("⬅ Back to Dashboard", key="back_merchant"):
            st.session_state.page = "home"
            st.rerun()

    with col_right:
        st.markdown(
            '<p style="color:#D32F2F; font-weight:bold; margin-bottom:5px;">Select Date Range</p>',
            unsafe_allow_html=True
        )
        start_date, end_date = st.date_input(
            "",
            [orders['order datetime'].min().date(), orders['order datetime'].max().date()],
            key="date_merchant"
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("Merchant Performance Dashboard")

    # -------------------------
    # Merchant Selection
    # -------------------------
    merchants = sorted(orders['Merchant'].dropna().unique().tolist())

    if "selected_merchants" not in st.session_state:
        st.session_state.selected_merchants = merchants

    spacer, b1, b2 = st.columns([6, 1, 1])

    with b1:
        if st.button("Select All", key="select_all_merchants"):
            st.session_state.selected_merchants = merchants
            st.rerun()

    with b2:
        if st.button("Clear All", key="clear_all_merchants"):
            st.session_state.selected_merchants = []
            st.rerun()

    selected_merchants = st.multiselect(
        "Select Merchant(s):",
        options=merchants,
        default=st.session_state.selected_merchants,
        key="merchant_multiselect"
    )

    st.session_state.selected_merchants = selected_merchants

    # -------------------------
    # Filter Data
    # -------------------------
    filtered_orders = orders[
        (orders['Merchant'].isin(selected_merchants)) &
        (orders['order datetime'].dt.date >= start_date) &
        (orders['order datetime'].dt.date <= end_date)
    ].copy()

    if filtered_orders.empty:
        st.warning("No data available for the selected merchants and date range.")
        return

    # -------------------------
    # Aggregation
    # -------------------------
    def cancellation_rate(x):
        return (x != 'Successful').mean()

    report_card = filtered_orders.groupby('Merchant').agg(
        orders_per_merchant=('Order ID', 'count'),
        net_revenue_per_merchant=('net_revenue', 'sum'),
        avg_delivery_time_per_merchant=('delivery_minutes', 'mean'),
        cancellation_rate_per_merchant=('Order Status', cancellation_rate),
        avg_NPS_per_merchant=('NPS', 'mean')
    ).reset_index()

    report_card[['net_revenue_per_merchant',
                 'avg_delivery_time_per_merchant',
                 'cancellation_rate_per_merchant',
                 'avg_NPS_per_merchant']] = report_card[[
                     'net_revenue_per_merchant',
                     'avg_delivery_time_per_merchant',
                     'cancellation_rate_per_merchant',
                     'avg_NPS_per_merchant'
                 ]].round(2)

    report_card.rename(columns={
        'orders_per_merchant': 'Orders per Merchant',
        'net_revenue_per_merchant': 'Net Revenue per Merchant',
        'avg_delivery_time_per_merchant': 'Avg Delivery Time',
        'cancellation_rate_per_merchant': 'Cancellation Rate',
        'avg_NPS_per_merchant': 'Avg NPS'
    }, inplace=True)

    # -------------------------
    # SCATTER PLOT ⭐
    # -------------------------
    st.subheader("Merchant Performance: Delivery Time vs NPS")

    fig_scatter = px.scatter(
        report_card,
        x='Avg Delivery Time',
        y='Avg NPS',
        size='Orders per Merchant',
        color='Merchant',
        hover_name='Merchant',
        title='Delivery Time vs Customer Satisfaction by Merchant'
    )

    # Add quadrant reference lines
    avg_delivery = report_card['Avg Delivery Time'].mean()
    avg_nps = report_card['Avg NPS'].mean()

    fig_scatter.add_vline(x=avg_delivery, line_dash="dash", line_color="red")
    fig_scatter.add_hline(y=avg_nps, line_dash="dash", line_color="red")

    fig_scatter.update_layout(
        xaxis_title='Average Delivery Time (minutes)',
        yaxis_title='Average NPS',
        legend_title='Merchant'
    )

    st.plotly_chart(fig_scatter, use_container_width=True)

    # -------------------------
    # TABLE
    # -------------------------
    st.subheader("Merchant Performance Table")

    st.dataframe(
        report_card.style
            .format({
                "Net Revenue per Merchant": "{:.2f}",
                "Avg Delivery Time": "{:.2f}",
                "Cancellation Rate": "{:.2f}",
                "Avg NPS": "{:.2f}"
            })
            .set_table_styles(
                [{'selector': 'th',
                  'props': [('border', '2px solid black'),
                            ('background-color', '#D32F2F'),
                            ('color', 'white')]}]
            ),
        use_container_width=True
    )
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

    # Main layout
    left_col, right_col = st.columns([1.2, 1.3])

    with left_col:
        # inner columns to push content right
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

    with right_col:
        img_left, img_center, img_right = st.columns([0.10, 0.95, 0.10])  # controls size
    
        with img_center:
            st.markdown("<div style='margin-top:-10px;'></div>", unsafe_allow_html=True)
            st.image("Image.png", use_container_width=True)

elif st.session_state.page == "cx":
    customer_experience_page()

elif st.session_state.page == "growth":
    customer_growth_page()

elif st.session_state.page == "financial":
    financial_results_page()

elif st.session_state.page == "merchant":
    merchant_performance_page()
