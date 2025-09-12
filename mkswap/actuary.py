from rel.util import ask, emit, listen
from .base import Worker
from .config import config

PERIODS = ["fast", "slow"]
TERMS = ["small", "medium", "large", "jumbo"]
SVALS = ["vpt", "OBVslope", "ADslope"] # not currently used
METRICS = ["ADX", "+DI", "-DI", "mfi", "macd", "macdsig", "VPTsmall", "VPTmedium"]

class Actuary(Worker):
	def __init__(self):
		self.ratios = {}
		self.candles = {}
		self.fcans = {}
		self.predictions = {}
		self.wheners = {}
		listen("range", self.range)
		listen("metric", self.latest)
		listen("metrics", self.metrics)
		listen("strength", self.strength)
		listen("overunders", self.overunders)
		listen("tellMeWhen", self.tellMeWhen)

	def range(self, symbol):
		vals = [self.latest(symbol, r) for r in TERMS]
		robj = {
			"short": vals[0],
			"long": vals[-1]
		}
		vals.sort()
		robj["low"] = vals[0]
		robj["high"] = vals[-1]
		robj["span"] = robj["high"] - robj["low"]
		self.log("range(%s)"%(symbol,), robj)
		return robj

	def overunder(self, sym, cb):
		mfi = lambda : "mfi: %s"%(self.latest(sym, "mfi"),)
		under = lambda : cb("buy", sym, "undersold", mfi())
		over = lambda : cb("sell", sym, "overheated", mfi())
		self.tellMeWhen(sym, "trajectory", "overheated", over)
		self.tellMeWhen(sym, "trajectory", "undersold", under)

	def overunders(self, syms, cb):
		for sym in syms:
			self.overunder(sym, cb)

	def tellMeWhen(self, symbol, metric, threshold, cb):
		if symbol not in self.wheners:
			self.wheners[symbol] = {}
		if metric not in self.wheners[symbol]:
			self.wheners[symbol][metric] = {}
		if threshold not in self.wheners[symbol][metric]:
			self.wheners[symbol][metric][threshold] = []
		self.log("tellMeWhen(%s, %s, %s)"%(symbol, metric, threshold))
		self.wheners[symbol][metric][threshold].append(cb)

	def tellWheners(self, sym):
		if sym not in self.wheners: return
		cans = self.candles[sym]
		wcfg = self.wheners[sym]
		rest, cur = cans[:-1], cans[-1]
		curclose = cur["close"]
		if "price" in wcfg:
			prev = rest[-1]
			diff = 1 - prev["close"] / curclose # TODO: derive/use average instead?
			emit("fave", "%spdiff"%(sym,), diff)
			self.thresh(sym, "price", diff)
		if "volatility" in wcfg:
			closers = list(map(lambda c : c["close"], rest))
			sig = ask("sigma", curclose, closers)
			vol = cur["volatility"] = ask("volatility", curclose, ask("ave", closers), sig)
			emit("fave", "%scsig"%(sym,), sig)
			emit("fave", "%scvol"%(sym,), vol)
			self.thresh(sym, "volatility", vol)
		if "trajectory" in wcfg:
			self.thresh(sym, "trajectory", cur["trajectory"])

	def thresh(self, sym, prop, comp):
		strcmp = type(comp) is str
		pcfg = self.wheners[sym][prop]
		numthresh = lambda t : (t < 0 and comp < t) or (t > 0 and comp > t)
		trig = lambda t : (t == comp) if strcmp else numthresh(t)
		for threshold in pcfg:
			self.log("checking", sym, prop, "threshold", threshold, "against", comp)
			if trig(threshold):
				for cb in pcfg[threshold]:
					cb()

	def candle(self, candles, sym):
		clen = len(candles)
		self.log("CANDLES!", sym, clen)
		cans = list(map(self.fixcan, candles))
		clen == 1 and self.log("candle:", cans)
		cans.reverse()
		self.updateOBV(sym, cans)
		self.updateVPT(sym, cans)
		self.updateAD(sym, cans)
		self.updateMF(sym, cans)
		prev = None
		if sym in self.candles:
			prev = self.candles[sym][-1]
		else:
			self.candles[sym] = []
			self.fcans[sym] = []
		for can in cans[:-1]:
			self.addCan(can, sym, prev)
			prev = can
		self.addCan(cans[-1], sym, prev, True)
		self.tellWheners(sym)

	def addCan(self, candle, sym, prev=None, check=False):
		self.updateMFI(candle, sym)
		self.fcans[sym].append(candle)
		canhist = self.candles[sym]
		canhist.append(candle)
		self.perStretch(canhist,
			lambda term, hist : self.updateMovings(candle, term, hist))
		self.perStretch(canhist,
			lambda term, hist : self.updateExMovings(candle, term, hist), PERIODS)
		self.updateMACD(candle, sym)
		if prev:
			self.updateADX(prev, candle, sym)
			if check:
				self.compare(prev, candle, sym)
				self.compare(prev, candle, sym, "VPT")
				self.crossCheck(sym, prev, candle, "+DI", "-DI", "ADX")
				self.crossCheck(sym, prev, candle, "macd", "macdsig", "MACD")
				self.setTrajectory(candle, sym)

	def setTrajectory(self, candle, sym):
		if candle["ADX"] > 25:
			goingup = candle["+DI"] > candle["-DI"]
			mfi = candle["mfi"]
			if goingup:
				if mfi > 80:
					candle["trajectory"] = "overheated"
				else:
					candle["trajectory"] = "up"
			else:
				if mfi < 20:
					candle["trajectory"] = "undersold"
				else:
					candle["trajectory"] = "down"
		else:
			candle["trajectory"] = "calm"
		self.notice("%s %s"%(sym, candle["trajectory"]))

	def crossCheck(self, sym, c1, c2, t1, t2, pref=None):
		if c1[t1] < c1[t2] and c2[t1] > c2[t2]:
			emit("cross", sym, "golden", "%s above %s"%(t1, t2), pref)
		elif c1[t1] > c1[t2] and c2[t1] < c2[t2]:
			emit("cross", sym, "death", "%s below %s"%(t1, t2), pref)

	def compare(self, c1, c2, sym, pref=None):
		terms = list(pref and map(lambda t : pref + t, TERMS) or TERMS)
		pref = pref or "price"
		t1 = terms.pop(0)
		while terms:
			for t2 in terms:
				self.crossCheck(sym, c1, c2, t1, t2, pref)
			t1 = terms.pop(0)

	def ave(self, hist, prop="close", op="ave", limit=None, filt=False):
		if filt:
			hist = filter(lambda h : prop in h, hist)
		return ask(op, list(map(lambda h : h[prop], hist)), limit)

	def updateMovings(self, candle, term, hist):
		candle[term] = self.ave(hist)
		candle["VPT" + term] = self.ave(hist, "vpt")

	def updateExMovings(self, candle, term, hist):
		candle["ema" + term] = self.ave(hist, op="ema")

	def perTerm(self, cb, terms=TERMS):
		for term in terms:
			cb(term, config.actuary[term])

	def perStretch(self, hist, cb, terms=TERMS):
		self.perTerm(lambda tname, tnum : cb(tname, hist[-tnum:]), terms)

	def updateADX(self, prev, can, sym):
		r = config.actuary.range
		cans = self.candles[sym][-r:]
		can["+DM"] = can["-DM"] = can["+DI"] = can["-DI"] = can["DX"] = 0
		mneg = prev["low"] - can["low"]
		mpos = can["high"] - prev["high"]
		if mneg > mpos and mneg > 0:
			can["-DM"] = mneg
		elif mpos > mneg and mpos > 0:
			can["+DM"] = mpos
		can["DM"] = max(can["+DM"], can["-DM"])
		can["TR"] = max(can["high"] - can["low"],
			abs(can["high"] - prev["close"]), abs(can["low"] - prev["close"]))
		can["ATR"] = self.ave(cans, "TR", filt=True)
		can["-ADM"] = self.ave(cans, "-DM", filt=True)
		can["+ADM"] = self.ave(cans, "+DM", filt=True)
		if can["ATR"]:
			can["+DI"] = 100 * can["+ADM"] / can["ATR"]
			can["-DI"] = 100 * can["-ADM"] / can["ATR"]
			divisor = can["+DI"] + can["-DI"]
			if divisor:
				can["DX"] = abs(100 * (can["+DI"] - can["-DI"]) / divisor)
		if len(cans) < r:
			return
		if "ADX" in prev:
			can["ADX"] = (prev["ADX"] * (r - 1) + can["DX"]) / r
		else:
			can["ADX"] = self.ave(cans, "DX", filt=True)

	def updateMACD(self, candle, sym):
		candle["macd"] = candle["emafast"] - candle["emaslow"]
		candle["macdsig"] = self.ave(self.candles[sym], "macd", "ema", config.actuary.sig)
		candle["macdhist"] = candle["macd"] - candle["macdsig"]

	def updateMFI(self, candle, sym):
		pos = 0
		neg = 0
		for can in self.candles[sym][-config.actuary.range:]:
			f = can["flow"]
			if f > 0:
				pos += f
			else:
				neg -= f
		mfr = neg and pos / neg or 1 # does this make sense?
		candle["mfi"] = 100 - 100 / (1 + mfr)

	def updateMF(self, sym, cans):
		typ = sym in self.candles and self.candles[sym][-1]["typical"] or 0
		for can in cans:
			can["typical"] = (can["high"] + can["low"] + can["close"]) / 3
			can["flow"] = can["typical"] * can["volume"]
			if can["typical"] < typ:
				can["flow"] *= -1
			typ = can["typical"]

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
		return sym in self.candles and self.candles[sym][-1][prop] or 0

	def score_nah(self, sym):
		score = self.ratios[sym].get("volatility", 0)
		for prop in SVALS:
			score += self.latest(sym, prop)
		score += (self.latest(sym, "mfi") / 25) - 2
		return score

	def metrics(self, sym):
		mets = {}
		for met in METRICS:
			mets[met] = self.latest(sym, met)
		mets["goingup"] = mets["+DI"] > mets["-DI"]
		return mets

	def strength(self, sym):
		vol = self.ratios.get(sym, {}).get("volatility", 0)
		mets = self.metrics(sym)
		score = mets["ADX"] / 100
		mfi = mets["mfi"]
		goingup = mets["goingup"]
		if not goingup:
			score *= -1
		if (goingup and mfi > 80) or (not goingup and mfi < 20):
			score *= -1
		score += vol / 10
		return score

	def scores(self):
		scores = {}
		for sym in self.candles:
			scores[sym] = self.strength(sym)
		return scores

	def oldCandles(self, limit=10, mod=0):
		cans = {}
		if mod:
			limit = limit * mod
		for sym in self.candles:
			cans[sym] = self.candles[sym][-limit:]
			if mod:
				cans[sym].reverse()
				cans[sym] = cans[sym][::mod]
				cans[sym].reverse()
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

	def volatilities(self):
		vols = {}
		for sym in self.ratios:
			vols[sym] = self.ratios[sym].get("volatility", 0)
		return vols

	def initRatios(self, sym):
		if sym not in self.ratios:
			self.ratios[sym] = {
				"history": []
			}
			emit("mfsub", sym, lambda c : self.candle(c, sym), "candles_%s"%(config.actuary.int,))

	def hints(self, vscores):
		for sym in vscores:
			self.initRatios(sym)
			if not vscores[sym]["bid"]:
				continue
			rat = vscores[sym]["ask"] / vscores[sym]["bid"]
			rdata = self.ratios[sym]
			rhist = rdata["history"]
			if rhist:
				sig = rdata["sigma"] = ask("sigma", rat, rhist)
				if sig:
					rdata["volatility"] = ask("volatility", rat, ask("ave", rhist), sig)
					score = self.strength(sym)
					if score > 0.5:
						self.predictions[sym] = "buy"
						emit("hint", sym, "buy", score)
					elif score < -0.5:
						self.predictions[sym] = "sell"
						emit("hint", sym, "sell", score)
					else:
						self.predictions[sym] = "chill"
			rhist.append(rat)
		return self.predictions