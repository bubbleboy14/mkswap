from rel.util import emit
from .backend import events, spew, predefs
from .base import Feeder

class Observer(Feeder):
	def __init__(self, symbol, platform=predefs["platform"], observe=spew, use_initial=False):
		self.symbol = symbol
		self.observe = observe
		self.use_initial = use_initial
		self.history = {
			"ask": [],
			"bid": [],
			"BUY": [],
			"SELL": [],
			"w_average": [],
			"1_w_average": []
		}
		self.feed(platform, symbol)

	def sig(self):
		return "Observer[%s]"%(self.symbol,)

	def on_message(self, ws, message):
		eventz = events(message, self.use_initial)
		for event in eventz:
			self.observe(event)
		eventz and emit("priceChange")