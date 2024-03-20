import json
from rel.util import listen
from .base import Feeder
from .config import config

sidetrans = {
	"buy": "bid",
	"sell": "ask"
}

class MultiFeed(Feeder):
	def __init__(self):
		self.platform = "geminiv2"
		self.subscriptions = {}
		self.start_feed()
		listen("mfsub", self.subscribe)

	def on_open(self):
		self.log("opened")
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

	def on_message(self, ws, message):
		config.base.unspammed or self.log(message)
		data = json.loads(message)
		mode = data["type"]
		if mode == "heartbeat":
			return self.log(message)
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
		self.ws.jsend({
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