import streamlit as st
import pandas as pd
import numpy as np
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# === CONFIGURATION (WORKS LOCALLY AND ON CLOUD) ===
# Automatically detects where the script is running
try:
    BASE_DIR = Path(__file__).parent
except:
    BASE_DIR = Path.cwd()

DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backups"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

# File paths
DATA_FILE = DATA_DIR / "inventory_transactions.csv"
ITEMS_FILE = DATA_DIR / "master_items.csv"
PARTIES_FILE = DATA_DIR / "master_parties.csv"

# App settings
PAGE_SIZE = 20
LOW_STOCK_THRESHOLD = 10
MAX_BACKUPS = 10

# Transaction type configuration
TRANSACTION_TYPES = {
    "Purchase": {"affects_stock": 1, "affects_balance": 1, "icon": "📥"},
    "Sale": {"affects_stock": -1, "affects_balance": -1, "icon": "📤"},
    "Receipt": {"affects_stock": 0, "affects_balance": -1, "icon": "💵"},
    "Payment": {"affects_stock": 0, "affects_balance": 1, "icon": "💸"},
    "Return In": {"affects_stock": 1, "affects_balance": -1, "icon": "↩️"},
    "Return Out": {"affects_stock": -1, "affects_balance": 1, "icon": "↪️"},
}

# === PAGE CONFIG ===
st.set_page_config(
    page_title="Business Inventory Tracker",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === CUSTOM CSS FOR BETTER VISIBILITY ===
st.markdown("""
<style>
    /* Fix metric card visibility */
    [data-testid="stMetricValue"] {
        color: #1f1f1f !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }
    
    [data-testid="stMetricLabel"] {
        color: #1f1f1f !important;
        font-weight: 600 !important;
    }
    
    [data-testid="stMetricDelta"] {
        color: #1f1f1f !important;
    }
    
    /* Metric container styling */
    [data-testid="metric-container"] {
        background-color: #e8f4f8 !important;
        border: 2px solid #2196F3 !important;
        border-radius: 10px !important;
        padding: 15px !important;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1) !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #f5f5f5 !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #1f1f1f !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        color: #1f1f1f !important;
    }
    
    /* Custom metric boxes */
    .metric-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        color: white !important;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        margin: 5px;
    }
    
    .metric-box h3 {
        color: white !important;
        margin: 0;
        font-size: 1rem;
        opacity: 0.9;
    }
    
    .metric-box h1 {
        color: white !important;
        margin: 10px 0 0 0;
        font-size: 2rem;
    }
    
    .metric-green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%) !important; }
    .metric-red { background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%) !important; }
    .metric-blue { background: linear-gradient(135deg, #2196F3 0%, #21CBF3 100%) !important; }
    .metric-purple { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important; }
    .metric-orange { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important; }
    
    /* Party balance boxes */
    .balance-owe {
        background-color: #ffcdd2 !important;
        border-left: 5px solid #f44336 !important;
        padding: 15px !important;
        margin: 10px 0 !important;
        border-radius: 5px !important;
        color: #b71c1c !important;
    }
    
    .balance-receive {
        background-color: #c8e6c9 !important;
        border-left: 5px solid #4caf50 !important;
        padding: 15px !important;
        margin: 10px 0 !important;
        border-radius: 5px !important;
        color: #1b5e20 !important;
    }
    
    .balance-settled {
        background-color: #e0e0e0 !important;
        border-left: 5px solid #9e9e9e !important;
        padding: 15px !important;
        margin: 10px 0 !important;
        border-radius: 5px !important;
        color: #424242 !important;
    }
    
    /* Table styling */
    .dataframe { color: #1f1f1f !important; }
    
    /* Fix expander content */
    .streamlit-expanderContent {
        background-color: #fafafa !important;
        color: #1f1f1f !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 { color: #1f1f1f !important; }
    
    /* General text */
    p, span, div { color: #1f1f1f; }
</style>
""", unsafe_allow_html=True)


# === UTILITY FUNCTIONS ===
def create_backup(filepath):
    """Create a backup of the file before saving"""
    try:
        filepath = Path(filepath)
        if filepath.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{filepath.stem}_backup_{timestamp}{filepath.suffix}"
            backup_path = BACKUP_DIR / backup_name
            shutil.copy(filepath, backup_path)
            
            backups = sorted(BACKUP_DIR.glob(f"{filepath.stem}_backup_*"), reverse=True)
            for old_backup in backups[MAX_BACKUPS:]:
                old_backup.unlink()
    except Exception as e:
        pass  # Silent fail for cloud compatibility


def sanitize_input(text):
    """Sanitize user input"""
    if text is None:
        return ""
    text = str(text).strip()[:500]
    dangerous_chars = ['<', '>', '{', '}', '|', '\\', '^', '`']
    for char in dangerous_chars:
        text = text.replace(char, '')
    return text


def safe_format_date(date_val, format_str='%d/%m/%Y'):
    """Safely format date value"""
    if pd.isna(date_val):
        return "Invalid Date"
    try:
        if isinstance(date_val, str):
            date_val = pd.to_datetime(date_val)
        return date_val.strftime(format_str)
    except:
        return "Invalid Date"


def safe_desc_preview(desc, max_length=50):
    """Safely create description preview"""
    desc = str(desc) if not pd.isna(desc) else ""
    return desc[:max_length] + "..." if len(desc) > max_length else desc


def calculate_quantity(qty_raw, trans_type):
    """Calculate signed quantity based on transaction type"""
    qty_raw = abs(qty_raw)
    multiplier = TRANSACTION_TYPES.get(trans_type, {}).get("affects_stock", 1)
    return qty_raw * multiplier


def calculate_balance_effect(amount, trans_type):
    """Calculate balance effect based on transaction type"""
    multiplier = TRANSACTION_TYPES.get(trans_type, {}).get("affects_balance", 1)
    return abs(amount) * multiplier


def display_metric_card(title, value, color="blue"):
    """Display a custom colored metric card"""
    color_class = f"metric-{color}"
    st.markdown(f"""
        <div class="metric-box {color_class}">
            <h3>{title}</h3>
            <h1>{value}</h1>
        </div>
    """, unsafe_allow_html=True)


def display_balance_card(party_name, amount, balance_type):
    """Display a balance card with proper styling"""
    if balance_type == "owe":
        st.markdown(f"""
            <div class="balance-owe">
                <strong>🔴 {party_name}</strong><br>
                You Owe: <strong>₹{amount:,.2f}</strong>
            </div>
        """, unsafe_allow_html=True)
    elif balance_type == "receive":
        st.markdown(f"""
            <div class="balance-receive">
                <strong>🟢 {party_name}</strong><br>
                They Owe You: <strong>₹{amount:,.2f}</strong>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
            <div class="balance-settled">
                <strong>⚪ {party_name}</strong><br>
                Settled: <strong>₹0.00</strong>
            </div>
        """, unsafe_allow_html=True)


# === DATA MANAGEMENT ===
def load_transactions():
    """Load transactions from CSV file"""
    if DATA_FILE.exists():
        try:
            df = pd.read_csv(DATA_FILE)
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
            df['Price per Unit'] = pd.to_numeric(df['Price per Unit'], errors='coerce').fillna(0)
            df['Total Amount'] = pd.to_numeric(df['Total Amount'], errors='coerce').fillna(0)
            
            if 'Description' not in df.columns:
                df['Description'] = ''
            df['Description'] = df['Description'].fillna('')
            
            if 'Balance Effect' not in df.columns:
                df['Balance Effect'] = df.apply(
                    lambda row: calculate_balance_effect(row['Total Amount'], row['Type']), axis=1
                )
            
            df = df.reset_index(drop=True)
            return df
        except Exception as e:
            st.error(f"Error loading transactions: {e}")
            return create_empty_dataframe()
    else:
        return create_empty_dataframe()


def create_empty_dataframe():
    """Create empty dataframe with proper columns"""
    return pd.DataFrame(columns=[
        'Date', 'Party Name', 'Type', 'Item Name', 
        'Quantity', 'Price per Unit', 'Total Amount', 
        'Balance Effect', 'Description'
    ])


def save_transactions(df):
    """Save transactions to CSV with backup"""
    try:
        create_backup(DATA_FILE)
        df = df.reset_index(drop=True)
        df.to_csv(DATA_FILE, index=False)
        st.session_state.df = df.copy()
        return True
    except Exception as e:
        st.error(f"Error saving transactions: {e}")
        return False


def load_master(file_path, column_name):
    """Load master data from CSV"""
    file_path = Path(file_path)
    if file_path.exists():
        try:
            data = pd.read_csv(file_path)[column_name].dropna().unique().tolist()
            return sorted([str(item).strip() for item in data if str(item).strip()])
        except Exception as e:
            return []
    return []


def save_master(file_path, data, column_name):
    """Save master data to CSV"""
    try:
        file_path = Path(file_path)
        create_backup(file_path)
        unique_data = sorted(list(set([str(item).strip() for item in data if str(item).strip()])))
        pd.DataFrame({column_name: unique_data}).to_csv(file_path, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving {column_name}: {e}")
        return False


# === SESSION STATE INITIALIZATION ===
def init_session_state():
    """Initialize all session state variables"""
    if 'df' not in st.session_state:
        st.session_state.df = load_transactions()
    if 'master_items' not in st.session_state:
        st.session_state.master_items = load_master(ITEMS_FILE, "Item Name")
    if 'master_parties' not in st.session_state:
        st.session_state.master_parties = load_master(PARTIES_FILE, "Party Name")
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1
    if 'edit_idx' not in st.session_state:
        st.session_state.edit_idx = None
    if 'show_delete_confirm' not in st.session_state:
        st.session_state.show_delete_confirm = None


def refresh_data():
    """Refresh all data from files"""
    st.session_state.df = load_transactions()
    st.session_state.master_items = load_master(ITEMS_FILE, "Item Name")
    st.session_state.master_parties = load_master(PARTIES_FILE, "Party Name")


# Initialize session state
init_session_state()

# Get data from session state
df = st.session_state.df
master_items = st.session_state.master_items
master_parties = st.session_state.master_parties


# === SIDEBAR ===
with st.sidebar:
    st.title("🏪 Inventory Tracker")
    st.markdown("---")
    
    # Show environment info
    st.caption(f"📁 Data: {DATA_DIR}")
    
    # Quick Stats with custom styling
    if not df.empty:
        st.subheader("📊 Quick Stats")
        
        st.markdown(f"""
            <div style="background-color: #e3f2fd; padding: 15px; border-radius: 10px; margin: 5px 0; border-left: 4px solid #2196F3;">
                <strong style="color: #1565c0;">📝 Total Transactions</strong><br>
                <span style="font-size: 1.5rem; font-weight: bold; color: #0d47a1;">{len(df)}</span>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 10px; margin: 5px 0; border-left: 4px solid #4caf50;">
                <strong style="color: #2e7d32;">📦 Unique Items</strong><br>
                <span style="font-size: 1.5rem; font-weight: bold; color: #1b5e20;">{df['Item Name'].nunique()}</span>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div style="background-color: #fff3e0; padding: 15px; border-radius: 10px; margin: 5px 0; border-left: 4px solid #ff9800;">
                <strong style="color: #e65100;">👥 Unique Parties</strong><br>
                <span style="font-size: 1.5rem; font-weight: bold; color: #bf360c;">{df['Party Name'].nunique()}</span>
            </div>
        """, unsafe_allow_html=True)
        
        valid_dates = df['Date'].dropna()
        if not valid_dates.empty:
            st.caption(f"📅 Data: {safe_format_date(valid_dates.min())} to {safe_format_date(valid_dates.max())}")
    
    st.markdown("---")
    
    # Data Management
    st.subheader("🔧 Data Management")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        refresh_data()
        st.success("Data refreshed!")
        st.rerun()
    
    if not df.empty:
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export All Data",
            data=csv_data,
            file_name=f"inventory_backup_{datetime.today().strftime('%Y%m%d')}.csv",
            mime='text/csv',
            use_container_width=True
        )
    
    st.markdown("---")
    
    # Import data - Critical for cloud
    st.subheader("📤 Import/Restore Data")
    st.caption("⚠️ On Cloud: Data resets on reboot. Use Export/Import to backup!")
    
    uploaded_file = st.file_uploader("Upload CSV", type=['csv'], key="main_upload")
    if uploaded_file is not None:
        try:
            imported_df = pd.read_csv(uploaded_file)
            required_cols = ['Date', 'Party Name', 'Type', 'Item Name', 'Quantity', 'Price per Unit', 'Total Amount']
            if all(col in imported_df.columns for col in required_cols):
                st.success(f"Found {len(imported_df)} transactions")
                if st.button("✅ Confirm Import", use_container_width=True):
                    imported_df['Date'] = pd.to_datetime(imported_df['Date'], errors='coerce')
                    if 'Description' not in imported_df.columns:
                        imported_df['Description'] = ''
                    if 'Balance Effect' not in imported_df.columns:
                        imported_df['Balance Effect'] = imported_df.apply(
                            lambda row: calculate_balance_effect(row['Total Amount'], row['Type']), axis=1
                        )
                    if save_transactions(imported_df):
                        st.success("Data imported successfully!")
                        refresh_data()
                        st.rerun()
            else:
                missing = [c for c in required_cols if c not in imported_df.columns]
                st.error(f"Missing columns: {missing}")
        except Exception as e:
            st.error(f"Import error: {e}")
    
    st.markdown("---")
    st.caption("v2.0 - Cloud Compatible")


# === MAIN APP LAYOUT ===
st.title("🏪 Business Inventory Tracker")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏠 Dashboard", 
    "📋 Transactions", 
    "➕ Add Transaction", 
    "⚙️ Masters", 
    "💰 Party Balances",
    "📈 Reports"
])


# ==================== TAB 1: DASHBOARD ====================
with tab1:
    st.header("Dashboard Overview")
    
    if df.empty:
        st.info("👋 Welcome! No transactions yet. Add some to see the dashboard!")
        st.markdown("""
        ### Getting Started:
        1. Go to **Masters** tab to add your items and parties
        2. Go to **Add Transaction** tab to record purchases and sales
        3. Come back here to see your business overview!
        
        ### 💡 Tip for Cloud Users:
        - Use **Export All Data** in sidebar to backup your data
        - Use **Import/Restore Data** to restore after app restarts
        """)
    else:
        # Top metrics row with custom cards
        col1, col2, col3, col4 = st.columns(4)
        
        total_items = df['Item Name'].nunique()
        stock_qty = df.groupby('Item Name')['Quantity'].sum()
        total_stock = stock_qty.sum()
        
        last_prices = df[df['Price per Unit'] > 0].groupby('Item Name')['Price per Unit'].last()
        positive_stock = stock_qty[stock_qty > 0]
        stock_value = (positive_stock * last_prices.reindex(positive_stock.index, fill_value=0)).sum()
        
        total_transactions = len(df)
        
        with col1:
            display_metric_card("📦 Unique Items", total_items, "blue")
        
        with col2:
            display_metric_card("📊 Current Stock", f"{int(total_stock):,}", "green")
        
        with col3:
            display_metric_card("💰 Stock Value", f"₹{stock_value:,.0f}", "purple")
        
        with col4:
            display_metric_card("📝 Transactions", total_transactions, "orange")
        
        st.markdown("---")
        
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.subheader("📦 Current Stock by Item")
            stock_summary = stock_qty.reset_index(name='Current Stock')
            stock_summary = stock_summary[stock_summary['Current Stock'] != 0].sort_values(
                'Current Stock', ascending=False
            ).head(15)
            
            if not stock_summary.empty:
                st.bar_chart(stock_summary.set_index('Item Name')['Current Stock'])
            else:
                st.info("No stock data available")
        
        with chart_col2:
            st.subheader("📈 Transaction Trend")
            valid_dates = df.dropna(subset=['Date'])
            if not valid_dates.empty:
                monthly = valid_dates.copy()
                monthly['Month'] = monthly['Date'].dt.to_period('M').astype(str)
                
                stock_types = [t for t, config in TRANSACTION_TYPES.items() if config['affects_stock'] != 0]
                stock_monthly = monthly[monthly['Type'].isin(stock_types)]
                
                if not stock_monthly.empty:
                    flow = stock_monthly.groupby(['Month', 'Type'])['Quantity'].sum().abs().unstack(fill_value=0)
                    st.line_chart(flow)
                else:
                    st.info("No stock movement data")
            else:
                st.info("No dated transactions")
        
        st.markdown("---")
        
        # Low stock alerts
        st.subheader("⚠️ Low Stock Alerts")
        low_stock = stock_summary[
            (stock_summary['Current Stock'] > 0) & 
            (stock_summary['Current Stock'] < LOW_STOCK_THRESHOLD)
        ]
        
        if not low_stock.empty:
            for _, row in low_stock.iterrows():
                st.markdown(f"""
                    <div style="background-color: #fff3e0; padding: 10px 15px; border-radius: 8px; 
                                margin: 5px 0; border-left: 4px solid #ff9800;">
                        <strong style="color: #e65100;">🔔 {row['Item Name']}</strong> - 
                        <span style="color: #bf360c;">Only {int(row['Current Stock'])} units left!</span>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style="background-color: #e8f5e9; padding: 15px; border-radius: 8px; 
                            border-left: 4px solid #4caf50;">
                    <strong style="color: #2e7d32;">✅ All items are adequately stocked</strong>
                </div>
            """, unsafe_allow_html=True)
        
        # Recent transactions
        st.markdown("---")
        st.subheader("🕐 Recent Transactions")
        recent = df.sort_values('Date', ascending=False).head(5)
        
        for _, row in recent.iterrows():
            icon = TRANSACTION_TYPES.get(row['Type'], {}).get('icon', '📝')
            date_str = safe_format_date(row['Date'])
            st.markdown(f"""
                <div style="background-color: #f5f5f5; padding: 10px 15px; border-radius: 8px; 
                            margin: 5px 0; border-left: 4px solid #2196F3;">
                    <span style="color: #1565c0;">{icon} <strong>{date_str}</strong></span> | 
                    <span style="color: #424242;">{row['Party Name']}</span> | 
                    <span style="color: #6a1b9a;"><strong>{row['Type']}</strong></span> | 
                    <span style="color: #00695c;">{row['Item Name']}</span> | 
                    <span style="color: #bf360c;">Qty: {int(abs(row['Quantity']))} @ ₹{row['Price per Unit']:,.2f}</span>
                </div>
            """, unsafe_allow_html=True)


# ==================== TAB 2: TRANSACTIONS ====================
with tab2:
    st.header("All Transactions")
    
    # Search and filters
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([3, 2, 2, 2])
    
    with filter_col1:
        search = st.text_input("🔍 Search (Item / Party / Description)", "", key="trans_search")
    
    with filter_col2:
        type_filter = st.multiselect(
            "Transaction Type",
            options=list(TRANSACTION_TYPES.keys()),
            default=[],
            key="trans_type_filter"
        )
    
    with filter_col3:
        date_range = st.date_input(
            "Date Range",
            value=[],
            key="trans_date_range"
        )
    
    with filter_col4:
        sort_order = st.selectbox(
            "Sort By",
            ["Date (Newest)", "Date (Oldest)", "Amount (High)", "Amount (Low)"],
            key="trans_sort"
        )
    
    # Apply filters
    view_df = df.copy()
    
    if search:
        mask = (
            view_df['Item Name'].str.contains(search, case=False, na=False) |
            view_df['Party Name'].str.contains(search, case=False, na=False) |
            view_df['Description'].str.contains(search, case=False, na=False)
        )
        view_df = view_df[mask]
    
    if type_filter:
        view_df = view_df[view_df['Type'].isin(type_filter)]
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        view_df = view_df[
            (view_df['Date'] >= pd.Timestamp(start_date)) & 
            (view_df['Date'] <= pd.Timestamp(end_date))
        ]
    
    # Apply sorting
    if sort_order == "Date (Newest)":
        view_df = view_df.sort_values('Date', ascending=False)
    elif sort_order == "Date (Oldest)":
        view_df = view_df.sort_values('Date', ascending=True)
    elif sort_order == "Amount (High)":
        view_df = view_df.sort_values('Total Amount', ascending=False, key=abs)
    elif sort_order == "Amount (Low)":
        view_df = view_df.sort_values('Total Amount', ascending=True, key=abs)
    
    view_df = view_df.reset_index(drop=False)
    view_df.rename(columns={'index': 'original_idx'}, inplace=True)
    
    st.markdown(f"**Showing {len(view_df)} transactions**")
    
    if not view_df.empty:
        # Pagination
        total_pages = max(1, (len(view_df) - 1) // PAGE_SIZE + 1)
        
        pag_col1, pag_col2, pag_col3 = st.columns([1, 2, 1])
        with pag_col2:
            page = st.number_input(
                f"Page (1-{total_pages})", 
                min_value=1, 
                max_value=total_pages, 
                value=min(st.session_state.current_page, total_pages),
                key="page_selector"
            )
            st.session_state.current_page = page
        
        start_idx = (page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_df = view_df.iloc[start_idx:end_idx]
        
        # Display transactions
        for _, row in page_df.iterrows():
            original_idx = row['original_idx']
            icon = TRANSACTION_TYPES.get(row['Type'], {}).get('icon', '📝')
            display_date = safe_format_date(row['Date'])
            desc_preview = safe_desc_preview(row['Description'])
            
            with st.container():
                col1, col2, col3 = st.columns([8, 1, 1])
                
                with col1:
                    qty_display = int(abs(row['Quantity']))
                    amount_display = abs(row['Total Amount'])
                    st.markdown(f"""
                        <div style="background-color: #fafafa; padding: 10px 15px; border-radius: 8px; 
                                    margin: 3px 0; border-left: 4px solid #673ab7;">
                            <span style="color: #1565c0;">{icon} <strong>{display_date}</strong></span> | 
                            <span style="color: #424242;">{row['Party Name']}</span> | 
                            <span style="color: #6a1b9a;"><strong>{row['Type']}</strong></span> | 
                            <span style="color: #00695c;">{row['Item Name']}</span> | 
                            <span style="color: #bf360c;">Qty: {qty_display} @ ₹{row['Price per Unit']:,.2f}</span> → 
                            <strong style="color: #1b5e20;">₹{amount_display:,.2f}</strong>
                            {f' | <em style="color: #757575;">{desc_preview}</em>' if desc_preview else ''}
                        </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    if st.button("✏️", key=f"edit_{original_idx}", help="Edit"):
                        st.session_state.edit_idx = original_idx
                        st.rerun()
                
                with col3:
                    if st.button("🗑️", key=f"del_{original_idx}", help="Delete"):
                        st.session_state.show_delete_confirm = original_idx
        
        # Delete confirmation dialog
        if st.session_state.show_delete_confirm is not None:
            del_idx = st.session_state.show_delete_confirm
            st.markdown("""
                <div style="background-color: #fff3e0; padding: 15px; border-radius: 8px; 
                            border: 2px solid #ff9800; margin: 10px 0;">
                    <strong style="color: #e65100;">⚠️ Are you sure you want to delete this transaction?</strong>
                </div>
            """, unsafe_allow_html=True)
            conf_col1, conf_col2, conf_col3 = st.columns([1, 1, 2])
            with conf_col1:
                if st.button("✅ Yes, Delete", type="primary"):
                    df_updated = st.session_state.df.drop(del_idx).reset_index(drop=True)
                    if save_transactions(df_updated):
                        st.session_state.show_delete_confirm = None
                        st.success("Transaction deleted!")
                        st.rerun()
            with conf_col2:
                if st.button("❌ Cancel"):
                    st.session_state.show_delete_confirm = None
                    st.rerun()
        
        # Edit form
        if st.session_state.edit_idx is not None:
            edit_idx = st.session_state.edit_idx
            
            if edit_idx in st.session_state.df.index:
                row = st.session_state.df.loc[edit_idx].copy()
                
                st.markdown("---")
                st.subheader("✏️ Edit Transaction")
                
                with st.form("edit_form"):
                    edit_col1, edit_col2 = st.columns(2)
                    
                    with edit_col1:
                        default_date = row['Date'] if pd.notna(row['Date']) else datetime.today()
                        if isinstance(default_date, pd.Timestamp):
                            default_date = default_date.date()
                        new_date = st.date_input("Date", value=default_date)
                        
                        new_party = st.text_input("Party Name", value=str(row['Party Name']))
                        
                        type_options = list(TRANSACTION_TYPES.keys())
                        current_type_idx = type_options.index(row['Type']) if row['Type'] in type_options else 0
                        new_type = st.selectbox("Type", type_options, index=current_type_idx)
                    
                    with edit_col2:
                        new_item = st.text_input("Item Name", value=str(row['Item Name']))
                        new_qty_raw = st.number_input(
                            "Quantity (absolute)", 
                            value=int(abs(row['Quantity'])), 
                            min_value=1
                        )
                        new_price = st.number_input(
                            "Price per Unit", 
                            value=float(row['Price per Unit']), 
                            min_value=0.0,
                            step=0.5
                        )
                    
                    new_description = st.text_area(
                        "Description", 
                        value=str(row['Description']) if pd.notna(row['Description']) else ""
                    )
                    
                    form_col1, form_col2, form_col3 = st.columns([1, 1, 2])
                    
                    with form_col1:
                        save_btn = st.form_submit_button("💾 Save Changes", type="primary")
                    with form_col2:
                        cancel_btn = st.form_submit_button("❌ Cancel")
                    
                    if save_btn:
                        if not sanitize_input(new_party) or not sanitize_input(new_item):
                            st.error("Party Name and Item Name are required!")
                        else:
                            new_qty = calculate_quantity(new_qty_raw, new_type)
                            new_total = abs(new_qty) * new_price
                            new_balance_effect = calculate_balance_effect(new_total, new_type)
                            
                            st.session_state.df.loc[edit_idx] = [
                                pd.Timestamp(new_date),
                                sanitize_input(new_party),
                                new_type,
                                sanitize_input(new_item),
                                new_qty,
                                new_price,
                                new_total,
                                new_balance_effect,
                                sanitize_input(new_description)
                            ]
                            
                            if save_transactions(st.session_state.df):
                                st.session_state.edit_idx = None
                                st.success("Transaction updated!")
                                st.rerun()
                    
                    if cancel_btn:
                        st.session_state.edit_idx = None
                        st.rerun()
            else:
                st.session_state.edit_idx = None
                st.rerun()
        
        # Export filtered data
        st.markdown("---")
        if not view_df.empty:
            export_df = view_df.drop(columns=['original_idx'])
            csv_export = export_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Filtered Transactions",
                data=csv_export,
                file_name=f"transactions_{datetime.today().strftime('%Y%m%d')}.csv",
                mime='text/csv'
            )
    else:
        st.info("No transactions found matching your filters.")


# ==================== TAB 3: ADD TRANSACTION ====================
with tab3:
    st.header("Add New Transaction")
    
    # Quick add buttons
    st.subheader("Quick Actions")
    quick_col1, quick_col2, quick_col3, quick_col4 = st.columns(4)
    
    with quick_col1:
        if st.button("📥 Quick Purchase", use_container_width=True):
            st.session_state.quick_type = "Purchase"
    with quick_col2:
        if st.button("📤 Quick Sale", use_container_width=True):
            st.session_state.quick_type = "Sale"
    with quick_col3:
        if st.button("💵 Quick Receipt", use_container_width=True):
            st.session_state.quick_type = "Receipt"
    with quick_col4:
        if st.button("💸 Quick Payment", use_container_width=True):
            st.session_state.quick_type = "Payment"
    
    st.markdown("---")
    
    with st.form("add_form", clear_on_submit=True):
        form_col1, form_col2 = st.columns(2)
        
        with form_col1:
            date = st.date_input("📅 Date", value=datetime.today())
            
            party_search = st.text_input("🔍 Search/Type Party Name")
            filtered_parties = [p for p in master_parties if party_search.lower() in p.lower()] if party_search else master_parties
            party_options = ["-- Select or type new --"] + filtered_parties
            selected_party = st.selectbox("👤 Select Party", options=party_options)
            party = party_search.strip() if selected_party == "-- Select or type new --" else selected_party
            
            default_type_idx = 0
            if 'quick_type' in st.session_state:
                quick_type = st.session_state.quick_type
                if quick_type in list(TRANSACTION_TYPES.keys()):
                    default_type_idx = list(TRANSACTION_TYPES.keys()).index(quick_type)
            
            trans_type = st.selectbox(
                "📋 Transaction Type", 
                list(TRANSACTION_TYPES.keys()),
                index=default_type_idx,
                help="Purchase/Return In: Adds to stock | Sale/Return Out: Removes from stock | Receipt/Payment: Only affects balance"
            )
        
        with form_col2:
            item_search = st.text_input("🔍 Search/Type Item Name")
            filtered_items = [i for i in master_items if item_search.lower() in i.lower()] if item_search else master_items
            item_options = ["-- Select or type new --"] + filtered_items
            selected_item = st.selectbox("📦 Select Item", options=item_options)
            item = item_search.strip() if selected_item == "-- Select or type new --" else selected_item
            
            quantity = st.number_input("🔢 Quantity", min_value=1, value=1)
            price = st.number_input("💲 Price per Unit (₹)", min_value=0.0, value=0.0, step=0.5)
        
        description = st.text_area(
            "📝 Description (optional)", 
            placeholder="e.g., Invoice #123, Cash payment, Credit sale, etc."
        )
        
        # Preview
        preview_qty = calculate_quantity(quantity, trans_type)
        preview_total = abs(preview_qty) * price
        preview_balance = calculate_balance_effect(preview_total, trans_type)
        
        st.markdown(f"""
            <div style="background-color: #e3f2fd; padding: 15px; border-radius: 8px; 
                        border: 1px solid #2196F3; margin: 10px 0;">
                <strong style="color: #1565c0;">📋 Preview:</strong><br>
                <span style="color: #424242;">
                    {trans_type} | Stock Effect: <strong>{'+' if preview_qty > 0 else ''}{preview_qty}</strong> | 
                    Amount: <strong>₹{preview_total:,.2f}</strong> | 
                    Balance Effect: <strong>{'+ (You Owe)' if preview_balance > 0 else '- (They Owe)'} ₹{abs(preview_balance):,.2f}</strong>
                </span>
            </div>
        """, unsafe_allow_html=True)
        
        submitted = st.form_submit_button("✅ Add Transaction", type="primary", use_container_width=True)
        
        if submitted:
            party = sanitize_input(party)
            item = sanitize_input(item)
            
            if not party:
                st.error("❌ Party Name is required!")
            elif not item and trans_type not in ["Receipt", "Payment"]:
                st.error("❌ Item Name is required for this transaction type!")
            else:
                if not item and trans_type in ["Receipt", "Payment"]:
                    item = "N/A - Payment Transaction"
                
                qty = calculate_quantity(quantity, trans_type)
                total = abs(qty) * price
                balance_effect = calculate_balance_effect(total, trans_type)
                
                new_row = pd.DataFrame([{
                    'Date': pd.Timestamp(date),
                    'Party Name': party,
                    'Type': trans_type,
                    'Item Name': item,
                    'Quantity': qty,
                    'Price per Unit': price,
                    'Total Amount': total,
                    'Balance Effect': balance_effect,
                    'Description': sanitize_input(description)
                }])
                
                updated_df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                
                if save_transactions(updated_df):
                    if party and party not in master_parties:
                        st.session_state.master_parties.append(party)
                        save_master(PARTIES_FILE, st.session_state.master_parties, "Party Name")
                    
                    if item and item not in master_items and item != "N/A - Payment Transaction":
                        st.session_state.master_items.append(item)
                        save_master(ITEMS_FILE, st.session_state.master_items, "Item Name")
                    
                    if 'quick_type' in st.session_state:
                        del st.session_state.quick_type
                    
                    st.success("✅ Transaction added successfully!")
                    st.balloons()
                    st.rerun()


# ==================== TAB 4: MASTERS ====================
with tab4:
    st.header("Manage Items & Parties")
    
    master_col1, master_col2 = st.columns(2)
    
    with master_col1:
        st.subheader("📦 Items Master")
        
        with st.form("add_item_form"):
            new_item = st.text_input("Add New Item", key="new_item_input")
            add_item_btn = st.form_submit_button("➕ Add Item", use_container_width=True)
            
            if add_item_btn and new_item.strip():
                clean_item = sanitize_input(new_item)
                if clean_item and clean_item not in st.session_state.master_items:
                    st.session_state.master_items.append(clean_item)
                    if save_master(ITEMS_FILE, st.session_state.master_items, "Item Name"):
                        st.success(f"✅ Added: {clean_item}")
                        st.rerun()
                else:
                    st.warning("Item already exists or invalid!")
        
        item_search = st.text_input("🔍 Search Items", key="search_items")
        
        display_items = st.session_state.master_items
        if item_search:
            display_items = [i for i in display_items if item_search.lower() in i.lower()]
        
        st.markdown(f"**Total Items: {len(display_items)}**")
        
        items_container = st.container()
        with items_container:
            for i, item_name in enumerate(sorted(display_items)):
                item_col1, item_col2 = st.columns([5, 1])
                item_col1.markdown(f"""
                    <div style="background-color: #e8f5e9; padding: 8px 12px; border-radius: 5px; margin: 2px 0;">
                        <span style="color: #2e7d32;">📦 {item_name}</span>
                    </div>
                """, unsafe_allow_html=True)
                if item_col2.button("❌", key=f"del_item_{i}_{item_name}"):
                    if item_name in st.session_state.master_items:
                        st.session_state.master_items.remove(item_name)
                        if save_master(ITEMS_FILE, st.session_state.master_items, "Item Name"):
                            st.success(f"Deleted: {item_name}")
                            st.rerun()
    
    with master_col2:
        st.subheader("👥 Parties Master")
        
        with st.form("add_party_form"):
            new_party = st.text_input("Add New Party", key="new_party_input")
            add_party_btn = st.form_submit_button("➕ Add Party", use_container_width=True)
            
            if add_party_btn and new_party.strip():
                clean_party = sanitize_input(new_party)
                if clean_party and clean_party not in st.session_state.master_parties:
                    st.session_state.master_parties.append(clean_party)
                    if save_master(PARTIES_FILE, st.session_state.master_parties, "Party Name"):
                        st.success(f"✅ Added: {clean_party}")
                        st.rerun()
                else:
                    st.warning("Party already exists or invalid!")
        
        party_search = st.text_input("🔍 Search Parties", key="search_parties")
        
        display_parties = st.session_state.master_parties
        if party_search:
            display_parties = [p for p in display_parties if party_search.lower() in p.lower()]
        
        st.markdown(f"**Total Parties: {len(display_parties)}**")
        
        parties_container = st.container()
        with parties_container:
            for i, party_name in enumerate(sorted(display_parties)):
                party_col1, party_col2 = st.columns([5, 1])
                party_col1.markdown(f"""
                    <div style="background-color: #e3f2fd; padding: 8px 12px; border-radius: 5px; margin: 2px 0;">
                        <span style="color: #1565c0;">👤 {party_name}</span>
                    </div>
                """, unsafe_allow_html=True)
                if party_col2.button("❌", key=f"del_party_{i}_{party_name}"):
                    if party_name in st.session_state.master_parties:
                        st.session_state.master_parties.remove(party_name)
                        if save_master(PARTIES_FILE, st.session_state.master_parties, "Party Name"):
                            st.success(f"Deleted: {party_name}")
                            st.rerun()
    
    st.markdown("---")
    st.subheader("🔧 Bulk Operations & CSV Format")
    
    # CSV FORMAT INSTRUCTIONS
    st.markdown("""
        <div style="background-color: #fff8e1; padding: 20px; border-radius: 10px; 
                    border: 2px dashed #ffc107; margin: 15px 0;">
            <h4 style="color: #f57f17; margin-top: 0;">📋 CSV Format Instructions</h4>
            <p style="color: #424242;">Your CSV files should be in the following format:</p>
        </div>
    """, unsafe_allow_html=True)
    
    format_col1, format_col2 = st.columns(2)
    
    with format_col1:
        st.markdown("""
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <strong style="color: #2e7d32;">📦 Items CSV Format:</strong>
                <pre style="background-color: #c8e6c9; padding: 10px; border-radius: 5px; margin-top: 10px; color: #1b5e20;">
Item Name
Rice 25kg
Sugar 10kg
Wheat Flour 5kg
                </pre>
            </div>
        """, unsafe_allow_html=True)
        
        sample_items = pd.DataFrame({"Item Name": ["Rice 25kg", "Sugar 10kg", "Wheat Flour 5kg", "Salt 1kg", "Oil 5L"]})
        st.download_button("📥 Download Sample Items CSV", sample_items.to_csv(index=False).encode('utf-8'), "sample_items.csv", "text/csv", use_container_width=True)
    
    with format_col2:
        st.markdown("""
            <div style="background-color: #e3f2fd; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <strong style="color: #1565c0;">👥 Parties CSV Format:</strong>
                <pre style="background-color: #bbdefb; padding: 10px; border-radius: 5px; margin-top: 10px; color: #0d47a1;">
Party Name
Sharma Traders
ABC Distributors
XYZ Wholesale
                </pre>
            </div>
        """, unsafe_allow_html=True)
        
        sample_parties = pd.DataFrame({"Party Name": ["Sharma Traders", "ABC Distributors", "XYZ Wholesale", "Ramesh Stores"]})
        st.download_button("📥 Download Sample Parties CSV", sample_parties.to_csv(index=False).encode('utf-8'), "sample_parties.csv", "text/csv", use_container_width=True)
    
    st.markdown("---")
    
    # Full Transaction Format
    st.markdown("""
        <div style="background-color: #fce4ec; padding: 20px; border-radius: 10px; margin: 15px 0;">
            <h4 style="color: #c2185b; margin-top: 0;">📊 Full Transaction CSV Format:</h4>
            <pre style="background-color: #f8bbd0; padding: 10px; border-radius: 5px; margin-top: 10px; color: #880e4f; font-size: 0.85rem;">
Date,Party Name,Type,Item Name,Quantity,Price per Unit,Total Amount,Description
2024-01-15,Sharma Traders,Purchase,Rice 25kg,100,1200,120000,Invoice #001
2024-01-16,Ramesh Stores,Sale,Rice 25kg,-50,1350,67500,Cash sale
            </pre>
            <small style="color: #ad1457;">
                <strong>Type values:</strong> Purchase, Sale, Receipt, Payment, Return In, Return Out
            </small>
        </div>
    """, unsafe_allow_html=True)
    
    sample_trans = pd.DataFrame({
        "Date": ["2024-01-15", "2024-01-16", "2024-01-17"],
        "Party Name": ["Sharma Traders", "Ramesh Stores", "Sharma Traders"],
        "Type": ["Purchase", "Sale", "Receipt"],
        "Item Name": ["Rice 25kg", "Rice 25kg", "N/A - Payment"],
        "Quantity": [100, -50, 0],
        "Price per Unit": [1200, 1350, 0],
        "Total Amount": [120000, 67500, 50000],
        "Description": ["Invoice #001", "Cash sale", "Advance payment"]
    })
    st.download_button("📥 Download Sample Transactions CSV", sample_trans.to_csv(index=False).encode('utf-8'), "sample_transactions.csv", "text/csv", use_container_width=True)
    
    st.markdown("---")
    
    bulk_col1, bulk_col2 = st.columns(2)
    
    with bulk_col1:
        st.markdown("**📦 Import Items from CSV**")
        items_file = st.file_uploader("Upload Items CSV", type=['csv'], key="items_upload")
        if items_file:
            try:
                items_df = pd.read_csv(items_file)
                if 'Item Name' in items_df.columns:
                    new_items = items_df['Item Name'].dropna().unique().tolist()
                    st.success(f"Found {len(new_items)} items")
                    if st.button("✅ Import Items", use_container_width=True):
                        st.session_state.master_items = list(set(st.session_state.master_items + new_items))
                        save_master(ITEMS_FILE, st.session_state.master_items, "Item Name")
                        st.success(f"Imported {len(new_items)} items!")
                        st.rerun()
                else:
                    st.error("Column 'Item Name' not found!")
            except Exception as e:
                st.error(f"Error: {e}")
    
    with bulk_col2:
        st.markdown("**👥 Import Parties from CSV**")
        parties_file = st.file_uploader("Upload Parties CSV", type=['csv'], key="parties_upload")
        if parties_file:
            try:
                parties_df = pd.read_csv(parties_file)
                if 'Party Name' in parties_df.columns:
                    new_parties = parties_df['Party Name'].dropna().unique().tolist()
                    st.success(f"Found {len(new_parties)} parties")
                    if st.button("✅ Import Parties", use_container_width=True):
                        st.session_state.master_parties = list(set(st.session_state.master_parties + new_parties))
                        save_master(PARTIES_FILE, st.session_state.master_parties, "Party Name")
                        st.success(f"Imported {len(new_parties)} parties!")
                        st.rerun()
                else:
                    st.error("Column 'Party Name' not found!")
            except Exception as e:
                st.error(f"Error: {e}")


# ==================== TAB 5: PARTY BALANCES ====================
with tab5:
    st.header("💰 Party-wise Payment Summary")
    
    if df.empty:
        st.info("No transactions yet. Add some to see balances.")
    else:
        st.subheader("🔍 Filters")
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        with filter_col1:
            min_date = df['Date'].min()
            default_from = min_date.date() if pd.notna(min_date) else datetime.today().date()
            from_date = st.date_input("From Date", value=default_from, key="balance_from")
        
        with filter_col2:
            max_date = df['Date'].max()
            default_to = max_date.date() if pd.notna(max_date) else datetime.today().date()
            to_date = st.date_input("To Date", value=default_to, key="balance_to")
        
        with filter_col3:
            party_filter = st.multiselect("Select Parties", options=master_parties, default=[], key="balance_parties")
        
        filtered_df = df.copy()
        filtered_df = filtered_df[(filtered_df['Date'] >= pd.Timestamp(from_date)) & (filtered_df['Date'] <= pd.Timestamp(to_date))]
        
        if party_filter:
            filtered_df = filtered_df[filtered_df['Party Name'].isin(party_filter)]
        
        if filtered_df.empty:
            st.warning("No transactions found for the selected filters.")
        else:
            if 'Balance Effect' in filtered_df.columns:
                party_summary = filtered_df.groupby('Party Name')['Balance Effect'].sum().reset_index()
                party_summary.rename(columns={'Balance Effect': 'Net Balance'}, inplace=True)
            else:
                party_summary = filtered_df.groupby('Party Name')['Total Amount'].sum().reset_index()
                party_summary.rename(columns={'Total Amount': 'Net Balance'}, inplace=True)
            
            party_summary['Status'] = party_summary['Net Balance'].apply(
                lambda x: "🟢 They Owe You" if x < 0 else "🔴 You Owe Them" if x > 0 else "⚪ Settled"
            )
            party_summary['Amount'] = party_summary['Net Balance'].abs()
            party_summary = party_summary.sort_values(by='Net Balance', ascending=True)
            
            total_receivable = party_summary[party_summary['Net Balance'] < 0]['Amount'].sum()
            total_payable = party_summary[party_summary['Net Balance'] > 0]['Amount'].sum()
            net_position = total_receivable - total_payable
            
            st.markdown("---")
            
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1:
                display_metric_card("💚 Total Receivable", f"₹{total_receivable:,.0f}", "green")
            with metric_col2:
                display_metric_card("❤️ Total Payable", f"₹{total_payable:,.0f}", "red")
            with metric_col3:
                color = "blue" if net_position >= 0 else "orange"
                display_metric_card("📊 Net Position", f"₹{net_position:,.0f}", color)
            
            st.markdown("---")
            st.subheader("📋 Party-wise Balances")
            
            for _, row in party_summary.iterrows():
                if row['Net Balance'] > 0:
                    display_balance_card(row['Party Name'], row['Amount'], "owe")
                elif row['Net Balance'] < 0:
                    display_balance_card(row['Party Name'], row['Amount'], "receive")
                else:
                    display_balance_card(row['Party Name'], 0, "settled")
            
            st.markdown("---")
            st.subheader("📊 Summary Table")
            display_summary = party_summary[['Party Name', 'Status', 'Amount']].copy()
            display_summary['Amount'] = display_summary['Amount'].apply(lambda x: f"₹{x:,.2f}")
            st.dataframe(display_summary, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("🔎 Detailed Party Transactions")
            
            selected_party_detail = st.selectbox(
                "Select Party to View Details",
                options=["-- Select --"] + party_summary['Party Name'].tolist()
            )
            
            if selected_party_detail != "-- Select --":
                party_transactions = filtered_df[filtered_df['Party Name'] == selected_party_detail].copy()
                party_transactions = party_transactions.sort_values('Date', ascending=False)
                
                st.markdown(f"### Transactions with {selected_party_detail}")
                
                party_purchases = party_transactions[party_transactions['Type'].isin(['Purchase', 'Return In'])]['Total Amount'].sum()
                party_sales = party_transactions[party_transactions['Type'].isin(['Sale', 'Return Out'])]['Total Amount'].sum()
                party_receipts = party_transactions[party_transactions['Type'] == 'Receipt']['Total Amount'].sum()
                party_payments = party_transactions[party_transactions['Type'] == 'Payment']['Total Amount'].sum()
                
                detail_col1, detail_col2, detail_col3, detail_col4 = st.columns(4)
                with detail_col1:
                    display_metric_card("📥 Purchases", f"₹{party_purchases:,.0f}", "blue")
                with detail_col2:
                    display_metric_card("📤 Sales", f"₹{party_sales:,.0f}", "green")
                with detail_col3:
                    display_metric_card("💵 Receipts", f"₹{party_receipts:,.0f}", "purple")
                with detail_col4:
                    display_metric_card("💸 Payments", f"₹{party_payments:,.0f}", "orange")
                
                st.markdown("---")
                
                display_cols = ['Date', 'Type', 'Item Name', 'Quantity', 'Price per Unit', 'Total Amount', 'Description']
                display_df = party_transactions[display_cols].copy()
                display_df['Date'] = display_df['Date'].apply(safe_format_date)
                display_df['Quantity'] = display_df['Quantity'].apply(lambda x: int(abs(x)))
                display_df['Total Amount'] = display_df['Total Amount'].apply(lambda x: f"₹{x:,.2f}")
                display_df['Price per Unit'] = display_df['Price per Unit'].apply(lambda x: f"₹{x:,.2f}")
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                export_party_csv = party_transactions.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label=f"📥 Export {selected_party_detail} Transactions",
                    data=export_party_csv,
                    file_name=f"{selected_party_detail}_transactions_{datetime.today().strftime('%Y%m%d')}.csv",
                    mime='text/csv'
                )


# ==================== TAB 6: REPORTS ====================
with tab6:
    st.header("📈 Reports & Analytics")
    
    if df.empty:
        st.info("No data available for reports. Add some transactions first!")
    else:
        report_type = st.selectbox(
            "Select Report Type",
            ["Stock Summary", "Transaction Summary", "Monthly Analysis", "Item Analysis", "Party Analysis"]
        )
        
        st.markdown("---")
        
        if report_type == "Stock Summary":
            st.subheader("📦 Current Stock Summary")
            
            stock_qty = df.groupby('Item Name')['Quantity'].sum()
            last_prices = df[df['Price per Unit'] > 0].groupby('Item Name')['Price per Unit'].last()
            
            stock_report = pd.DataFrame({
                'Item Name': stock_qty.index,
                'Current Stock': stock_qty.values,
                'Last Price': last_prices.reindex(stock_qty.index, fill_value=0).values
            })
            stock_report['Stock Value'] = stock_report['Current Stock'] * stock_report['Last Price']
            stock_report = stock_report.sort_values('Stock Value', ascending=False)
            
            display_stock = stock_report.copy()
            display_stock['Last Price'] = display_stock['Last Price'].apply(lambda x: f"₹{x:,.2f}")
            display_stock['Stock Value'] = display_stock['Stock Value'].apply(lambda x: f"₹{x:,.2f}")
            display_stock['Current Stock'] = display_stock['Current Stock'].apply(lambda x: int(x))
            
            st.dataframe(display_stock, use_container_width=True, hide_index=True)
            
            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                st.markdown("**Stock Quantity Distribution**")
                positive_stock = stock_report[stock_report['Current Stock'] > 0].head(10)
                if not positive_stock.empty:
                    st.bar_chart(positive_stock.set_index('Item Name')['Current Stock'])
            
            with chart_col2:
                st.markdown("**Stock Value Distribution**")
                positive_value = stock_report[stock_report['Stock Value'] > 0].head(10)
                if not positive_value.empty:
                    st.bar_chart(positive_value.set_index('Item Name')['Stock Value'])
        
        elif report_type == "Transaction Summary":
            st.subheader("📊 Transaction Summary")
            
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                report_from = st.date_input(
                    "From", 
                    value=df['Date'].min().date() if pd.notna(df['Date'].min()) else datetime.today().date(), 
                    key="report_from"
                )
            with date_col2:
                report_to = st.date_input(
                    "To", 
                    value=df['Date'].max().date() if pd.notna(df['Date'].max()) else datetime.today().date(), 
                    key="report_to"
                )
            
            mask = (df['Date'] >= pd.Timestamp(report_from)) & (df['Date'] <= pd.Timestamp(report_to))
            report_df = df[mask]
            
            if not report_df.empty:
                type_summary = report_df.groupby('Type').agg({
                    'Quantity': lambda x: abs(x).sum(),
                    'Total Amount': 'sum'
                }).reset_index()
                type_summary.columns = ['Type', 'Total Quantity', 'Total Amount']
                
                st.markdown("**By Transaction Type**")
                for _, row in type_summary.iterrows():
                    icon = TRANSACTION_TYPES.get(row['Type'], {}).get('icon', '📝')
                    st.markdown(f"""
                        <div style="background-color: #f5f5f5; padding: 10px 15px; border-radius: 8px; 
                                    margin: 5px 0; border-left: 4px solid #673ab7;">
                            <span style="color: #424242;">{icon} <strong>{row['Type']}</strong>: 
                            {int(row['Total Quantity'])} units | ₹{row['Total Amount']:,.2f}</span>
                        </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                
                st.markdown("**Daily Transaction Trend**")
                daily = report_df.groupby(report_df['Date'].dt.date)['Total Amount'].sum()
                st.line_chart(daily)
            else:
                st.warning("No transactions found for the selected date range.")
        
        elif report_type == "Monthly Analysis":
            st.subheader("📅 Monthly Analysis")
            
            valid_dates = df.dropna(subset=['Date'])
            if not valid_dates.empty:
                monthly_df = valid_dates.copy()
                monthly_df['Month'] = monthly_df['Date'].dt.to_period('M').astype(str)
                
                monthly_summary = monthly_df.groupby(['Month', 'Type']).agg({
                    'Quantity': lambda x: abs(x).sum(),
                    'Total Amount': 'sum'
                }).reset_index()
                
                monthly_pivot = monthly_summary.pivot(index='Month', columns='Type', values='Total Amount').fillna(0)
                
                st.markdown("**Monthly Transaction Amounts**")
                display_monthly = monthly_pivot.copy()
                for col in display_monthly.columns:
                    display_monthly[col] = display_monthly[col].apply(lambda x: f"₹{x:,.2f}")
                st.dataframe(display_monthly, use_container_width=True)
                
                st.markdown("**Trend Chart**")
                st.line_chart(monthly_pivot)
            else:
                st.warning("No dated transactions available for monthly analysis.")
        
        elif report_type == "Item Analysis":
            st.subheader("📦 Item-wise Analysis")
            
            selected_item = st.selectbox("Select Item", options=["-- All Items --"] + master_items)
            
            if selected_item == "-- All Items --":
                item_summary = df.groupby('Item Name').agg({
                    'Quantity': 'sum',
                    'Total Amount': 'sum'
                }).reset_index()
                item_summary.columns = ['Item Name', 'Net Stock Change', 'Total Value']
                item_summary = item_summary.sort_values('Total Value', ascending=False)
                
                display_item_summary = item_summary.copy()
                display_item_summary['Net Stock Change'] = display_item_summary['Net Stock Change'].apply(lambda x: int(x))
                display_item_summary['Total Value'] = display_item_summary['Total Value'].apply(lambda x: f"₹{x:,.2f}")
                
                st.dataframe(display_item_summary, use_container_width=True, hide_index=True)
            else:
                item_df = df[df['Item Name'] == selected_item].sort_values('Date', ascending=False)
                
                if not item_df.empty:
                    total_in = item_df[item_df['Quantity'] > 0]['Quantity'].sum()
                    total_out = abs(item_df[item_df['Quantity'] < 0]['Quantity'].sum())
                    current_stock = total_in - total_out
                    avg_price = item_df[item_df['Price per Unit'] > 0]['Price per Unit'].mean()
                    
                    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                    with m_col1:
                        display_metric_card("📥 Total In", int(total_in), "green")
                    with m_col2:
                        display_metric_card("📤 Total Out", int(total_out), "red")
                    with m_col3:
                        display_metric_card("📦 Current Stock", int(current_stock), "blue")
                    with m_col4:
                        display_metric_card("💰 Avg Price", f"₹{avg_price:,.0f}" if pd.notna(avg_price) else "N/A", "purple")
                    
                    st.markdown("---")
                    st.markdown("**Transaction History**")
                    display_item_df = item_df[['Date', 'Party Name', 'Type', 'Quantity', 'Price per Unit', 'Total Amount']].copy()
                    display_item_df['Date'] = display_item_df['Date'].apply(safe_format_date)
                    display_item_df['Quantity'] = display_item_df['Quantity'].apply(lambda x: int(x))
                    display_item_df['Price per Unit'] = display_item_df['Price per Unit'].apply(lambda x: f"₹{x:,.2f}")
                    display_item_df['Total Amount'] = display_item_df['Total Amount'].apply(lambda x: f"₹{x:,.2f}")
                    st.dataframe(display_item_df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"No transactions found for {selected_item}")
        
        elif report_type == "Party Analysis":
            st.subheader("👥 Party-wise Analysis")
            
            selected_party = st.selectbox("Select Party", options=["-- All Parties --"] + master_parties)
            
            if selected_party == "-- All Parties --":
                party_summary = df.groupby('Party Name').agg({
                    'Total Amount': 'sum',
                    'Quantity': lambda x: len(x)
                }).reset_index()
                party_summary.columns = ['Party Name', 'Total Value', 'Transaction Count']
                party_summary = party_summary.sort_values('Total Value', ascending=False)
                
                display_party_summary = party_summary.copy()
                display_party_summary['Total Value'] = display_party_summary['Total Value'].apply(lambda x: f"₹{x:,.2f}")
                
                st.dataframe(display_party_summary, use_container_width=True, hide_index=True)
            else:
                party_df = df[df['Party Name'] == selected_party].sort_values('Date', ascending=False)
                
                if not party_df.empty:
                    total_transactions = len(party_df)
                    total_value = party_df['Total Amount'].sum()
                    first_trans = party_df['Date'].min()
                    last_trans = party_df['Date'].max()
                    
                    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                    with m_col1:
                        display_metric_card("📝 Transactions", total_transactions, "blue")
                    with m_col2:
                        display_metric_card("💰 Total Value", f"₹{total_value:,.0f}", "green")
                    with m_col3:
                        display_metric_card("📅 First Trans", safe_format_date(first_trans), "purple")
                    with m_col4:
                        display_metric_card("📅 Last Trans", safe_format_date(last_trans), "orange")
                    
                    st.markdown("---")
                    
                    # Type breakdown
                    type_breakdown = party_df.groupby('Type')['Total Amount'].sum()
                    st.markdown("**Transaction Type Breakdown**")
                    
                    breakdown_cols = st.columns(len(type_breakdown))
                    for i, (trans_type, amount) in enumerate(type_breakdown.items()):
                        icon = TRANSACTION_TYPES.get(trans_type, {}).get('icon', '📝')
                        with breakdown_cols[i]:
                            st.markdown(f"""
                                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 8px; text-align: center;">
                                    <span style="font-size: 1.5rem;">{icon}</span><br>
                                    <strong style="color: #424242;">{trans_type}</strong><br>
                                    <span style="color: #1b5e20; font-size: 1.2rem;">₹{amount:,.0f}</span>
                                </div>
                            """, unsafe_allow_html=True)
                    
                    st.markdown("---")
                    st.markdown("**All Transactions**")
                    display_party_df = party_df[['Date', 'Type', 'Item Name', 'Quantity', 'Price per Unit', 'Total Amount', 'Description']].copy()
                    display_party_df['Date'] = display_party_df['Date'].apply(safe_format_date)
                    display_party_df['Quantity'] = display_party_df['Quantity'].apply(lambda x: int(x))
                    display_party_df['Price per Unit'] = display_party_df['Price per Unit'].apply(lambda x: f"₹{x:,.2f}")
                    display_party_df['Total Amount'] = display_party_df['Total Amount'].apply(lambda x: f"₹{x:,.2f}")
                    st.dataframe(display_party_df, use_container_width=True, hide_index=True)
                    
                    # Export option
                    export_csv = party_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label=f"📥 Export {selected_party} Data",
                        data=export_csv,
                        file_name=f"{selected_party}_report_{datetime.today().strftime('%Y%m%d')}.csv",
                        mime='text/csv'
                    )
                else:
                    st.info(f"No transactions found for {selected_party}")
        
        st.markdown("---")
        st.download_button(
            label="📥 Export Full Data for Custom Reports",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name=f"full_data_export_{datetime.today().strftime('%Y%m%d')}.csv",
            mime='text/csv',
            use_container_width=True
        )


# === FOOTER ===
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #757575; padding: 20px;'>
        <p style='margin: 0;'>🏪 <strong>Business Inventory Tracker</strong> v2.0</p>
        <small>Built with ❤️ using Streamlit | Works Locally & on Cloud</small>
    </div>
    """,
    unsafe_allow_html=True
)