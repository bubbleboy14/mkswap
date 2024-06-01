from rel.util import ask, emit, listen
from .base import Base
from ..config import config

ccfg = config.strategy.cross

class Cross(Base):
	def __init__(self, symbol):
		Base.__init__(self, symbol)
		listen("cross", self.cross)
		listen("hint", self.hint)

	def cross(self, sym, variety, reason, dimension="price"):
		self.log("cross(%s, %s, %s) %s"%(sym, dimension, variety, reason))
		side = (variety == "golden") and "buy" or "sell"
		self.notice("hard %s!"%(side,), ask("bestTrades", sym, side, force=True))

	def hint(self, sym, side, score):
		if sym != self.symbol: return
		self.stat(side, score)
		if abs(score) < ccfg.score:
			return
		price = self.stat("best%s"%(side,), ask("bestPrice", sym, side))
		amount = ccfg.mult * score / price
		if side == "sell":
			amount *= -1
		self.log("hint(%s, %s, %s): %s @ %s"%(sym, side, score, amount, price))
		emit("trade", {
			"side": side,
			"symbol": sym,
			"price": price,
			"amount": amount
		})