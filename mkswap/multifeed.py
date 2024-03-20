from rel.util import listen
from .base import Feeder

class MultiFeed(Feeder):
	def __init__(self):
		self.platform = "geminiv2"
		self.subscriptions = {}
		self.start_feed()
		listen("mfsub", self.subscribe)

	def on_message(self, ws, message):
		symsubs = self.subscriptions[message["symbol"]]
		# pass updates to cb()s

	def subs(self, symbol, mode="l2"):
		if symbol not in self.subscriptions:
			self.subscriptions[symbol] = {}
		if mode not in self.subscriptions[symbol]:
			self.subscriptions[symbol][mode] = []
			self.ws.jsend({
				"type": "subscribe",
				"subscriptions": [{
					"name": mode,
					"symbols": [symbol]
				}]
			})
		return self.subscriptions[symbol][mode]

	def subscribe(self, symbol, cb, mode="l2"):
		self.subs(symbol, mode).append(cb)