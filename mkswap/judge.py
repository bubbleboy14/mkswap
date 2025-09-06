from rel.util import ask, listen
from .base import Worker
from .config import config

class Judge(Worker):
	def __init__(self, syms=["ETHUSD", "BTCUSD"]):
		self.syms = list(filter(lambda s : s.endswith("USD"), syms))
		listen("wise", self.wise)
		listen("usdcap", self.usdcap)
		listen("bestBuys", self.bestBuys)

	def mods(self):
		mods = {}
		for sym in self.syms:
			r = ask("range", sym)
			short = r["short"]
			span = r["span"]
			low = r["low"]
			mods[sym] = span and ((short - low) / span - 0.5) or 0
		vals = list(mods.values())
		vals.sort()
		mods["lowest"] = vals.pop(0)
		return mods

	def bestBuys(self, syms=None):
		mods = self.mods()
		lowest = mods["lowest"]
		s2p = lambda s : mods[ask("fullSym", s)]
		syms = syms or [s[:3] for s in self.syms]
		lowsyms = list(filter(lambda s : s2p(s) == lowest, syms))
		if not lowsyms:
			syms.sort(key=s2p)
			lowsyms.append(syms.pop(0))
		return lowsyms

	def usdcap(self, base=50):
		mods = self.mods()
		cap = base + base * mods["lowest"]
		self.log("usdcap", cap, mods)
		return cap

	def wise(self, trade, strict=False):
		if strict:
			adxlim = 25
			mfibot = 20
		else:
			jcfg = config.judge
			adxlim = jcfg.adxlim
			mfibot = jcfg.mfilim
		mfitop = 100 - mfibot
		if adxlim:
			side = trade["side"]
			sym = trade["symbol"]
			adx = ask("metric", sym, "ADX")
			pdi = ask("metric", sym, "+DI")
			mdi = ask("metric", sym, "-DI")
			if adx > adxlim:
				goingup = pdi > mdi
				selling = side == "sell"
				if (goingup and selling) or (not goingup and not selling):
					mfi = ask("metric", sym, "mfi")
					vpts = ask("metric", sym, "VPTsmall")
					vptm = ask("metric", sym, "VPTmedium")
					macdsig = ask("metric", sym, "macdsig")
					macd = ask("metric", sym, "macd")
					macdup = macd > macdsig
					vptup = vpts > vptm
					vals = {
						"ADX": adx,
						"+DI": pdi,
						"-DI": mdi,
						"mfi": mfi,
						"macd": macd,
						"macdsig": macdsig,
						"VPTsmall": vpts,
						"VPTmedium": vptm,
						"adxlim": adxlim,
						"mfilim": mfibot,
						"trade": trade
					}
					noticer = strict and self.notice or self.log
					if (selling and mfi > mfitop) or (not selling and mfi < mfibot):
						noticer("wise (mfi) %s %s"%(sym, side), vals)
						return "very"
					elif (selling and not macdup) or (not selling and macdup):
						noticer("wise (macd) %s %s"%(sym, side), vals)
						return "very"
					elif (selling and not vptup) or (not selling and vptup):
						self.log("approved (vpt) %s %s"%(sym, side), vals)
					else:
						return noticer("unwise %s %s"%(sym, side), vals)
		return True