from rel.util import ask
from .macd import MACD
from ..config import config

mxfg = config.strategy.macdadx

class MACDADX(MACD):
	def trigTrade(self, sym, side):
		adx = ask("metric", sym, "ADX")
		if adx < mxfg.low:
			return self.log("trigTrade(%s, %s) aborted! ADX=%s"%(sym, side, adx))
		force = adx > mxfg.high
		self.notice("%s %s!"%(force and "hard" or "soft", side),
			ask("bestTrades", sym, side, force=force))