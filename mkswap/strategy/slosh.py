from math import sqrt
from ..backend import log, emit
from .base import Base, INNER, OUTER, LONG

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
		self.onesym = self.bottom[:3] + self.top[:3]
		self.onequote = None
		self.ratios = {
			"current": None,
			"high": None,
			"low": None
		}
		self.averages = {
			"total": None,
			"inner": None,
			"outer": None,
			"long": None
		}
		self.allratios = []
		self.shouldUpdate = False
		Base.__init__(self, symbol, recommender)

	def status(self):
		return {
			"ratios": self.ratios,
			"averages": self.averages
		}

	def buysell(self, buysym, sellsym, size=10):
		buyprice = self.bestPrice(buysym, "buy")
		sellprice = self.bestPrice(sellsym, "sell")
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

	def swap(self, size=10):
		if ONESWAP:
			self.oneswap(size)
		elif size > 0:
			self.buysell(self.bottom, self.top, size)
		else:
			self.buysell(self.top, self.bottom, -size)

	def sigma(self):
		sqds = []
		cur = self.allratios[-1]
		for r in self.allratios[-OUTER:-1]:
			d = r - cur
			sqds.append(d * d)
		return sqrt(self.ave(collection=sqds))

	def volatility(self, cur, sigma):
		if sigma:
			return (cur - self.averages["outer"]) / sigma
		print("sigma is 0 - volatility() returning 0")
		return 0

	def hilo(self, cur):
		rz = self.ratios
		az = self.averages
		sigma = self.sigma()
		volatility = self.volatility(cur, sigma)
		emit("quote", "sigma", sigma)
		emit("quote", "volatility", volatility)
		emit("quote", "turb", sigma * sqrt(min(OUTER, len(self.allratios))))
		print("\n\nsigma", sigma,
			"\nvolatility", volatility,
			"\ncurrent", cur,
			"\naverage", az["total"],
			"\ndifference", cur - az["total"], "\n\n")
		rz["current"] = cur
		if cur > rz["high"]:
			self.log("ratio is new high:", cur)
			rz["high"] = cur;
		elif cur < rz["low"]:
			self.log("ratio is new low:", cur)
			rz["low"] = cur;
		if abs(volatility) > VOLATILITY_CUTOFF:
			self.swap(volatility * VOLATILITY_MULT)

	def tick(self, history=None):
		history = self.histories
		if not self.shouldUpdate:
			return
		self.shouldUpdate = False
		if self.top not in history or self.bottom not in history:
			return self.log("skipping tick (waiting for history)")
		cur = history[self.top]["current"] / history[self.bottom]["current"]
		self.allratios.append(cur)
		self.onequote = round(1 / cur, 5)
		emit("quote", self.onesym, self.onequote)
		self.averages["total"] = self.ave()
		self.averages["inner"] = self.ave(INNER)
		self.averages["outer"] = self.ave(OUTER)
		self.averages["long"] = self.ave(LONG)
		if not self.ratios["current"]:
			self.ratios["current"] = self.ratios["high"] = self.ratios["low"] = cur
		elif len(self.allratios) >= OUTER:
			self.hilo(cur)
		self.log(self.ratios, "\n", self.averages)

	def compare(self, symbol, side, price, eobj, history):
		self.shouldUpdate = True
		self.log("compare", symbol, side, price, eobj)
		Base.compare(self, symbol, side, price, eobj, history)