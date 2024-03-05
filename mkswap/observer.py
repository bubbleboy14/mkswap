from rel.util import emit
from .backend import events, spew, predefs
from .base import Feeder

class Observer(Feeder):
	def __init__(self, symbol, platform=predefs["platform"], observe=spew):
		self.platform = platform
		self.symbol = symbol
		self.observe = observe
		self.history = {
			"ask": [],
			"bid": [],
			"BUY": [],
			"SELL": [],
			"w_average": [],
			"1_w_average": []
		}
		self.start_feed()

	def sig(self):
		return "Observer[%s]"%(self.symbol,)

	def on_message(self, ws, message):
		eventz = events(message)
		trades = False
		for event in eventz:
			if event["type"] == "trade":
				event["side"] = event["makerSide"]
				self.observe(event)
				trades = True
			else:
				emit("updateOrderBook", self.symbol, event)
		trades and emit("priceChange")