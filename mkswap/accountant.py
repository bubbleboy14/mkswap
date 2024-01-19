import rel
from rel.util import ask, listen
from datetime import datetime
from .backend import log, predefs
from .base import Feeder
from .gem import gem

CAPPED = True

def setCapped(capped):
	log("setCapped(%s)"%(capped,))
	global CAPPED
	CAPPED = capped

class Accountant(Feeder):
	def __init__(self, platform=predefs["platform"], balances=predefs["balances"], balcaps=None):
		self.counts = {
			"fees": 0,
			"active": 0,
			"filled": 0,
			"approved": 0,
			"rejected": 0,
			"cancelled": 0
		}
		self.syms = []
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
		listen("affordable", self.affordable)
		listen("balances", self.fullBalances)
		listen("fee", self.fee)

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

	def orderFilled(self, trade):
		self.updateBalances(trade, self._balances, force=True)
		self.counts["filled"] += 1
		self.counts["active"] -= 1
		self.log("order filled!")

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

	def realistic(self, prop):
		return self.updateBalances(prop, self._balances, test=True)

	def updateBalances(self, prop, bz=None, revert=False, force=False, test=False):
		bz = bz or self._theoretical
		s = rs = float(prop.get("amount", 10))
		v = rv = s * float(prop["price"])
		if revert:
			rs *= -1
			rv *= -1
		sym1, sym2 = self.pair(prop["symbol"])
		self.log("balances", bz)
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

	def affordable(self, prop):
		if prop["symbol"] not in self.syms:
			self.syms.append(prop["symbol"])
		if self.realistic(prop) and self.updateBalances(prop):
			self.counts["approved"] += 1
			self.log("trade approved!")
			return True
		else:
			self.log("balances not updated!")