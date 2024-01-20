from math import sqrt
from rel.util import listen
from .backend import log
from .base import Worker

INNER = 3
OUTER = 20
LONG = 40

def setInner(inner):
	log("setInner(%s)"%(inner,))
	global INNER
	INNER = inner

def setOuter(outer):
	log("setOuter(%s)"%(outer,))
	global OUTER
	OUTER = outer

def setLong(howlong):
	log("setLong(%s)"%(howlong,))
	global LONG
	LONG = howlong

def getSpan(span):
	return {
		"long": LONG,
		"inner": INNER,
		"outer": OUTER
	}[span]

side2height = {
	"buy": "low",
	"sell": "high"
}

class NDX(Worker):
	def __init__(self):
		self.faves = {}
		self.ratios = {}
		self.histories = {}
		listen("mad", self.mad)
		listen("price", self.price)
		listen("quote", self.quote)
		listen("ratio", self.ratio)
		listen("sigma", self.sigma)
		listen("hadEnough", self.hadEnough)
		listen("bestPrice", self.bestPrice)
		listen("bestPrices", self.bestPrices)
		listen("volatility", self.volatility)

	def price(self, symbol):
		if symbol in self.histories:
			return self.histories[symbol]["current"]

	def bestPrice(self, sym, side, span="inner"):
		return round(self.histories[sym][span][side2height[side]], 6)

	def bestPrices(self, sym, side):
		d = {}
		for span in ["inner", "outer", "long"]:
			d[span] = self.bestPrice(sym, side, span)
		return d

	def hadEnough(self, top, bot, span="outer"):
		return len(self.ratios[top][bot]["all"]) >= getSpan(span)

	def nowAndThen(self, top, bot):
		rats = self.ratios[top][bot]
		return rats["current"], rats["all"][:-1]

	def mad(self, top, bot):
		adiffs = []
		cur, rats = self.nowAndThen(top, bot)
		for r in rats[-OUTER:]:
			adiffs.append(abs(r - cur))
		return self.ave(adiffs)

	def sigma(self, top, bot):
		sqds = []
		cur, rats = self.nowAndThen(top, bot)
		for r in rats[-OUTER:]:
			d = r - cur
			sqds.append(d * d)
		return sqrt(self.ave(sqds))

	def volatility(self, top, bot, sigma):
		rstats = self.ratio(top, bot)
		if not sigma:
			return 0
		return (rstats["current"] - rstats["outer"]) / sigma

	def ave(self, symbol, limit=None, ratio=False):
		if ratio:
			top, bot = symbol
			rats = self.ratios[top][bot]["all"]
		elif type(symbol) is list:
			rats = symbol
		else:
			rats = self.histories[symbol]["all"]
		if limit:
			rats = rats[-limit:]
		return sum(rats) / len(rats)

	def ratio(self, top, bot, update=False):
		lpref = "ratio(%s/%s)"%(top, bot)
		if top not in self.histories or bot not in self.histories:
			return self.log("%s not ready - check back later"%(lpref,))
		if top not in self.ratios:
			self.ratios[top] = {}
		if bot not in self.ratios[top]:
			self.ratios[top][bot] = {
				"all": []
			}
		rstats = self.ratios[top][bot]
		if update:
			tb = [top, bot]
			rat = self.price(top) / self.price(bot)
			if "current" not in rstats:
				rstats["current"] = rstats["high"] = rstats["low"] = rat
			else:
				rstats["current"] = rat
				if rat > rstats["high"]:
					rstats["high"] = rat
				elif rat < rstats["low"]:
					rstats["low"] = rat
			rstats["all"].append(rat)
			rstats["total"] = self.ave(tb, ratio=True)
			for span in ["inner", "outer", "long"]:
				rstats[span] = self.ave(tb, getSpan(span), True)
		return rstats

	def quote(self, symbol, price, fave=False):
		if symbol not in self.histories:
			self.histories[symbol] = {
				"all": [],
				"long": {},
				"outer": {},
				"inner": {}
			}
		if fave:
			self.faves[symbol] = price
		symhis = self.histories[symbol]
		symhis["current"] = price
		symhis["all"].append(price)
		symhis["average"] = self.ave(symbol)
		for span in ["inner", "outer", "long"]:
			stretch = symhis["all"][-getSpan(span):]
			symhis[span]["high"] = max(stretch)
			symhis[span]["low"] = min(stretch)