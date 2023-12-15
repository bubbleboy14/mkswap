# Copy And Trade
import rel
from .base import Worker
from .observer import Observer
from .backend import start, setStaging, predefs, gemtrade

class Cat(Worker):
	def __init__(self, symbols=["ETHUSD", "BTCUSD"], platform=predefs["platform"]):
		setStaging(False)
		self.symbols = symbols
		self.platform = platform
		self.watchers = {}
		self.pending = []
		self.relayed = 0
		for symbol in symbols:
			self.setWatcher(symbol)
		setStaging(True)
		rel.timeout(0.1, self.churn)
		rel.timeout(1, self.tick)

	def tick(self):
		self.log("relayed:", self.relayed, "; pending:", len(self.pending))

	def churn(self):
		if self.pending:
			self.relayed += 1
			gemtrade(self.pending.pop(0))

	def setWatcher(self, symbol):
		self.watchers[symbol] = Observer(self.platform,
			symbol, lambda event : self.relay(symbol, event))

	def relay(self, symbol, event):
#		self.log("relay", symbol, event)
		self.pending.append({
			"symbol": symbol,
			"price": event["price"],
			"amount": event["delta"],
			"side": (event["side"] == "ask") and "buy" or "sell"
		})

if __name__ == "__main__":
	Cat()
	start()