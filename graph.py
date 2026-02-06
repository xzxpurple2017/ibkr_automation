import signal
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.common import TickerId
from calendar import monthrange

port = 7496

# Configuration
SYMBOL = "ES"  # ES futures, change to "SPX" for index, "MES" for micro ES, etc.
SEC_TYPE = "FUT"  # FUT for futures, IND for index, STK for stocks
EXCHANGE = "CME"  # CME for ES futures, CBOE for SPX
CURRENCY = "USD"
CONTRACT_MONTH = None  # Set to None for auto (current front month), or specify like "202603" for March 2026
DATA_DURATION = "3 W"  # How much historical data to fetch
BAR_SIZE = "15 mins"  # Bar size

def get_front_month_contract():
    """Calculate the current front-month futures contract."""
    now = datetime.now()
    year = now.year
    month = now.month
    
    # ES futures expire on 3rd Friday of contract month
    # Find 3rd Friday of current month
    def third_friday(year, month):
        # Find first day of month and its weekday
        first_day = datetime(year, month, 1)
        # Friday is weekday 4
        days_until_friday = (4 - first_day.weekday()) % 7
        # First Friday
        first_friday = 1 + days_until_friday
        # Third Friday is 14 days later
        third_friday_day = first_friday + 14
        return datetime(year, month, third_friday_day)
    
    current_expiry = third_friday(year, month)
    
    # If we're within 5 days of expiry or past it, roll to next month
    if now >= current_expiry - timedelta(days=5):
        month += 1
        if month > 12:
            month = 1
            year += 1
    
    # ES quarterly cycle: Mar(H), Jun(M), Sep(U), Dec(Z)
    # But also has all months, use quarterly for main contracts
    quarterly_months = [3, 6, 9, 12]  # H, M, U, Z
    
    # Find next quarterly month
    for qm in quarterly_months:
        if month <= qm:
            month = qm
            break
    else:
        # If past December, go to next year's March
        month = 3
        year += 1
    
    return f"{year}{month:02d}"

def calculate_td_sequential(df):
    """Calculate TD Sequential Setup"""
    close = df['Close'].values
    setup_count = np.zeros(len(df))
    
    for i in range(4, len(df)):
        # Buy setup: close < close 4 bars ago
        if close[i] < close[i-4]:
            if i > 0 and setup_count[i-1] < 0:
                setup_count[i] = setup_count[i-1] - 1
            else:
                setup_count[i] = -1
            # Reset if we reach -9
            if setup_count[i] <= -9:
                setup_count[i] = -9
        # Sell setup: close > close 4 bars ago
        elif close[i] > close[i-4]:
            if i > 0 and setup_count[i-1] > 0:
                setup_count[i] = setup_count[i-1] + 1
            else:
                setup_count[i] = 1
            # Reset if we reach 9
            if setup_count[i] >= 9:
                setup_count[i] = 9
        else:
            setup_count[i] = 0
    
    return setup_count

def calculate_td_combo(df):
    """Calculate TD Combo"""
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    
    setup_count = np.zeros(len(df))
    countdown_count = np.zeros(len(df))
    in_countdown = False
    countdown_direction = 0
    
    for i in range(4, len(df)):
        # Setup phase (same as TD Sequential)
        if not in_countdown:
            if close[i] < close[i-4]:
                if i > 0 and setup_count[i-1] < 0:
                    setup_count[i] = setup_count[i-1] - 1
                else:
                    setup_count[i] = -1
                    
                if setup_count[i] <= -9:
                    setup_count[i] = -9
                    in_countdown = True
                    countdown_direction = -1
                    
            elif close[i] > close[i-4]:
                if i > 0 and setup_count[i-1] > 0:
                    setup_count[i] = setup_count[i-1] + 1
                else:
                    setup_count[i] = 1
                    
                if setup_count[i] >= 9:
                    setup_count[i] = 9
                    in_countdown = True
                    countdown_direction = 1
            else:
                setup_count[i] = 0
        
        # Countdown phase
        if in_countdown and i >= 2:
            countdown_count[i] = countdown_count[i-1]
            
            if countdown_direction == 1:  # Sell countdown
                if close[i] > high[i-2]:
                    countdown_count[i] += 1
            else:  # Buy countdown
                if close[i] < low[i-2]:
                    countdown_count[i] -= 1
            
            # Complete at 13
            if abs(countdown_count[i]) >= 13:
                countdown_count[i] = 13 * countdown_direction
                in_countdown = False
    
    return setup_count, countdown_count

class IBapi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.dates = []
        self.opens = []
        self.highs = []
        self.lows = []
        self.closes = []
        self.volumes = []

    def nextValidId(self, orderId: int):
        self.nextOrderId = orderId
        self.start()

    def start(self):
        contract = Contract()
        contract.symbol = SYMBOL
        contract.secType = SEC_TYPE
        contract.exchange = EXCHANGE
        contract.currency = CURRENCY
        
        # Set contract month for futures
        if SEC_TYPE == "FUT":
            contract.lastTradeDateOrContractMonth = CONTRACT_MONTH if CONTRACT_MONTH else get_front_month_contract()
            print(f"Trading contract: {SYMBOL} {contract.lastTradeDateOrContractMonth}")

        # Request historical data - empty string means "now"
        # useRTH = 0 to include all trading hours (extended/overnight), not just regular hours
        self.reqHistoricalData(1, contract, "", DATA_DURATION, BAR_SIZE, "TRADES", 0, 1, False, [])

    def historicalData(self, reqId, bar):
        print(f"Date: {bar.date}, Open: {bar.open}, High: {bar.high}, Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}")
        # Store data for graphing
        # Remove timezone portion if present (e.g., "20260123 06:30:00 America/Los_Angeles")
        date_str = bar.date.split()[0] + ' ' + bar.date.split()[1]
        self.dates.append(datetime.strptime(date_str, "%Y%m%d %H:%M:%S"))
        self.opens.append(bar.open)
        self.highs.append(bar.high)
        self.lows.append(bar.low)
        self.closes.append(bar.close)
        self.volumes.append(bar.volume)

    def historicalDataEnd(self, reqId, start, end):
        print("Historical data request completed")
        
        # Create DataFrame for mplfinance
        df = pd.DataFrame({
            'Open': pd.to_numeric(self.opens),
            'High': pd.to_numeric(self.highs),
            'Low': pd.to_numeric(self.lows),
            'Close': pd.to_numeric(self.closes),
            'Volume': pd.to_numeric(self.volumes)
        }, index=pd.DatetimeIndex(self.dates))
        
        # Calculate TD indicators
        td_seq = calculate_td_sequential(df)
        td_combo_setup, td_combo_countdown = calculate_td_combo(df)
        
        # Debug: print some statistics
        print(f"TD Sequential - Min: {td_seq.min()}, Max: {td_seq.max()}")
        print(f"TD Combo Countdown - Min: {td_combo_countdown.min()}, Max: {td_combo_countdown.max()}")
        print(f"Number of TD Sequential 8-9: {np.sum(np.abs(td_seq) >= 8)}")
        print(f"Number of TD Combo Countdown values: {np.sum(td_combo_countdown != 0)}")
        
        # Create annotations for TD Sequential
        annotations = []
        for i, (date, value) in enumerate(zip(df.index, td_seq)):
            if value != 0 and abs(value) >= 6:
                # Only show when count changes or is at 9 (completion)
                if i == 0 or td_seq[i] != td_seq[i-1]:
                    color = 'red' if value > 0 else 'green'
                    annotations.append(
                        dict(
                            x=i, y=df['High'].iloc[i] * 1.003,
                            text=str(int(abs(value))),
                            fontsize=9,
                            color=color,
                            weight='bold'
                        )
                    )
        
        # Add TD Combo countdown annotations
        for i, (date, value) in enumerate(zip(df.index, td_combo_countdown)):
            if value != 0 and abs(value) >= 1:
                # Only show when countdown changes
                if i == 0 or td_combo_countdown[i] != td_combo_countdown[i-1]:
                    color = 'darkred' if value > 0 else 'darkgreen'
                    annotations.append(
                        dict(
                            x=i, y=df['Low'].iloc[i] * 0.997,
                            text=f"C{int(abs(value))}",
                            fontsize=8,
                            color=color,
                            style='italic'
                        )
                    )
        
        print(f"Total annotations to add: {len(annotations)}")
        
        # Detect trading hours pattern to determine if we should close gaps
        # Check time differences between consecutive bars
        time_diffs = df.index.to_series().diff().dropna()
        median_diff = time_diffs.median()
        max_diff = time_diffs.max()
        
        # If max gap is much larger than median (e.g., overnight/weekend gaps),
        # this is likely a regular hours market - apply rangebreaks
        has_gaps = max_diff > median_diff * 5
        
        print(f"Median bar interval: {median_diff}")
        print(f"Max gap detected: {max_diff}")
        print(f"Applying gap closure: {has_gaps}")
        
        # Create interactive plotly chart
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=(f'{SYMBOL} with TD Sequential & TD Combo', 'Volume')
        )
        
        # Add candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name=SYMBOL,
                increasing_line_color='green',
                decreasing_line_color='red'
            ),
            row=1, col=1
        )
        
        # Add volume bars
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['Volume'],
                name='Volume',
                marker_color='lightgray',
                showlegend=False
            ),
            row=2, col=1
        )
        
        # Add annotations to plotly
        plotly_annotations = []
        for ann in annotations:
            plotly_annotations.append(
                dict(
                    x=df.index[ann['x']],
                    y=ann['y'],
                    text=ann['text'],
                    showarrow=False,
                    font=dict(
                        size=ann['fontsize'],
                        color=ann['color'],
                        family='Arial Black' if ann.get('weight') == 'bold' else 'Arial'
                    ),
                    xref='x',
                    yref='y'
                )
            )
        
        # Build layout configuration
        layout_config = dict(
            annotations=plotly_annotations,
            title=f'{SYMBOL} - Interactive Candlestick Chart with TD Indicators',
            yaxis_title='Price (USD)',
            yaxis2_title='Volume',
            xaxis_rangeslider_visible=False,
            height=800,
            hovermode='x unified',
            template='plotly_white'
        )
        
        # Don't apply rangebreaks - show all data continuously including weekend opens
        # For futures that trade nearly 24/7, gaps are minimal and informative
        print(f"Not closing gaps - showing all trading hours for futures")
        
        fig.update_layout(**layout_config)
        
        fig.show()
        
        self.disconnect()

    def tickPrice(self, reqId: TickerId, tickType: int, price: float, attrib):
        print(f"Tick Price. Ticker Id: {reqId}, tickType: {tickType}, Price: {price}")

    def tickSize(self, reqId: TickerId, tickType: int, size: int):
        print(f"Tick Size. Ticker Id: {reqId}, tickType: {tickType}, Size: {size}")

def signal_handler(sig, frame):
    print('Disconnecting...')
    app.disconnect()

app = IBapi()
app.connect('127.0.0.1', port, 123)

signal.signal(signal.SIGINT, signal_handler)

app.run()
print('Disconnected')