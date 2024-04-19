from math import sqrt
from rel.util import ask, emit
from .base import Worker
from .config import config

TERMS = ["small", "medium", "large"]
SVALS = ["vpt", "OBVslope", "ADslope"]

class Actuary(Worker):
	def __init__(self):
		self.ratios = {}
		self.candles = {}
		self.fcans = {}
		self.predictions = {}

	def candle(self, candles, sym):
		clen = len(candles)
		self.log("CANDLES!", sym, clen)
		cans = list(map(self.fixcan, candles))
		clen == 1 and self.log("candle:", cans)
		cans.reverse()
		self.updateOBV(sym, cans)
		self.updateVPT(sym, cans)
		self.updateAD(sym, cans)
		prev = None
		if sym in self.candles:
			prev = self.candles[sym][-1]
		else:
			self.candles[sym] = []
			self.fcans[sym] = []
		for can in cans:
			self.addCan(can, sym, prev)
			prev = can

	def addCan(self, candle, sym, prev=None):
		self.fcans[sym].append(candle)
		canhist = self.candles[sym]
		canhist.append(candle)
		self.perStretch(canhist,
			lambda term, hist : self.updateMovings(candle, term, hist))
		if prev:
			self.compare(prev, candle, sym)
			self.compare(prev, candle, sym, "VPT")

	def compare(self, c1, c2, sym, pref=None):
		terms = list(pref and map(lambda t : pref + t, TERMS) or TERMS)
		t1 = terms.pop(0)
		while terms:
			for t2 in terms:
				if c1[t1] < c1[t2] and c2[t1] > c2[t2]:
					emit("cross", sym, "golden", "%s above %s"%(t1, t2), pref)
				elif c1[t1] > c1[t2] and c2[t1] < c2[t2]:
					emit("cross", sym, "death", "%s below %s"%(t1, t2), pref)
			t1 = terms.pop(0)

	def updateMovings(self, candle, term, hist):
		candle[term] = ask("ave", list(map(lambda h : h["close"], hist)))
		candle["VPT" + term] = ask("ave", list(map(lambda h : h["vpt"], hist)))

	def perTerm(self, cb):
		for term in TERMS:
			cb(term, config.actuary[term])

	def perStretch(self, hist, cb):
		self.perTerm(lambda tname, tnum : cb(tname, hist[-tnum:]))

	def updateVPT(self, sym, cans):
		if sym in self.candles:
			last = self.candles[sym][-1]
			oprice = last["close"]
			vpt = last["vpt"]
		else:
			oprice = cans[0]["close"]
			vpt = 0#cans[0]["volume"]
		for can in cans:
			volume = can["volume"]
			price = can["close"]
			vpt = can["vpt"] = vpt + volume * (price - oprice) / oprice
			oprice = price

	def updateAD(self, sym, cans):
		ad = sym in self.candles and self.candles[sym][-1]["ad"] or 0
		for can in cans:
			low = can["low"]
			high = can["high"]
			close = can["close"]
			volume = can["volume"]
			hldiff = high - low
			slope = 0
			if hldiff:
				mult = ((close - low) - (high - close)) / hldiff
				slope = mult * volume
				ad += slope
			can["ad"] = ad
			can["ADslope"] = slope

	def updateOBV(self, sym, cans):
		if sym in self.candles:
			last = self.candles[sym][-1]
			oprice = last["close"]
			obv = last["obv"]
		else:
			oprice = cans[0]["close"]
			obv = 0#cans[0]["volume"]
		for can in cans:
			volume = can["volume"]
			price = can["close"]
			slope = 0
			if price > oprice:
				slope = volume
			elif price < oprice:
				slope = -volume
			obv += slope
			oprice = price
			can["obv"] = obv
			can["OBVslope"] = slope

	def latest(self, sym, prop):
		symcans = self.candles[sym]
		return symcans and symcans[-1][prop] or 0

	def score(self, sym):
		score = self.ratios[sym]["volatility"]
		for prop in SVALS:
			score += self.latest(sym, prop)
		return score

	def oldCandles(self, limit=10):
		cans = {}
		for sym in self.candles:
			cans[sym] = self.candles[sym][-limit:]
		return cans

	def freshCandles(self):
		cans = {}
		for sym in self.fcans:
			cans[sym] = self.fcans[sym][-10:]
			self.fcans[sym] = []
		return cans

	def fixcan(self, candle):
		return {
			"timestamp": candle[0],
			"open": candle[1],
			"high": candle[2],
			"low": candle[3],
			"close": candle[4],
			"volume": candle[5]
		}

	def sigma(self, symbol, cur):
		hist = self.ratios[symbol]["history"]
		sqds = []
		for rat in hist:
			d = rat - cur
			sqds.append(d * d)
		return sqrt(ask("ave", sqds))

	def volatility(self, symbol, cur):
		rdata = self.ratios[symbol]
		return (cur - ask("ave", rdata["history"])) / rdata["sigma"]

	def volatilities(self):
		vols = {}
		for sym in self.ratios:
			if "volatility" in self.ratios[sym]:
				vols[sym] = self.ratios[sym]["volatility"]
		return vols

	def initRatios(self, sym):
		if sym not in self.ratios:
			self.ratios[sym] = {
				"history": []
			}
			emit("mfsub", sym, lambda c : self.candle(c, sym), "candles_1m")

	def hints(self, vscores):
		for sym in vscores:
			self.initRatios(sym)
			if not vscores[sym]["bid"]:
				continue
			rat = vscores[sym]["ask"] / vscores[sym]["bid"]
			if self.ratios[sym]["history"]:
				self.ratios[sym]["sigma"] = self.sigma(sym, rat)
				if self.ratios[sym]["sigma"]:
					self.ratios[sym]["volatility"] = self.volatility(sym, rat)
					score = self.score(sym)
					if score > 0.5:
						self.predictions[sym] = "buy"
					elif score < -0.5:
						self.predictions[sym] = "sell"
					else:
						self.predictions[sym] = "chill"
			self.ratios[sym]["history"].append(rat)
		return self.predictions