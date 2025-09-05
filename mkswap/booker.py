from rel.util import emit, listen
from .base import Worker

request2order = {
	"buy": "ask",
	"sell": "bid"
}

class Booker(Worker):
	def __init__(self):
		self.bests = {}
		self.totes = {}
		self.orders = {}
		self.orderBook = {}
		listen("unbook", self.unbook)
		listen("bestOrder", self.bestOrder)
		listen("updateOrderBook", self.updateOrderBook)

	def unbook(self, order):
		order["price"] = self.shifted(order["symbol"], order["side"], order["price"])
		return order

	def shifted(self, symbol, side, price):
		oside = request2order[side]
		inusd = symbol.endswith("USD")
		inc = inusd and 0.01 or 0.00001
		if side == "buy":
			inc *= -1
		orig = price
		ob = self.orderBook[symbol][oside]
		if price in ob:
			while price in ob:
				price += inc
			price = round(price, inusd and 2 or 5)
			self.notice("shifted %s %s (%s) from %s to %s"%(symbol, oside, side, orig, price))
		return price

	def bestOrder(self, symbol, side, shift=False):
		oside = request2order[side]
		bo = self.bests[symbol][oside]
		self.log("bestOrder(%s, %s->%s)"%(symbol, side, oside), bo)
		return shift and self.shifted(symbol, side, bo) or bo

	def pricePoints(self, symbol, side):
		obook = self.orderBook[symbol][side]
		return list(filter(lambda p : obook[p], obook.keys()))

	def updateOrderBook(self, symbol, event):
		if symbol not in self.orders:
			self.bests[symbol] = {}
			self.orders[symbol] = {}
			self.orderBook[symbol] = { "bid": {}, "ask": {} }
		side = event["side"]
		isask = side == "ask"
		price = float(event["price"])
		remaining = float(event["remaining"])
		obook = self.orderBook[symbol][side]
		if remaining:
			obook[price] = remaining
			self.orders[symbol][side] = price
		elif price in obook:
			del obook[price]
		prices = self.pricePoints(symbol, side)
		if prices:
			self.bests[symbol][side] = (isask and min or max)(prices)
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