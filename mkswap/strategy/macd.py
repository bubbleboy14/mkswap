from rel.util import ask, listen
from .base import Base

class MACD(Base):
	def __init__(self, symbol):
		Base.__init__(self, symbol)
		listen("cross", self.cross)

	def cross(self, sym, variety, reason, dimension="price"):
		if sym != self.symbol or dimension != "MACD": return
		self.log("cross(%s, %s, %s) %s"%(sym, dimension, variety, reason))
		side = (variety == "golden") and "buy" or "sell"
		self.notice("hard %s!"%(side,), ask("bestTrades", sym, side, force=True))