from datetime import datetime
from dydx3.helpers.request_helpers import generate_now_iso
from .backend import listen
from .base import Feeder

defbals = {
	"USD": 100,
	"ETH": 0.1,
	"BTC": 0.005
}

class Accountant(Feeder):
	def __init__(self, balances=defbals):
		self._obals = {}
		self._balances = balances
		self._obals.update(balances)
		self.starttime = datetime.now()
		listen("clientReady", self.load)
		listen("affordable", self.affordable)

	def balances(self, pricer):
		total = 0
		bz = self._balances
		obz = self._obals
		vz = {}
		for sym in bz:
			amount = bz[sym] - obz[sym]
			v = vz[sym] = bz[sym]
			if amount and sym != "USD":
				price = pricer(sym + "-USD")
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
		sym = prop["symbol"].split("-")[0]
		self.log("balances", bz)
		if prop["action"] == "BUY":
			if s > bz["USD"]:
				self.log("not enough USD!")
				return False
			bz["USD"] -= s
			bz[sym] += v
		else:
			if v > bz[sym]:
				self.log("not enough %s!"%(sym,))
				return False
			bz["USD"] += s
			bz[sym] -= v
		self.log("trade approved!")
		return True

	def load(self):
		self.feed("dacc", generate_now_iso())