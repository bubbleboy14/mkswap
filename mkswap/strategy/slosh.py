from rel.util import ask, emit
from .base import Base
from ..config import config

scfg = config.strategy.slosh

class Slosh(Base):
	def __init__(self, symbol, recommender=None):
		self.top, self.bottom = symbol
		self.syms = [self.top[:3], self.bottom[:3]]
		self.onesym = "".join(self.syms)
		self.ratsym = "/".join(self.syms)
		self.shouldUpdate = False
		emit("observe", self.onesym)
		emit("tellMeWhen", self.onesym, "volatility", scfg.vcutoff, self.hardsell)
		emit("tellMeWhen", self.onesym, "volatility", -scfg.vcutoff, self.hardbuy)
		Base.__init__(self, symbol, recommender)

	def hardsell(self):
		self.notice("hardsell!", ask("bestTrades", self.onesym, "sell", force=True))

	def hardbuy(self):
		self.notice("hardbuy!", ask("bestTrades", self.onesym, "buy", force=True))

	def buysell(self, buysym, sellsym, size=10):
		buyprice = ask("bestPrice", buysym, "buy")
		sellprice = ask("bestPrice", sellsym, "sell")
		self.recommender({
			"side": "sell",
			"symbol": sellsym,
			"price": sellprice,
			"amount": size / sellprice
		})
		self.recommender({
			"side": "buy",
			"symbol": buysym,
			"price": buyprice,
			"amount": size / buyprice
		})

	def oneswap(self, side, size=10):
		vmult = config.strategy.slosh.vmult
		price = ask("bestPrice", self.onesym, side)
		denom = vmult * vmult / price # arbitrary
		self.recommender({
			"side": side,
			"price": price,
			"symbol": self.onesym,
			"amount": size / denom
		})

	def shouldOneSwap(self, side):
		bias = self.stats["bias"]
		bigone = bias > 0
		if scfg.oneswap != "auto":
			return scfg.oneswap
		bals = ask("balances")
		for sec in bals:
			s = bals[sec]
			for sym in self.syms:
				if sym == "USD":
					if ask("tooLow", s[sym]):
						return True
				else:
					usdval = ask("getUSD", ask("fullSym", sym), s[sym])
					if usdval and ask("tooLow", usdval):
						return False
		if abs(bias) < scfg.randlim:
			return "both"
		if side == "buy":
			return not bigone
		return bigone

	def swap(self, size=10):
		side = "sell"
		if size < 0:
			size *= -1
			side = "buy"
		shouldOne = self.shouldOneSwap(side)
		shouldOne and self.oneswap(side, size)
		if not shouldOne or shouldOne == "both":
			if side == "sell":
				self.buysell(self.bottom, self.top, size)
			else:
				self.buysell(self.top, self.bottom, size)

	def upStats(self):
		mad = self.stats["mad"] = ask("rmad", self.top, self.bottom)
		sigma = self.stats["sigma"] = ask("rsigma", self.top, self.bottom)
		self.stats["turb"] = ask("rvolatility", self.top, self.bottom, mad)
		self.stats["volatility"] = ask("rvolatility", self.top, self.bottom, sigma)
		self.stats["bias"] = (ask("price", self.onesym) / ask("price", self.ratsym)) - 1

	def hilo(self):
		self.upStats()
		volatility = self.stats["volatility"]
		if abs(volatility) + abs(self.stats["bias"]) > scfg.vcutoff:
			self.swap(volatility * scfg.vmult)

	def tick(self, history=None):
		if not self.shouldUpdate:
			return
		self.shouldUpdate = False
		if ask("hadEnough", self.top, self.bottom):
			self.hilo()

	def compare(self, symbol, side, price, eobj, history):
		self.shouldUpdate = True
		self.log("compare", symbol, side, price, eobj)
		Base.compare(self, symbol, side, price, eobj, history)
		rdata = ask("ratio", self.top, self.bottom, True)
		if not rdata:
			return self.log("skipping ratio (waiting for history)")
		ratcur = round(rdata["current"], 5) # occasionally rounds to 0...
		ratcur and emit("quote", self.ratsym, ratcur, fave=True)
