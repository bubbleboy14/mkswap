from rel.util import emit, listen
from .base import Worker

class Booker(Worker):
	def __init__(self):
		self.totals = {}
		self.orders = {}
		self.orderBook = {}
		listen("updateOrderBook", self.updateOrderBook)

	def updateOrderBook(self, symbol, event):
		if symbol not in self.orders:
			self.orders[symbol] = {}
			self.orderBook[symbol] = { "bid": {}, "ask": {} }
		side = event["side"]
		price = float(event["price"])
		self.orderBook[symbol][side][price] = float(event["remaining"])
		self.orders[symbol][side] = price
		emit("quote", symbol, price, volume=float(event["delta"]), history=side)

	def totals(self):
		for sym in self.orderBook:
			self.totals[sym] = {}
			symhist = self.orderBook[sym]
			for side in symhist:
				self.totals[sym][side] = 0
				sidehist = symhist[side]
				for price in sidehist:
					self.totals[sym][side] += price * sidehist[price]
		return tz