import rel
from rel.util import ask, listen
from .base import Worker
from .config import config

class Balancer(Worker):
	def __init__(self):
		self.defills = 0
		self.refills = []
		self.refillCount = 0
		listen("tooLow", self.tooLow)
		rel.timeout(config.balancer.int, self.measure)

	def status(self):
		return {
			"refills": self.refillCount,
			"defills": self.defills
		}

	def measure(self):
		if config.balancer.balance and ask("accountsReady"):
			self.balance(ask("balances", mode="tri"))
		return True

	def balance(self, balances):
		abals = balances["actual"]
		avbals = balances["available"]
		tbals = balances["theoretical"]
		smalls = {}
		bigs = []
		lows = []
		highness = 0
		for sym in abals:
			isusd = sym == "USD"
			avbal = avbals[sym]
			abal = abals[sym]
			tbal = tbals[sym]
			if not isusd:
				if sym == "diff":
					continue
				fs = ask("fullSym", sym)
				avbal = ask("getUSD", fs, avbal)
				abal = ask("getUSD", fs, abal)
				tbal = ask("getUSD", fs, tbal)
				if abal is None:
					self.log("no balance for", fs)
					continue
			lowness = max(self.tooLow(abal), self.tooLow(tbal, True), self.tooLow(avbal, isusd))
			if lowness:
				lows.append(sym)
				if not self.tooHigh(abal) and not self.tooHigh(tbal):
					smalls[sym] = lowness
			else:
				bigs.append(sym)
				if isusd:
					umax = ask("usdcap", config.balancer.usdmax)
					highness = max(self.tooHigh(avbal, umax), self.tooHigh(abal + tbal, umax * 3))
					highness = min(highness, avbal * 0.9)
		for sym in smalls:
			self.refillCount += 1
			self.refills.append(self.orderBalance(sym, smalls[sym], bigs))
		if highness:
			self.defills += 1
			syms = list(smalls.keys()) or lows or list(filter(lambda s : s != "USD", bigs))
			lowests = [ask("bestBuy", syms)]
			self.refills.append(self.orderBalance("USD", highness, lowests, "sell"))

	def getRefills(self):
		refs = self.refills
		self.refills = []
		return refs

	def tooLow(self, bal, double=False, half=False):
		bot = config.balancer.bottom
		if double:
			bot *= 2
		if half:
			bot /= 2
		return max(0, bot - bal)

	def tooHigh(self, bal, bot=None):
		if bot == None:
			bot = config.balancer.bottom * 2
		return max(0, bal - bot)

	def orderBalance(self, sym, diff, balancers, side="buy", force="auto", strict=True):
		bals = {}
		markets = ask("markets", sym, side)
		diff = ask("round", diff / len(balancers))
		sig = "%s %s %s %s"%(side, diff, sym, balancers)
		self.log("orderBalance(%s)"%(sig,), markets)
		for side in markets:
			for fullSym in markets[side]:
				for balancer in balancers:
					if balancer in fullSym:
						bals[fullSym] = ask("bestTrades", fullSym, side, diff,
							force=force, strict=strict, reason="balance", note=sig)
		return {
			"msg": "balance %s"%(sig,),
			"data": bals
		}
