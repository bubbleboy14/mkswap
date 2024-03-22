from math import sqrt
from rel.util import ask, emit
from .base import Worker

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
		if sym not in self.candles:
			self.candles[sym] = cans
			self.fcans[sym] = []
		else:
			self.candles[sym] += cans
			self.fcans[sym] += cans

	def updateOBV(self, sym, cans):
		if sym in self.candles:
			last = self.candles[sym][-1]
			oprice = last["close"]
			obv = last["obv"]
		else:
			oprice = cans[0]["close"]
			obv = cans[0]["volume"]
		for can in cans:
			volume = can["volume"]
			price = can["close"]
			if price > oprice:
				can["obv"] = obv + volume
			elif price < oprice:
				can["obv"] = obv - volume
			else: # price == oprice:
				can["obv"] = obv
			oprice = can["close"]
			obv = can["obv"]

	def oldCandles(self):
		cans = {}
		for sym in self.candles:
			cans[sym] = self.candles[sym][-10:]
		return cans

	def freshCandles(self):
		cans = {}
		for sym in self.fcans:
			cans[sym] = self.fcans[sym]
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

	def hints(self, vscores):
		for sym in vscores:
			if sym not in self.ratios:
				self.ratios[sym] = {
					"history": []
				}
				emit("mfsub", sym, lambda c : self.candle(c, sym), "candles_1m")
			if not vscores[sym]["bid"]:
				continue
			rat = vscores[sym]["ask"] / vscores[sym]["bid"]
			if self.ratios[sym]["history"]:
				self.ratios[sym]["sigma"] = self.sigma(sym, rat)
				if self.ratios[sym]["sigma"]:
					vol = self.ratios[sym]["volatility"] = self.volatility(sym, rat)
					if vol > 0.5:
						self.predictions[sym] = "buy"
					elif vol < -0.5:
						self.predictions[sym] = "sell"
					else:
						self.predictions[sym] = "chill"
			self.ratios[sym]["history"].append(rat)
		return self.predictions