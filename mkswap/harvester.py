import rel
from rel.util import ask
from .base import Worker
from .gem import gem
from .config import config

net2sym = {
	"bitcoin": "btc",
	"ethereum": "eth"
}

class Harvester(Worker):
	def __init__(self, office):
		self.hauls = 0
		self.harvest = 0
		self.office = office
		self.pricer = office.price
		network = config.harvester.network
		self.symbol = net2sym[network]
		self.bigSym = self.symbol.upper()
		self.accountant = office.accountant
		self.fullSym = ask("fullSym", self.bigSym)
		gem.accounts(network, self.setStorehouse)
		rel.timeout(config.harvester.int, self.measure)

	def status(self):
		return {
			"hauls": self.hauls,
			"harvest": self.harvest
		}

	def setStorehouse(self, resp):
		self.log("setStorehouse()", resp)
		if type(resp) is list and len(resp):
			self.storehouse = resp[0]["address"]
		else:
			self.warn("no storehouse!")

	def measure(self):
		hcfg = config.harvester
		if hcfg.skim and ask("accountsReady") and ask("hasMan", self.fullSym):
			bals = ask("balances", mode="tri")
			price = ask("price", self.fullSym)
			diff = bals["actual"]["diff"]
			msg = "measure() complete: %s diff;"%(diff,)
			if price:
				target = hcfg.batch + self.harvest * price
				msg = "%s %s target"%(msg, target)
				if diff > target:
					self.log("full - skim!")
					self.skim(bals)
			else:
				msg = "%s no price, no target!"%(msg,)
			self.log(msg)
		return True

	def skimmed(self, resp):
		self.log("skimmed #%s:"%(self.hauls,), resp["message"])

	def skim(self, bals):
		price = self.pricer(self.fullSym)
		amount = round(config.harvester.batch / price, 5)
		bal = float(bals["actual"][self.bigSym].split(" ").pop(0))
		if amount > bal:
			self.log("balance (%s) < skim (%s)"%(bal, amount))
			if bal <= 0:
				return self.log("non-positive balance - skipping skim!")
			self.log("reducing skim to half balance")
			amount = round(bal / 2)
		self.hauls += 1
		self.harvest += amount
		memo = "skim #%s"%(self.hauls,)
		self.log(memo, ":", amount, self.symbol, "- now @",
			self.harvest, "($%s)"%(round(self.harvest * price, 2),))
		self.accountant.skim(self.bigSym, amount)
		gem.withdraw(self.symbol, amount, self.storehouse, memo, self.skimmed)