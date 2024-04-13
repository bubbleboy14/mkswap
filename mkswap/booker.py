from rel.util import emit, listen
from .base import Worker

class Booker(Worker):
	def __init__(self):
		self.bests = {}
		self.totes = {}
		self.orders = {}
		self.orderBook = {}
		listen("bestOrder", self.bestOrder)
		listen("updateOrderBook", self.updateOrderBook)

	def bestOrder(self, symbol, side):
		return self.bests[symbol][side]

	def updateOrderBook(self, symbol, event):
		if symbol not in self.orders:
			self.bests[symbol] = {}
			self.orders[symbol] = {}
			self.orderBook[symbol] = { "bid": {}, "ask": {} }
		side = event["side"]
		isask = side == "ask"
		price = float(event["price"])
		self.orderBook[symbol][side][price] = float(event["remaining"])
		self.orders[symbol][side] = price
		self.bests[symbol][side] = (isask and min or max)(self.orderBook[symbol][side].keys())
		emit("quote", symbol, price, volume=float(event["remaining"]), history=side)

	def totals(self):
		for sym in self.orderBook:
			self.totes[sym] = {}
			symhist = self.orderBook[sym]
			for side in symhist:
				self.totes[sym][side] = 0
				sidehist = symhist[side]
				for price in sidehist:
					self.totes[sym][side] += sidehist[price]
		return self.totes