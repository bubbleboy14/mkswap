import rel
from rel.util import ask, emit, listen
from .base import Worker
from .backend import log
from .gem import gem

BATCH = 10
BOTTOM = 50
SKIM = False
BALANCE = True
NETWORK = "bitcoin" # ethereum available on production...

net2sym = {
	"bitcoin": "btc",
	"ethereum": "eth"
}

def setBatch(batch):
	log("setBatch(%s)"%(batch,))
	global BATCH
	BATCH = batch

def setBottom(bottom):
	log("setBottom(%s)"%(bottom,))
	global BOTTOM
	BOTTOM = bottom

def setSkim(skim):
	log("setSkim(%s)"%(skim,))
	global SKIM
	SKIM = skim

def setBalance(shouldBal):
	log("setBalance(%s)"%(shouldBal,))
	global BALANCE
	BALANCE = shouldBal

def setNetwork(network):
	log("setNetwork(%s)"%(network,))
	global NETWORK
	NETWORK = network

class Harvester(Worker):
	def __init__(self, office):
		self.hauls = 0
		self.harvest = 0
		self.refills = []
		self.refillCount = 0
		self.office = office
		self.pricer = office.price
		self.symbol = net2sym[NETWORK]
		self.bigSym = self.symbol.upper()
		self.accountant = office.accountant
		self.fullSym = self.accountant.fullSym(self.bigSym)
		gem.accounts(NETWORK, self.setStorehouse)
		listen("tooLow", self.tooLow)
		listen("getUSD", self.getUSD)
		rel.timeout(10, self.measure)
		self.log("starting to measure")

	def status(self):
		return {
			"hauls": self.hauls,
			"harvest": self.harvest,
			"refills": self.refillCount
		}

	def setStorehouse(self, resp):
		self.log("setStorehouse()", resp)
		if type(resp) is list and len(resp):
			self.storehouse = resp[0]["address"]
		else:
			self.warn("no storehouse!")

	def measure(self):
		if SKIM or BALANCE:
			if not ask("accountsReady"):
				self.log("measure() waiting for accounts")
				return True
			bals = self.accountant.balances(self.pricer, "both", True)
			self.log("measure(%s)"%(bals,))
			msg = "measure() complete"
			BALANCE and self.balance(bals)
			if SKIM and self.office.hasMan(self.fullSym):
				price = self.pricer(self.fullSym)
				actual = bals["actual"]["diff"]
				msg = "%s: %s diff;"%(msg, actual)
				if price:
					target = BATCH + self.harvest * price
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
		for sym in abals:
			abal = abals[sym]
			tbal = tbals[sym]
			if sym != "USD":
				if sym == "diff":
					continue
				fs = self.accountant.fullSym(sym)
				abal = self.getUSD(fs, abal)
				tbal = self.getUSD(fs, tbal)
				if abal is None:
					self.log("no balance for", fs)
					continue
			lowness = self.tooLow(abal, True) or self.tooLow(tbal)
			if lowness:
				smalls[sym] = lowness
			else:
				bigs.append(sym)
		for sym in smalls:
			self.refillCount += 1
			self.refills.append(self.orderBalance(sym, smalls[sym], bigs))

	def getRefills(self):
		refs = self.refills
		self.refills = []
		return refs

	def tooLow(self, bal, actual=False):
		bot = BOTTOM
		if actual:
			bot *= 2
		return max(0, bot - bal)

	def getUSD(self, sym, bal):
		iline = "getUSD(%s, %s) ->"%(sym, bal)
		if type(bal) in [float, int]:
			price = self.pricer(sym)
			if not price:
				return self.log("%s -> no price yet!"%(iline,))
			bal *= price
		else:
			bal = float(bal[:-1].split(" ($").pop())
		self.log(iline, "$%s"%(bal,))
		return bal

	def fromUSD(self, sym, amount):
		return round(amount / self.pricer(self.accountant.fullSym(sym[:3])), 6)

	def balTrade(self, sym, side, amount, price):
		order = {
			"side": side,
			"symbol": sym,
			"price": price,
			"amount": amount
		}
		self.log("balTrade(%s, %s, %s) placing order: %s"%(sym, side, amount, order))
		emit("balanceTrade", order)

	def balTrades(self, sym, side, amountUSD):
		prices = ask("bestPrices", sym, side)
		sym = sym.replace("/", "") # for ratio-derived prices
		amount = self.fromUSD(sym, amountUSD)
		self.log("balTrades(%s, %s, %s->%s)"%(sym, side, amountUSD, amount))
		for span in prices:
			self.balTrade(sym, side, amount, prices[span])
		return {
			"amount": amount,
			"prices": prices
		}

	def orderBalance(self, sym, diff, balancers):
		bals = {}
		markets = ask("markets", sym)
		sig = "%s, %s, %s"%(sym, diff, balancers)
		self.log("orderBalance(%s)"%(sig,), markets)
		for side in markets:
			for fullSym in markets[side]:
				for balancer in balancers:
					if balancer in fullSym:
						bals[fullSym] = self.balTrades(fullSym, side, diff)
		return {
			"msg": "balance %s"%(sig,),
			"data": bals
		}

	def skimmed(self, resp):
		self.log("skimmed #%s:"%(self.hauls,), resp["message"])

	def skim(self, bals):
		price = self.pricer(self.fullSym)
		amount = round(BATCH / price, 5)
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