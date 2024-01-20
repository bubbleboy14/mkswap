import random
from rel.util import ask, emit
from ..backend import log
from .base import Base

ONESWAP = False
VOLATILITY_MULT = 16
VOLATILITY_CUTOFF = 0.5

def setOneSwap(s1):
	log("setOneSwap(%s)"%(s1,))
	global ONESWAP
	ONESWAP = s1

def setVolatilityMult(vmult):
	log("setVolatilityMult(%s)"%(vmult,))
	global VOLATILITY_MULT
	VOLATILITY_MULT = vmult

def setVolatilityCutoff(cutoff):
	log("setVolatilityCutoff(%s)"%(cutoff,))
	global VOLATILITY_CUTOFF
	VOLATILITY_CUTOFF = cutoff

class Slosh(Base):
	def __init__(self, symbol, recommender=None):
		self.top, self.bottom = symbol
		self.syms = [self.bottom[:3], self.top[:3]]
		self.onesym = "".join(self.syms)
		self.onequote = None
		self.shouldUpdate = False
		Base.__init__(self, symbol, recommender)

	def buysell(self, buysym, sellsym, size=10):
		buyprice = ask("bestPrice", buysym, "buy")
		sellprice = ask("bestPrice", sellsym, "sell")
		self.recommender({
			"side": "sell",
			"symbol": sellsym,
			"price": sellprice,
			"amount": round(size / sellprice, 6)
		})
		self.recommender({
			"side": "buy",
			"symbol": buysym,
			"price": buyprice,
			"amount": round(size / buyprice, 6)
		})

	def oneswap(self, size=10):
		side = "buy"
		if size < 0:
			side = "sell"
			size *= -1
		denom = VOLATILITY_MULT * VOLATILITY_MULT / self.onequote # arbitrary
		self.recommender({
			"side": side,
			"symbol": self.onesym,
			"price": self.onequote,
			"amount": round(size / denom, 5)
		})

	def shouldOneSwap(self):
		if ONESWAP != "auto":
			return ONESWAP
		bals = ask("balances")
		for sec in bals:
			s = bals[sec]
			for sym in self.syms:
				if sym == "USD":
					if ask("tooLow", s[sym]):
						return True
				else:
					usdval = ask("getUSD", sym, s[sym])
					if usdval and ask("tooLow", usdval):
						return False
		return random.randint(0, 1)

	def swap(self, size=10):
		if self.shouldOneSwap():
			self.oneswap(size)
		elif size > 0:
			self.buysell(self.bottom, self.top, size)
		else:
			self.buysell(self.top, self.bottom, -size)

	def upStats(self):
		mad = self.stats["mad"] = ask("mad", self.top, self.bottom)
		sigma = self.stats["sigma"] = ask("sigma", self.top, self.bottom)
		self.stats["turb"] = ask("volatility", self.top, self.bottom, mad)
		self.stats["volatility"] = ask("volatility", self.top, self.bottom, sigma)

	def hilo(self):
		self.upStats()
		volatility = self.stats["volatility"]
		if abs(volatility) > VOLATILITY_CUTOFF:
			self.swap(volatility * VOLATILITY_MULT)

	def tick(self, history=None):
		if not self.shouldUpdate:
			return
		self.shouldUpdate = False
		rdata = ask("ratio", self.top, self.bottom, True)
		if not rdata:
			return self.log("skipping tick (waiting for history)")
		self.onequote = round(1 / rdata["current"], 5)
		emit("quote", self.onesym, self.onequote, True)
		if ask("hadEnough", self.top, self.bottom):
			self.hilo()

	def compare(self, symbol, side, price, eobj, history):
		self.shouldUpdate = True
		self.log("compare", symbol, side, price, eobj)
		Base.compare(self, symbol, side, price, eobj, history)