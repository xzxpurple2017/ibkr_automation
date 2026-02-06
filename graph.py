import signal
from datetime import datetime, timedelta
import pandas as pd
import mplfinance as mpf
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.common import TickerId

port = 7496

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
        contract.symbol = "SPX"
        contract.secType = "IND"
        contract.exchange = "CBOE"
        contract.currency = "USD"

        # Request historical data - empty string means "now"
        self.reqHistoricalData(1, contract, "", "2 W", "15 mins", "TRADES", 1, 1, False, [])

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
        
        # Create candlestick chart
        mpf.plot(df, 
                 type='candle',
                 style='charles',
                 volume=True,
                 title='SPX Index - Historical Data (15-minute bars)',
                 ylabel='Price (USD)',
                 ylabel_lower='Volume',
                 figsize=(12, 8),
                 warn_too_much_data=1000)
        
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