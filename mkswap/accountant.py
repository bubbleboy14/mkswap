import rel
from rel.util import ask, emit, listen, when, transpire
from datetime import datetime
from .backend import predefs
from .base import Worker
from .gem import gem
from .config import config

class Accountant(Worker):
	def __init__(self, platform=predefs["platform"], symbols=[], balances=predefs["balances"], balcaps=None):
		self.counts = {
			"fees": 0,
			"fills": 0,
			"filled": 0,
			"active": 0,
			"approved": 0,
			"rejected": 0,
			"cancelled": 0
		}
		self.syms = symbols
		self._skimmed = {}
		bz = self._balances = {
			"actual": {},
			"initial": {},
			"available": {},
			"theoretical": {}
		}
		for bal in bz:
			bz[bal].update(balances)
		self.starttime = datetime.now()
		self.platform = platform
		self._usd = "USD"
		if balcaps is None:
			balcaps = config.accountant.capped
		if balcaps == "auto":
			balcaps = config.backend.staging
		if platform == "dydx":
			rel.timeout(10, self.checkFilled)
			self._usd = "-USD"
		elif balcaps:
			transpire("balancesReady")
		else:
			when("clientReady", self.getBalances)
		listen("orderCancelled", self.orderCancelled)
		listen("orderRejected", self.orderRejected)
		listen("orderFilled", self.orderFilled)
		listen("orderActive", self.orderActive)
		listen("overActive", self.overActive)
		listen("accountsReady", self.accountsReady)
		listen("updateBalances", self.updateBalances)
		listen("balances", self.fullBalances)
		listen("available", self.available)
		listen("approved", self.approved)
		listen("fullSym", self.fullSym)
		listen("fromUSD", self.fromUSD)
		listen("getUSD", self.getUSD)
		listen("skim", self.skim)

	def getBalances(self):
		self.log("getBalances!!!")
		gem.balances(self.setBalances)

	def setBalances(self, bals):
		self.log("setBalances", bals)
		bz = self._balances
		acz = bz["actual"]
		syms = list(acz.keys())
		for bal in bals:
			sym = bal["currency"]
			if sym in syms:
				acz[sym] = float(bal["amount"])
				syms.remove(sym)
		for sym in syms:
			acz[sym] = 0
		for bal in ["initial", "available", "theoretical"]:
			bz[bal].update(acz)
		self.log("setBalances", acz)
		transpire("balancesReady")

	def pair(self, syms):
		if self.platform == "dydx":
			return syms.split("-")
		return syms[:3], syms[3:]

	def checkFilled(self):
		self.counts["filled"] = 0
		for sym in self.syms:
			self.counts["filled"] += len(ask("fills", sym))
		return True

	def getUSD(self, sym, bal):
		iline = "getUSD(%s, %s) ->"%(sym, bal)
		if type(bal) in [float, int]:
			price = self.price(sym)
			if not price:
				return self.log("%s no price yet!"%(iline,))
			bal *= price
		else:
			bal = float(bal[:-1].split(" ($").pop())
		config.base.unspammed or self.log(iline, "$%s"%(bal,))
		return bal

	def fromUSD(self, sym, amount):
		return ask("round", amount / self.price(self.fullSym(sym[:3])))

	def fullSym(self, sym):
		return sym + self._usd

	def price(self, sym, history="trade", fallback=None):
		return ask("price", sym, history=history, fallback=fallback)

	def available(self, sym=None):
		abz = self._balances["available"]
		if sym:
			return abz[sym]
		return abz

	def accountsReady(self, history="trade"):
		for sym in self.syms:
			if self.price(sym, history) == None:
				self.log("no price for", sym, "!!!!!!")
				return False
		return True

	def fullBalances(self, nodph=True, pricer=None, mode="both", nousd=False, nodiff=False, history="trade"):
		return self.balances(pricer, mode, nodph, nousd, history)

	def balances(self, pricer=None, balset="theoretical", nodph=False, nousd=False, nodiff=False, history="trade"):
		obz = self._balances["initial"]
		if not self.accountsReady(history):
			return { "waiting": "balances not ready" }
		if balset == "both":
			return {
				"actual": self.balances(pricer, "actual", nodph),
				"theoretical": self.balances(pricer, nodph=nodph)
			}
		elif balset == "tri":
			return {
				"actual": self.balances(pricer, "actual", nodph),
				"theoretical": self.balances(pricer, nodph=nodph),
				"available": self.balances(pricer, "available", nodph)
			}
		elif balset == "all":
			return {
				"initial": obz,
				"actual": self.balances(pricer, "actual", nodph),
				"theoretical": self.balances(pricer, nodph=nodph),
				"available": self.balances(pricer, "available", nodph),
				"ask": self.balances(pricer, nodph=nodph, history="ask"),
				"bid": self.balances(pricer, nodph=nodph, history="bid")
			}
		pricer = pricer or self.price
		bz = self._balances[balset]
		total = 0
		vz = {}
		for sym in bz:
			amount = bz[sym] - obz[sym]
			v = vz[sym] = bz[sym]
			if sym != "USD" and not nousd:
				if sym in self._skimmed:
					amount += self._skimmed[sym]
				price = pricer(self.fullSym(sym), history=history)
				amount *= price
				vz[sym] = "%s ($%s)"%(v, v * price)
			total += amount
		if not nodiff:
			vz["diff"] = total
		secs = (datetime.now() - self.starttime).seconds
		if not nodph:
			vz["dph"] = secs and (total * 60 * 60 / secs)
		return vz

	def orderCancelled(self, trade, backlogged=False):
		self.updateBalances(trade, revert=True, force=True, available=True)
		self.counts["cancelled"] += 1
		if not backlogged:
			self.counts["active"] -= 1
		self.log("order cancelled!")

	def orderFilled(self, trade):
		self.updateBalances(trade, "actual", force=True, available=True)
		complete = not trade["remaining"]
		side = trade["side"]
		price = trade["price"]
		amount = trade["amount"]
		feesym = trade["feesym"]
		self.fee(feesym, trade["fee"])
		pdiff = price - trade["oprice"]
		sig = "orderFilled(%s %s @ %s)"%(side, trade["symbol"], price)
		if pdiff:
			if side == "buy":
				pdiff *= -1
			adjustment = amount * pdiff
			self.log(sig, "adjusting", feesym, "by",
				amount, "times", pdiff, "=", adjustment)
			self._balances["theoretical"][feesym] += adjustment
		self.counts["fills"] += 1
		if complete:
			self.counts["filled"] += 1
			self.counts["active"] -= 1
		self.log(sig, "complete:", str(complete))

	def orderActive(self, trade):
		self.log("order active!")
		self.counts["active"] += 1

	def orderRejected(self, trade):
		self.log("order rejected!")
		self.counts["rejected"] += 1
		self.updateBalances(trade, revert=True, force=True, available=True)

	def fee(self, sym, amount):
		self.log("paying", amount, "fee from", sym)
		self.deduct(sym, amount)
		if sym != "USD":
			amount *= self.price(self.fullSym(sym), fallback="both")
		self.counts["fees"] += amount

	def skim(self, sym, amount):
		skz = self._skimmed
		if (sym not in skz):
			skz[sym] = 0;
		skz[sym] += amount
		self.log("skimming", amount, "from", sym, "- now @", skz[sym])
		self.deduct(sym, amount)

	def deduct(self, sym, amount):
		self.log("deducting", amount, "from", sym)
		for b in ["actual", "available", "theoretical"]:
			self._balances[b][sym] -= amount

	def overActive(self, lim=0.9):
		rat = self.counts["active"] / config.comptroller.actives
		return max(0, rat - lim)

	def updateBalances(self, trade, balset="theoretical", revert=False, force=False, test=False, repair=False, available=False):
		bz = self._balances[balset]
		s = rs = float(trade.get("amount", 10))
		v = rv = s * float(trade["price"])
		side = trade["side"]
		sym1, sym2 = self.pair(trade["symbol"])
		if side == "buy":
			fromSym = sym2
			toSym = sym1
			fromVal = v
			rv *= -1
		else:
			fromSym = sym1
			toSym = sym2
			fromVal = s
			rs *= -1
		if revert:
			rs *= -1
			rv *= -1
		if fromVal > bz[fromSym] and not force:
			self.log("not enough %s for %s!"%(fromSym, side))
			if test and repair:
				trade["amount"] = bz[fromSym] / config.accountant.split
				self.log("downsized order: %s -> %s"%(s, trade["amount"]))
			return False
		if not test:
			if available:
				az = self._balances["available"]
				if revert or balset == "actual":
					do2 = rv > 0
				else:
					do2 = rv < 0
				if not (force or revert):
					if do2 and az[sym2] + rv < 0:
						return False
					elif az[sym1] + rs < 0:
						return False
				if do2:
					az[sym2] += rv
				else:
					az[sym1] += rs
			bz[sym2] += rv
			bz[sym1] += rs
		return True

	def approved(self, trade, force=False):
		if trade["symbol"] not in self.syms:
			self.syms.append(trade["symbol"])
		if ask("shouldWork", trade, force):
			if self.updateBalances(trade, force=force, available=True):
				self.counts["approved"] += 1
				self.log("trade approved!", trade)
				return True