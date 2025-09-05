from rel.util import emit, listen
from .backend import predefs
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
		listen("bestOrder", self.bestOrder)
		listen("updateOrderBook", self.updateOrderBook)

	def bestOrder(self, symbol, side, shift=False):
		oside = request2order[side]
		bo = self.bests[symbol][oside]
		self.log("bestOrder(%s, %s->%s)"%(symbol, side, oside), bo)
		if shift:
			inc = predefs["minimums"][symbol]
			if side == "buy":
				inc *= -1
			obo = bo
			ob = self.orderBook[symbol][side]
			while bo in ob:
				bo += inc
			self.notice("shifted %s %s from %s to %s"%(symbol, side, obo, bo))
		return bo

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
		self.orderBook[symbol][side][price] = float(event["remaining"])
		self.orders[symbol][side] = price
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