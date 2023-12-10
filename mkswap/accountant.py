from datetime import datetime
from .backend import rel, ask, listen, predefs
from .base import Feeder

class Accountant(Feeder):
	def __init__(self, platform=predefs["platform"], balances=predefs["balances"]):
		self.counts = {
			"filled": 0,
			"approved": 0
		}
		self.syms = []
		self._obals = {}
		self._balances = balances
		self._obals.update(balances)
		self.starttime = datetime.now()
		self.platform = platform
		self._usd = "USD"
		if platform == "dydx":
			rel.timeout(10, self.checkFilled)
			self._usd = "-USD"
		listen("affordable", self.affordable)

	def pair(self, syms):
		if self.platform == "dydx":
			return syms.split("-")
		return syms[:3], syms[3:]

	def checkFilled(self):
		self.counts["filled"] = 0
		for sym in self.syms:
			self.counts["filled"] += len(ask("fills", sym))
		return True

	def balances(self, pricer):
		total = 0
		bz = self._balances
		obz = self._obals
		vz = {}
		for sym in bz:
			amount = bz[sym] - obz[sym]
			v = vz[sym] = bz[sym]
			if amount and sym != "USD":
				price = pricer(sym + self._usd)
				amount *= price
				vz[sym] = "%s ($%s)"%(v, v * price)
			total += amount
		vz["diff"] = total
		vz["dph"] = total * 60 * 60 / (datetime.now() - self.starttime).seconds
		return vz

	def affordable(self, prop):
		s = prop.get("size", 10)
		v = s / prop["price"]
		bz = self._balances
		sym1, sym2 = self.pair(prop["symbol"])
		if prop["symbol"] not in self.syms:
			self.syms.append(prop["symbol"])
		self.log("balances", bz)
		if prop["action"] == "BUY":
			if s > bz[sym2]:
				self.log("not enough %s!"%(sym2,))
				return False
			bz[sym2] -= s
			bz[sym1] += v
		else:
			if v > bz[sym1]:
				self.log("not enough %s!"%(sym1,))
				return False
			bz[sym2] += s
			bz[sym1] -= v
		self.counts["approved"] += 1
		self.log("trade approved!")
		return True