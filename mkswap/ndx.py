from math import sqrt
from rel.util import ask, listen
from .base import Worker
from .observer import Observer
from .config import config

def getSpan(span):
	return config.ndx[span]

SPANS = ["inner", "short", "long", "outer"]
BESTIES = ["short", "long", "outer"]
side2height = {
	"buy": "low",
	"sell": "high"
}

class NDX(Worker):
	def __init__(self):
		self.faves = {}
		self.ratios = {}
		self._volumes = {}
		self.histories = {}
		self.observers = {}
		listen("mad", self.mad)
		listen("fave", self.fave)
		listen("price", self.price)
		listen("quote", self.quote)
		listen("ratio", self.ratio)
		listen("sigma", self.sigma)
		listen("markets", self.markets)
		listen("observe", self.observe)
		listen("hadEnough", self.hadEnough)
		listen("bestPrice", self.bestPrice)
		listen("bestPrices", self.bestPrices)
		listen("volatility", self.volatility)

	def volumes(self):
		vols = self._volumes.copy()
		for v in self._volumes:
			self._volumes[v] = 0
		return vols

	def price(self, symbol, fullSym=False):
		if fullSym:
			symbol = ask("fullSym", symbol)
		if symbol in self.histories:
			return self.histories[symbol]["current"]

	def bestPrice(self, sym, side, span="inner"):
		return round(self.histories[sym][span][side2height[side]], 6)

	def bestPrices(self, sym, side, spans=BESTIES):
		d = {}
		for span in spans:
			d[span] = self.bestPrice(sym, side, span)
		return d

	def markets(self, sym, side="buy"):
		marks = {}
		buyer = []
		seller = []
		for fullSym in self.histories:
			if fullSym.startswith(sym):
				buyer.append(fullSym)
			elif fullSym.endswith(sym):
				seller.append(fullSym)
		if side == "buy":
			marks["buy"] = buyer
			marks["sell"] = seller
		else:
			marks["buy"] = seller
			marks["sell"] = buyer
		return marks

	def observe(self, sym):
		if sym in self.observers:
			return self.log("observe(%s) already observing!"%(sym,))
		self.observers[sym] = Observer(sym,
			observe=lambda e : self.observed(sym, float(e["price"])))

	def observed(self, sym, price):
		self.log("observed(%s@%s)"%(sym, price))
		self.quote(sym, price, True)

	def hadEnough(self, top, bot, span="short"):
		return len(self.ratios[top][bot]["all"]) >= getSpan(span)

	def nowAndThen(self, top, bot):
		rats = self.ratios[top][bot]
		return rats["current"], rats["all"][:-1]

	def mad(self, top, bot, span="short"):
		adiffs = []
		cur, rats = self.nowAndThen(top, bot)
		for r in rats[-getSpan(span):]:
			adiffs.append(abs(r - cur))
		return self.ave(adiffs)

	def sigma(self, top, bot, span="short"):
		sqds = []
		cur, rats = self.nowAndThen(top, bot)
		for r in rats[-getSpan(span):]:
			d = r - cur
			sqds.append(d * d)
		return sqrt(self.ave(sqds))

	def volatility(self, top, bot, sigma, span="short"):
		rstats = self.ratio(top, bot)
		if not sigma:
			return 0
		return (rstats["current"] - rstats[span]) / sigma

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
			for span in SPANS:
				rstats[span] = self.ave(tb, getSpan(span), True)
		return rstats

	def fave(self, key, val):
		self.faves[key] = val

	def quote(self, symbol, price, volume=None, fave=False):
		if symbol not in self.histories:
			self.histories[symbol] = {
				"all": [],
				"inner": {},
				"short": {},
				"long": {},
				"outer": {}
			}
		if volume:
			if symbol not in self._volumes:
				self._volumes[symbol] = 0
			self._volumes[symbol] += volume
		fave and self.fave(symbol, price)
		symhis = self.histories[symbol]
		symhis["current"] = price
		symhis["all"].append(price)
		symhis["average"] = self.ave(symbol)
		for span in SPANS:
			stretch = symhis["all"][-getSpan(span):]
			symhis[span]["high"] = max(stretch)
			symhis[span]["low"] = min(stretch)