from math import sqrt
from rel.util import emit, listen
from ..backend import log
from .base import Base, INNER, OUTER, LONG

VOLATILITY_MULT = 8
VOLATILITY_CUTOFF = 0.5

def setVolatilityMult(vmult):
	log("setVolatilityMult(%s)"%(vmult,))
	global VOLATILITY_MULT
	VOLATILITY_MULT = vmult

def setVolatilityCutoff(cutoff):
	log("setVolatilityCutoff(%s)"%(cutoff,))
	global VOLATILITY_CUTOFF
	VOLATILITY_CUTOFF = cutoff

side2height = {
	"buy": "low",
	"sell": "high"
}

class Slosh(Base):
	def __init__(self, symbol, recommender=None):
		self.top, self.bottom = symbol
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
		self.histories = {}
		self.shouldUpdate = False
		listen("best", self.bestPrice)
		Base.__init__(self, symbol, recommender)

	def bestPrice(self, sym, side):
		return round(self.histories[sym][side2height[side]], 6)

	def status(self):
		return {
			"ratios": self.ratios,
			"averages": self.averages
		}

	def ave(self, limit=None, collection=None):
		rats = collection or self.allratios
		if limit:
			rats = rats[-limit:]
		return sum(rats) / len(rats)

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

	def swap(self, size=10):
		if size > 0:
			self.buysell(self.bottom, self.top, size)
		else:
			self.buysell(self.top, self.bottom, -size)

	def sigma(self):
		sqds = []
		cur = self.allratios[-1]
		for r in self.allratios[-INNER:-1]:
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
		if symbol not in self.histories:
			self.histories[symbol] = {
				"all": []
			}
		symhis = self.histories[symbol]
		symhis["current"] = price
		symhis["all"].append(price)
		symhis["average"] = self.ave(collection=symhis["all"])
		inner = symhis["all"][-INNER:]
		symhis["high"] = max(inner)
		symhis["low"] = min(inner)
		emit("priceChange")