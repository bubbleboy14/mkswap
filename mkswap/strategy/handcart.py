from rel.util import ask, emit, listen
from .base import Base
from ..config import config

hcfg = config.strategy.handcart

class HandCart(Base):
	def __init__(self, symbol):
		Base.__init__(self, symbol)
		emit("tellMeWhen", self.symbol, "price",
			-hcfg.threshold, lambda : self.order("buy"))
		emit("tellMeWhen", self.symbol, "price",
			hcfg.threshold, lambda : self.order("sell"))
		listen("orderFilled", self.filled)
		self.log("loaded")

	def filled(self, trade):
		if trade["remaining"]:
			return self.log("order filled ... incomplete")
		side = trade["side"] == "buy" and "sell" or "buy"
		self.order(side, self.nextPrice(trade))

	def nextPrice(self, trade):
		side = trade["side"]
		price = trade["price"]
		pdiff = price * hcfg.profit
		if side == "sell":
			pdiff *= -1
		nextPrice = price + pdiff
		self.stat("lastSide", side)
		self.stat("lastPrice", price)
		self.stat("nextPrice", nextPrice)
		return nextPrice

	def orderAmount(self, side, price):
		isbuy = side == "buy"
		sym1, sym2 = self.symbol[:3], self.symbol[-3:]
		bals = ask("balances", mode="actual", nousd=True)
		bal = bals[isbuy and sym2 or sym1]
		if isbuy: # convert to sym1 units
			bal /= price
		return bal * hcfg.risk

	def order(self, side, price=None):
		if not price:
			price = ask("bestOrder", self.symbol, side)
		order = {
			"side": side,
			"force": True,
			"price": price,
			"symbol": self.symbol,
			"amount": self.orderAmount(side, price)
		}
		self.warn("order(%s, %s) nextPrice: %s"%(side,
			price, self.nextPrice(order)), order)
		emit("trade", order)