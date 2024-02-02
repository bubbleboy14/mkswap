import rel
from rel.util import ask, listen
from datetime import datetime
from .comptroller import activesAllowed
from .backend import log, predefs
from .base import Feeder
from .gem import gem
from .config import config

NUDGE = "auto"
CAPPED = "auto"

def setNudge(nudge):
	log("setNudge(%s)"%(nudge,))
	global NUDGE
	NUDGE = nudge

def setCapped(capped):
	log("setCapped(%s)"%(capped,))
	global CAPPED
	CAPPED = capped

class Accountant(Feeder):
	def __init__(self, platform=predefs["platform"], symbols=[], balances=predefs["balances"], balcaps=None):
		self.counts = {
			"fees": 0,
			"fills": 0,
			"active": 0,
			"filled": 0,
			"nudged": 0,
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
			balcaps = CAPPED
		if balcaps == "auto":
			balcaps = config.get("backend", "staging")
		if platform == "dydx":
			rel.timeout(10, self.checkFilled)
			self._usd = "-USD"
		elif not balcaps:
			listen("clientReady", self.getBalances)
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

	def price(self, sym):
		return ask("price", sym)

	def accountsReady(self):
		for sym in self.syms:
			if self.price(sym) == None:
				self.log("no price for", sym, "!!!!!!")
				return False
		return True

	def fullBalances(self, nodph=True, pricer=None):
		return self.balances(pricer, "both", nodph)

	def balances(self, pricer=None, bz=None, nodph=False):
		if not self.accountsReady():
			return { "waiting": "balances not ready" }
		if bz == "both":
			return {
				"actual": self.balances(pricer, self._balances, nodph),
				"theoretical": self.balances(pricer, nodph=nodph)
			}
		pricer = pricer or self.price
		total = 0
		bz = bz or self._theoretical
		obz = self._obals
		vz = {}
		for sym in bz:
			amount = bz[sym] - obz[sym]
			v = vz[sym] = bz[sym]
			if amount and sym != "USD":
				if sym in self._skimmed:
					amount += self._skimmed[sym]
				price = pricer(self.fullSym(sym))
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

	def fee(self, sym, amount):
		self.log("paying", amount, "fee from", sym)
		self.deduct(sym, amount)
		if sym != "USD":
			amount *= self.price(self.fullSym(sym))
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
			return self.counts["active"] / activesAllowed() < 0.5
		return nudge

	def nudge(self, trade):
		self.counts["nudged"] += 1
		oprice = trade["price"]
		cprice = self.price(trade["symbol"])
		pdiff = oprice - cprice
		trade["price"] = round(oprice + pdiff, 5)
		self.log("nudge(%s -> %s)"%(oprice, trade["price"]), trade)

	def realistic(self, trade, feeSide="taker", asScore=False, nudge=False):
		if not self.updateBalances(trade, self._balances, test=True):
			return asScore and -1
		score = gain = ask("estimateGain", trade)
		fee = ask("estimateFee", trade, feeSide)
		if fee:
			score -= fee
		if score <= 0 and gain > 0 and self.shouldNudge(nudge):
			self.nudge(trade)
			return self.realistic(trade, feeSide, asScore, nudge)
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
		if (force or self.realistic(prop, nudge=NUDGE)) and self.updateBalances(prop, force=force):
			self.counts["approved"] += 1
			self.log("trade approved!", prop)
			return True