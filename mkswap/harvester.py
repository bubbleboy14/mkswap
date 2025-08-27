import rel
from rel.util import ask, emit, listen
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
		self.defills = 0
		self.refills = []
		self.refillCount = 0
		self.office = office
		self.pricer = office.price
		network = config.harvester.network
		self.symbol = net2sym[network]
		self.bigSym = self.symbol.upper()
		self.accountant = office.accountant
		self.fullSym = self.accountant.fullSym(self.bigSym)
		gem.accounts(network, self.setStorehouse)
		listen("tooLow", self.tooLow)
		rel.timeout(10, self.measure)
		self.log("starting to measure")

	def status(self):
		return {
			"hauls": self.hauls,
			"harvest": self.harvest,
			"refills": self.refillCount,
			"defills": self.defills
		}

	def setStorehouse(self, resp):
		self.log("setStorehouse()", resp)
		if type(resp) is list and len(resp):
			self.storehouse = resp[0]["address"]
		else:
			self.warn("no storehouse!")

	def measure(self):
		hcfg = config.harvester
		if hcfg.skim or hcfg.balance:
			if not ask("accountsReady"):
				self.log("measure() waiting for accounts")
				return True
			bals = self.accountant.balances(self.pricer, "both", True)
			self.log("measure(%s)"%(bals,))
			msg = "measure() complete"
			hcfg.balance and self.balance(bals)
			if hcfg.skim and self.office.hasMan(self.fullSym):
				price = self.pricer(self.fullSym)
				actual = bals["actual"]["diff"]
				msg = "%s: %s diff;"%(msg, actual)
				if price:
					target = hcfg.batch + self.harvest * price
					msg = "%s %s target"%(msg, target)
					if actual > target:
						self.log("full - skim!")
						self.skim(bals)
				else:
					msg = "%s no price, no target!"%(msg,)
			self.log(msg)
		return True

	def balance(self, balances):
		abals = balances["actual"]
		tbals = balances["theoretical"]
		smalls = {}
		bigs = []
		lows = []
		for sym in abals:
			isusd = sym == "USD"
			abal = abals[sym]
			tbal = tbals[sym]
			if not isusd:
				if sym == "diff":
					continue
				fs = self.accountant.fullSym(sym)
				abal = ask("getUSD", fs, abal)
				tbal = ask("getUSD", fs, tbal)
				if abal is None:
					self.log("no balance for", fs)
					continue
			lowness = self.tooLow(abal, True) or self.tooLow(tbal)
			if lowness:
				lows.append(sym)
				if not self.tooHigh(abal, True) and not self.tooHigh(tbal):
					smalls[sym] = lowness
			else:
				bigs.append(sym)
				if isusd:
					umax = config.harvester.usdmax
					highness = self.tooHigh(abal, True, umax) or self.tooHigh(tbal, bot=umax)
		for sym in smalls:
			self.refillCount += 1
			self.refills.append(self.orderBalance(sym, round(smalls[sym], 5), bigs))
		if highness:
			self.defills += 1
			syms = list(smalls.keys()) or lows or list(filter(lambda s : s != "USD"), bigs)
			self.refills.append(self.orderBalance("USD", round(highness, 5), syms, "sell"))

	def getRefills(self):
		refs = self.refills
		self.refills = []
		return refs

	def tooLow(self, bal, actual=False):
		bot = config.harvester.bottom
		if actual:
			bot *= 2
		return max(0, bot - bal)

	def tooHigh(self, bal, actual=False, bot=None):
		if bot == None:
			bot = config.harvester.bottom * 2
		return max(0, bal - bot)

	def orderBalance(self, sym, diff, balancers, side="buy"):
		bals = {}
		markets = ask("markets", sym, side)
		sig = "%s %s %s %s"%(side, diff, sym, balancers)
		self.log("orderBalance(%s)"%(sig,), markets)
		for side in markets:
			for fullSym in markets[side]:
				for balancer in balancers:
					if balancer in fullSym:
						bals[fullSym] = ask("bestTrades", fullSym, side, diff)
		return {
			"msg": "balance %s"%(sig,),
			"data": bals
		}

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