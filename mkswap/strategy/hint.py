from rel.util import ask, emit, listen
from .base import Base
from ..config import config

hcfg = config.strategy.hint

class Hint(Base):
	def __init__(self, symbol):
		Base.__init__(self, symbol)
		listen("hint", self.hint)

	def hint(self, sym, side, score):
		if sym != self.symbol: return
		self.stat(side, score)
		if abs(score) < hcfg.score:
			return
		price = self.stat("best%s"%(side,), ask("bestPrice", sym, side))
		amount = hcfg.mult * score / price
		if side == "sell":
			amount *= -1
		self.log("hint(%s, %s, %s): %s @ %s"%(sym, side, score, amount, price))
		emit("trade", {
			"side": side,
			"symbol": sym,
			"price": price,
			"amount": amount
		})