from rel.util import ask, emit, listen
from .base import Base
from ..config import config

hcfg = config.strategy.handcart

class HandCart(Base):
	def __init__(self, symbol, recommender=None):
		Base.__init__(self, symbol, recommender)
		emit("tellMeWhen", self.symbol, "price",
			-hcfg.threshold, lambda : self.order("buy"))
		emit("tellMeWhen", self.symbol, "price",
			hcfg.threshold, lambda : self.order("sell"))
		listen("orderFilled", self.filled)
		self.log("loaded")

	def stat(self, name, value):
		self.stats[name] = value

	def filled(self, trade):
		if trade["remaining"]:
			return self.log("order filled ... incomplete")
		side = trade["side"] == "buy" and "sell" or "buy"
		self.order(side, self.nextPrice)

	def orderAmount(self, side):
		sym1, sym2 = self.symbol[:3], self.symbol[-3:]
		bals = ask("balances", mode="actual")
		bal = bals[side == "buy" and sym2 or sym1]
		return bal * hcfg.risk

	def order(self, side, price=None):
		if not price:
			price = ask("bestOrder", self.symbol, side)
		order = {
			"side": side,
			"price": price,
			"symbol": self.symbol,
			"amount": self.orderAmount(side)
		}
		pdiff = price * hcfg.profit
		if side == "buy":
			pdiff *= -1
		self.nextPrice = price + pdiff
		self.stat("lastPrice", price)
		self.stat("nextPrice", self.nextPrice)
		self.warn("order(%s, %s) nextPrice: %s"%(side,
			price, self.nextPrice), order)
		emit("trade", order)