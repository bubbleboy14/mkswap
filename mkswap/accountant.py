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
			"nudges": 0,
			"nudged": 0,
			"active": 0,
			"approved": 0,
			"rejected": 0,
			"cancelled": 0
		}
		self.syms = symbols
		self._skimmed = {}
		self._obals = {}
		self._theoretical = {}
		self._balances = balances
		self._obals.update(balances)
		self._theoretical.update(balances)
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
		listen("accountsReady", self.accountsReady)
		listen("balances", self.fullBalances)
		listen("affordable", self.affordable)
		listen("realistic", self.realistic)
		listen("fullSym", self.fullSym)

	def getBalances(self):
		self.log("getBalances!!!")
		gem.balances(self.setBalances)

	def setBalances(self, bals):
		self.log("setBalances", bals)
		for bal in bals:
			sym = bal["currency"]
			if sym in self._balances:
				self._balances[sym] = float(bal["available"])
		self._obals.update(self._balances)
		self._theoretical.update(self._balances)
		self.log("setBalances", self._balances)
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

	def fullSym(self, sym):
		return sym + self._usd

	def price(self, sym, history="trade", fallback=None):
		return ask("price", sym, history=history, fallback=fallback)

	def accountsReady(self):
		for sym in self.syms:
			if self.price(sym) == None:
				self.log("no price for", sym, "!!!!!!")
				return False
		return True

	def fullBalances(self, nodph=True, pricer=None):
		return self.balances(pricer, "both", nodph)

	def balances(self, pricer=None, bz=None, nodph=False, history="trade"):
		if not self.accountsReady():
			return { "waiting": "balances not ready" }
		if bz == "both":
			return {
				"actual": self.balances(pricer, self._balances, nodph),
				"theoretical": self.balances(pricer, nodph=nodph)
			}
		elif bz == "all":
			return {
				"theoretical": self.balances(pricer, nodph=nodph),
				"actual": self.balances(pricer, self._balances, nodph),
				"ask": self.balances(pricer, nodph=nodph, history="ask"),
				"bid": self.balances(pricer, nodph=nodph, history="bid")
			}
		pricer = pricer or self.price
		total = 0
		bz = bz or self._theoretical
		obz = self._obals
		vz = {}
		for sym in bz:
			amount = bz[sym] - obz[sym]
			v = vz[sym] = bz[sym]
			if sym != "USD":
				if sym in self._skimmed:
					amount += self._skimmed[sym]
				price = pricer(self.fullSym(sym), history=history)
				amount *= price
				vz[sym] = "%s ($%s)"%(v, v * price)
			total += amount
		vz["diff"] = total
		secs = (datetime.now() - self.starttime).seconds
		if not nodph:
			vz["dph"] = secs and (total * 60 * 60 / secs)
		return vz

	def orderCancelled(self, trade, backlogged=False):
		self.updateBalances(trade, revert=True, force=True)
		self.counts["cancelled"] += 1
		if not backlogged:
			self.counts["active"] -= 1
		self.log("order cancelled!")

	def orderFilled(self, trade, complete=False):
		self.updateBalances(trade, self._balances, force=True)
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
			self._theoretical[feesym] += adjustment
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
		self.updateBalances(trade, revert=True, force=True)

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
		self._theoretical[sym] -= amount
		self._balances[sym] -= amount

	def shouldNudge(self, nudge):
		if nudge == "auto":
			return self.counts["active"] / config.comptroller.actives < 0.5
		return nudge

	def nudge(self, trade):
		sym = trade["symbol"]
		oprice = trade["price"]
		cprice = self.price(sym)
		self.counts["nudges"] += 1
		pdiff = (oprice - cprice) * config.accountant.nmult
		trade["price"] = round(oprice + pdiff, predefs["sigfigs"].get(sym, 2))
		self.log("nudge(%s -> %s)"%(oprice, trade["price"]), trade)

	def realistic(self, trade, feeSide="taker", asScore=False, nudge=False, nudged=0):
		if not self.updateBalances(trade, self._balances, test=True):
			return asScore and -1
		score = gain = ask("estimateGain", trade)
		fee = ask("estimateFee", trade, feeSide)
		if fee:
			score -= fee
		if score <= 0 and gain > 0 and self.shouldNudge(nudge) and nudged < 10:
			self.nudge(trade)
			if not nudged:
				self.counts["nudged"] += 1
			return self.realistic(trade, feeSide, asScore, nudge, nudged + 1)
		if asScore:
			return score
		return score > 0

	def updateBalances(self, prop, bz=None, revert=False, force=False, test=False):
		bz = bz or self._theoretical
		s = rs = float(prop.get("amount", 10))
		v = rv = s * float(prop["price"])
		if revert:
			rs *= -1
			rv *= -1
		sym1, sym2 = self.pair(prop["symbol"])
		if prop["side"] == "buy":
			if v > bz[sym2] and not force:
				self.log("not enough %s!"%(sym2,))
				return False
			if not test:
				bz[sym2] -= rv
				bz[sym1] += rs
		else:
			if s > bz[sym1] and not force:
				self.log("not enough %s!"%(sym1,))
				return False
			if not test:
				bz[sym2] += rv
				bz[sym1] -= rs
		return True

	def affordable(self, prop, force=False):
		if prop["symbol"] not in self.syms:
			self.syms.append(prop["symbol"])
		if (force or self.realistic(prop, nudge=config.accountant.nudge)) and self.updateBalances(prop, force=force):
			self.counts["approved"] += 1
			self.log("trade approved!", prop)
			return True