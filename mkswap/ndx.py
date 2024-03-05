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
		self.orders = {}
		self._volumes = {}
		self.observers = {}
		self.orderBook = {}
		self.histories = { "trade": {}, "ask": {}, "bid": {} }
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
		listen("observersReady", self.observersReady)
		listen("updateOrderBook", self.updateOrderBook)

	def updateOrderBook(self, symbol, event):
		if symbol not in self.orders:
			self.orders[symbol] = {}
			self.orderBook[symbol] = { "bid": {}, "ask": {} }
		side = event["side"]
		price = float(event["price"])
		self.orderBook[symbol][side][price] = float(event["remaining"])
		self.orders[symbol][side] = price
		self.incVol(symbol, float(event["delta"]))

	def volumes(self):
		vols = self._volumes.copy()
		for v in self._volumes:
			self._volumes[v] = 0
		return vols

	def price(self, symbol, fullSym=False, history="trade"):
		if fullSym:
			symbol = ask("fullSym", symbol)
		if symbol in self.histories[history]:
			return self.histories[history][symbol]["current"]

	def bestPrice(self, sym, side, span="inner", history="trade"):
		return round(self.histories[history][sym][span][side2height[side]], 6)

	def bestPrices(self, sym, side, spans=BESTIES, history="trade"):
		d = {}
		for span in spans:
			d[span] = self.bestPrice(sym, side, span, history)
		return d

	def markets(self, sym, side="buy", history="trade"):
		marks = {}
		buyer = []
		seller = []
		for fullSym in self.histories[history]:
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
			observe=lambda e : self.observed(sym, float(e["price"]), float(e["amount"])))

	def observed(self, sym, price, volume, history="trade"):
		config.base.unspammed or self.log("observed(%s %s %s @ %s)"%(volume, sym, history, price))
		self.quote(sym, price, volume=volume, fave=True, history=history)

	def observersReady(self, history="trade"):
		for sym in self.observers:
			if sym not in self.histories[history]:
				self.log("no", history, "history for", sym, "!!!!!")
				return False
		return True

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

	def ave(self, symbol, limit=None, ratio=False, history="trade"):
		if ratio:
			top, bot = symbol
			rats = self.ratios[top][bot]["all"]
		elif type(symbol) is list:
			rats = symbol
		else:
			rats = self.histories[history][symbol]["all"]
		if limit:
			rats = rats[-limit:]
		return sum(rats) / len(rats)

	def ratio(self, top, bot, update=False, history="trade"):
		lpref = "ratio(%s/%s)"%(top, bot)
		hists = self.histories[history]
		if top not in hists or bot not in hists:
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
			rat = self.price(top, history=history) / self.price(bot, history=history)
			if "current" not in rstats:
				rstats["current"] = rstats["high"] = rstats["low"] = rat
			else:
				rstats["current"] = rat
				if rat > rstats["high"]:
					rstats["high"] = rat
				elif rat < rstats["low"]:
					rstats["low"] = rat
			rstats["all"].append(rat)
			rstats["total"] = self.ave(tb, ratio=True, history=history)
			for span in SPANS:
				rstats[span] = self.ave(tb, getSpan(span), True, history)
		return rstats

	def fave(self, key, val):
		self.faves[key] = val

	def incVol(self, symbol, volume):
		if symbol not in self._volumes:
			self._volumes[symbol] = 0
		self._volumes[symbol] += volume

	def quote(self, symbol, price, volume=None, fave=False, history="trade"):
		hists = self.histories[history]
		if symbol not in hists:
			hists[symbol] = {
				"all": [],
				"inner": {},
				"short": {},
				"long": {},
				"outer": {}
			}
		volume and self.incVol(symbol, volume)
		fave and self.fave(symbol, price)
		symhis = hists[symbol]
		symhis["current"] = price
		symhis["all"].append(price)
		symhis["average"] = self.ave(symbol, history=history)
		for span in SPANS:
			stretch = symhis["all"][-getSpan(span):]
			symhis[span]["high"] = max(stretch)
			symhis[span]["low"] = min(stretch)