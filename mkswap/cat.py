# Copy And Trade
import rel
from .base import Worker
from .observer import Observer
from .backend import start, setStaging, predefs
from .agent import agencies
from .gem import gem

class Cat(Worker):
	def __init__(self, relay=gem.trade, symbols=["ETHUSD", "BTCUSD"], platform=predefs["platform"]):
		setStaging(False)
		self.relay = relay
		self.symbols = symbols
		self.platform = platform
		self.watchers = {}
		self.pending = []
		self.relayed = 0
		for symbol in symbols:
			self.setWatcher(symbol)
		setStaging(True)
		self.agent = agencies[platform]()
		rel.timeout(0.1, self.churn)
		rel.timeout(1, self.tick)

	def tick(self):
		self.log("relayed:", self.relayed, "; pending:", len(self.pending))
		return True

	def churn(self):
		if self.pending:
			self.relayed += 1
			self.relay(self.pending.pop(0))
		return True

	def setWatcher(self, symbol):
		self.watchers[symbol] = Observer(symbol, self.platform,
			lambda event : self.intake(symbol, event))

	def intake(self, symbol, event):
#		self.log("relay", symbol, event)
		self.pending.append({
			"symbol": symbol,
			"price": event["price"],
			"amount": event["delta"],
			"type": "exchange limit",
			"side": (event["side"] == "ask") and "buy" or "sell"
		})

if __name__ == "__main__":
	Cat()
	start()