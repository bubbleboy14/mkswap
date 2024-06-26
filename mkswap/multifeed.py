import json
from rel.util import listen
from .base import Feeder

sidetrans = {
	"buy": "bid",
	"sell": "ask"
}

class MultiFeed(Feeder):
	def __init__(self):
		listen("mfsub", self.subscribe)
		self.platform = "geminiv2"
		self.subscriptions = {}
		self.start_feed()

	def on_ready(self):
		for sym in self.subscriptions:
			for mode in self.subscriptions[sym]:
				self.sub(sym, mode)

	def l2(self, change, sym):
		return {
			"symbol": sym,
			"price": change[1],
			"type": "orderbook",
			"remaining": change[2],
			"side": sidetrans[change[0]]
		}

	def trade(self, trade):
		trade["side"] = sidetrans[trade["side"]]
		trade["amount"] = trade["quantity"]
		return trade

	def message(self, data):
		mode = data.get("type")
		if not mode:
			return self.log("skipping typeless data:", data)
		events = []
		sym = data["symbol"]
		if mode == "trade":
			mode = "l2"
			events.append(self.trade(data))
		else:
			changes = data["changes"]
			mode = mode[:-8]
			if mode == "l2":
				events += [self.l2(change, sym) for change in changes]
				events += [self.trade(t) for t in data.get("trades", [])]
			else: # candles
				events = changes
		for sub in self.subs(sym, mode):
			sub(events)

	def sub(self, symbol, mode):
		self.ws.ready() and self.ws.jsend({
			"type": "subscribe",
			"subscriptions": [{
				"name": mode,
				"symbols": [symbol]
			}]
		})

	def subs(self, symbol, mode="l2"):
		if symbol not in self.subscriptions:
			self.subscriptions[symbol] = {}
		if mode not in self.subscriptions[symbol]:
			self.subscriptions[symbol][mode] = []
			self.sub(symbol, mode)
		return self.subscriptions[symbol][mode]

	def subscribe(self, symbol, cb, mode="l2"):
		self.subs(symbol, mode).append(cb)