import rel
from rel.util import ask, listen
from .base import Worker
from .config import config

class Balancer(Worker):
	def __init__(self):
		self.refills = []
		self.scheduled = {}
		self.counts = {
			"refills": 0,
			"defills": 0,
			"balances": 0
		}
		listen("tooLow", self.tooLow)
		rel.timeout(config.balancer.int, self.measure)

	def status(self):
		status = self.counts.copy()
		status.update(self.scheduled)
		return status

	def usdcap(self, base=None):
		positions = ask("positions")
		base = base or config.balancer.usdmax
		cap = base + base * positions["lowest"]
		self.log("usdcap", cap, positions)
		self.counts["usdcap"] = cap
		return cap

	def measure(self):
		if config.balancer.balance and ask("accountsReady"):
			self.balance(ask("balances", mode="tri"))
			self.orderBalances()
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
					umax = self.usdcap()
					highness = max(self.tooHigh(avbal, umax), self.tooHigh(abal + tbal, umax * 3))
					highness = min(highness, avbal * 0.9)
		for sym in smalls:
			self.counts["refills"] += 1
			self.scheduleBalance(sym, smalls[sym], bigs)
		if highness:
			self.counts["defills"] += 1
			syms = list(smalls.keys()) or lows or list(filter(lambda s : s != "USD", bigs))
			lowests = [ask("bestBuy", syms)]
			self.scheduleBalance("USD", highness, lowests, "sell")

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

	def orderBalances(self, force="auto", strict=True):
		bals = {}
		trades = []
		for sym, amount in self.scheduled.items():
			traj = ask("metric", sym, "trajectory")
			side = "buy"
			if amount < 0:
				amount *= -1
				side = "sell"
			buydown = side == "buy" and (traj == "down" or traj == "overheated")
			sellup = side == "sell" and (traj == "up" or traj == "undersold")
			if buydown or sellup:
				self.log("%s market is %s - waiting"%(sym, traj))
			else:
				sig = "%s %s %s (%s)"%(side, amount, sym, traj)
				self.log(sig)
				trades.append(sig)
				bals[sym] = ask("bestTrades", sym, side, amount,
					force=force, strict=strict, reason="balance", note=traj)
		if bals:
			for sym in bals:
				del self.scheduled[sym]
			self.counts["balances"] += 1
			self.refills.append({
				"msg": "balance: %s"%("; ".join(trades),),
				"data": bals
			})

	def scheduleBalance(self, sym, diff, balancers, side="buy"):
		markets = ask("markets", sym, side)
		diff = ask("round", diff / len(balancers))
		sig = "%s %s %s with %s"%(side, diff, sym, balancers)
		self.log("scheduleBalance(%s)"%(sig,), markets)
		for side in markets:
			for fullSym in markets[side]:
				for balancer in balancers:
					if balancer in fullSym:
						self.scheduled[fullSym] = (side == "buy") and diff or -diff
		self.notice("schedule %s"%(sig,), self.scheduled)
