import signal
from datetime import datetime, timedelta
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.common import TickerId

port = 7496

class IBapi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId: int):
        self.nextOrderId = orderId
        self.start()

    def start(self):
        contract = Contract()
        contract.symbol = "SPX"
        contract.secType = "IND"
        contract.exchange = "CBOE"
        contract.currency = "USD"

        # Request historical data
        end_date_time = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d-%H:%M:%S")
        self.reqHistoricalData(1, contract, end_date_time, "1 W", "15 mins", "TRADES", 1, 1, False, [])

    def historicalData(self, reqId, bar):
        print(f"Date: {bar.date}, Open: {bar.open}, High: {bar.high}, Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}")

    def historicalDataEnd(self, reqId, start, end):
        print("Historical data request completed")
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