from rel.util import emit
from .backend import extractEvents, spew, predefs
from .base import Feeder
from .config import config

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
		if config.backend.mdv2:
			emit("mfsub", symbol, self.ingest)
		else:
			self.start_feed()

	def sig(self):
		return "Observer[%s]"%(self.symbol,)

	def message(self, message):
		self.ingest(extractEvents(message))

	def ingest(self, events):
		trades = False
		for event in events:
			if event["type"] == "trade":
				self.observe(event)
				trades = True
			else:
				emit("updateOrderBook", self.symbol, event)
			emit("histUp", self.symbol, event)
		trades and emit("priceChange")