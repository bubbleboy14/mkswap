from rel.util import ask, emit, listen
from .base import Worker
from .config import config

class Judge(Worker):
	def __init__(self, syms=["ETHUSD", "BTCUSD"]):
		self.syms = list(filter(lambda s : s.endswith("USD"), syms))
		listen("wise", self.wise)
		listen("usdcap", self.usdcap)
		listen("bestBuy", self.bestBuy)

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

	def score(self, sym):
		return ask("strength", sym) + ask("drift", sym) * 100

	def bestBuy(self, syms=None):
		mods = self.mods()
		symscore = lambda fs : self.score(fs) - mods[fs]
		fscore = lambda s : symscore(ask("fullSym", s))
		syms = syms or [s[:3] for s in self.syms]
		syms.sort(key=fscore)
		return syms[-1]

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
			mets = ask("metrics", sym)
			if mets["ADX"] > adxlim:
				selling = side == "sell"
				goingup = mets["goingup"]
				if (goingup and selling) or (not goingup and not selling):
					upshifting = mets["upshifting"] = ask("upshifting", sym)
					macdup = mets["macdup"] = mets["macd"] > mets["macdsig"]
					vptup = mets["vptup"] = mets["VPTsmall"] > mets["VPTmedium"]
					mfi = mets["mfi"]
					mets["trade"] = trade
					mets["adxlim"] = adxlim
					mets["mfilim"] = mfibot
					reason = trade["rationale"]["reason"]
					sig = "%s (%s) %s"%(sym, reason, side)
					noticer = strict and self.notice or self.log
					note = lambda n : emit("note", trade, n) or noticer(n, mets)
					signote = lambda n : note("%s %s"%(n, sig))
					if (selling and mfi > mfitop) or (not selling and mfi < mfibot):
						signote("wise (mfi)")
						return "very"
					elif (selling and not macdup) or (not selling and macdup):
						signote("wise (macd)")
						return "very"
					elif (selling and not vptup) or (not selling and vptup):
						signote("approved (vpt)")
					elif (selling and not upshifting) or (not selling and upshifting):
						signote("approved (shifting)")
					else:
						return noticer("unwise %s"%(sig,), mets)
		return True