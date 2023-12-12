from datetime import datetime
from .backend import rel, ask, listen, predefs, gemget
from .base import Feeder

CAP_BALANCES = True

class Accountant(Feeder):
	def __init__(self, platform=predefs["platform"], balances=predefs["balances"], balcaps=CAP_BALANCES):
		self.counts = {
			"filled": 0,
			"approved": 0,
			"cancelled": 0
		}
		self.syms = []
		self._obals = {}
		self._theoretical = {}
		self._balances = balances
		self._obals.update(balances)
		self._theoretical.update(balances)
		self.starttime = datetime.now()
		self.platform = platform
		self._usd = "USD"
		if platform == "dydx":
			rel.timeout(10, self.checkFilled)
			self._usd = "-USD"
		elif not balcaps:
			listen("clientReady", self.getBalances)
		listen("tradeComplete", self.tradeComplete)
		listen("tradeCancelled", self.tradeCancelled)
		listen("affordable", self.affordable)

	def getBalances(self):
		self.log("getBalances!!!")
		gemget("/v1/balances", self.setBalances)

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

	def balances(self, pricer, bz=None):
		if bz == "both":
			return {
				"actual": self.balances(pricer, self._balances),
				"theoretical": self.balances(pricer)
			}
		total = 0
		bz = bz or self._theoretical
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
		secs = (datetime.now() - self.starttime).seconds
		vz["dph"] = secs and (total * 60 * 60 / secs)
		return vz

	def tradeCancelled(self, trade):
		if self.updateBalances(trade, revert=True):
			self.counts["cancelled"] += 1
			self.log("trade cancelled!")
		else:
			self.log("balances out of sync!")

	def tradeComplete(self, trade):
		if self.updateBalances(trade, self._balances):
			self.counts["filled"] += 1
			self.log("trade complete!")
		else:
			self.log("balances out of sync!")

	def updateBalances(self, prop, bz=None, revert=False):
		bz = bz or self._theoretical
		s = rs = prop.get("amount", 10)
		v = rv = s / prop["price"]
		if revert:
			rs *= -1
			rv *= -1
		sym1, sym2 = self.pair(prop["symbol"])
		self.log("balances", bz)
		if prop["side"] == "buy":
			if s > bz[sym2]:
				self.log("not enough %s!"%(sym2,))
				return False
			bz[sym2] -= rs
			bz[sym1] += rv
		else:
			if v > bz[sym1]:
				self.log("not enough %s!"%(sym1,))
				return False
			bz[sym2] += rs
			bz[sym1] -= rv
		return True

	def affordable(self, prop):
		if prop["symbol"] not in self.syms:
			self.syms.append(prop["symbol"])
		if self.updateBalances(prop):
			self.counts["approved"] += 1
			self.log("trade approved!")
			return True
		else:
			self.log("balances not updated!")