from rel.util import ask
from .macd import MACD

class MACDADX(MACD):
	def trigTrade(self, sym, side):
		adx = ask("metric", sym, "ADX")
		if adx < 25:
			return self.log("trigTrade(%s, %s) aborted! ADX=%s"%(sym, side, adx))
		force = adx > 30
		self.notice("%s %s!"%(force and "hard" or "soft", side),
			ask("bestTrades", sym, side, force=force))