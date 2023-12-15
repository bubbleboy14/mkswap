# Copy And Trade
from .base import Worker
from .observer import Observer
from .backend import start, setStaging, predefs, gemget

class Cat(Worker):
	def __init__(self, symbols=["ETHUSD", "BTCUSD"], platform=predefs["platform"]):
		setStaging(False)
		self.symbols = symbols
		self.platform = platform
		self.watchers = {}
		for symbol in symbols:
			self.setWatcher(symbol)
		setStaging(True)

	def setWatcher(self, symbol):
		self.watchers[symbol] = Observer(self.platform,
			symbol, lambda event : self.relay(symbol, event))

	def relay(self, symbol, event):
		self.log("relay", symbol, event)

if __name__ == "__main__":
	Cat()
	start()