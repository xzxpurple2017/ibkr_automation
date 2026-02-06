import signal
from datetime import datetime, timedelta
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.common import OrderId
from ibapi.execution import Execution, ExecutionFilter

port = 7496

class IBapi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId: int):
        self.nextOrderId = orderId
        self.start()

    def start(self):
        # Request executions (trades)
        filter = ExecutionFilter()
        filter.time = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d %H:%M:%S")
        filter.acctCode = ""  # Specify account code if needed
        self.reqExecutions(1, filter)

    def execDetails(self, reqId: int, contract, execution: Execution):
        print(f"ExecDetails. ReqId: {reqId}, Symbol: {contract.symbol}, SecType: {contract.secType}, "
              f"Exchange: {contract.exchange}, Action: {execution.side}, "
              f"Shares: {execution.shares}, Price: {execution.price}, Time: {execution.time}")

    def execDetailsEnd(self, reqId: int):
        print("Execution details request completed")
        self.disconnect()

def signal_handler(sig, frame):
    print('Disconnecting...')
    app.disconnect()

app = IBapi()
app.connect('127.0.0.1', port, 123)

signal.signal(signal.SIGINT, signal_handler)

app.run()
print('Disconnected')