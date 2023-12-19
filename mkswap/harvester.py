import rel
from rel.util import ask, emit
from .base import Worker
from .backend import log, gemget

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
		self.office = office
		self.pricer = office.price
		self.symbol = net2sym[NETWORK]
		self.bigSym = self.symbol.upper()
		self.accountant = office.accountant
		self.fullSym = self.accountant.fullSym(self.bigSym)
		gemget("/v1/addresses/%s"%(NETWORK,), self.setStorehouse)
		rel.timeout(10, self.measure)

	def status(self):
		return {
			"hauls": self.hauls,
			"harvest": self.harvest
		}

	def setStorehouse(self, resp):
		self.storehouse = resp[0]["address"]

	def measure(self):
		if SKIM or BALANCE and self.office.hasMan(self.fullSym):
			bals = self.accountant.balances(self.pricer, "both", True)
			actual = bals["actual"]["diff"]
			target = BATCH + self.harvest * self.pricer(self.fullSym)
			self.log("measure():", actual, "actual;", target, "target.", bals)
			if actual > target:
				self.log("full!")
				BALANCE and self.balance(bals)
				SKIM and self.skim(bals)
		return True

	def balance(self, balances):
		self.log("balance(%s)"%(balances,))
		abals = balances["actual"]
		for sym in abals:
			if sym == "diff":
				continue
			if sym == "USD": # handle later...
				continue
			fs = self.accountant.fullSym(sym)
			bal = abals[sym]
			if type(bal) is float:
				bal *= self.pricer(fs)
			else:
				bal = float(bal[:-1].split(" ($").pop())
			diff = bal - BOTTOM
			if diff < 0:
				price = self.bestPrice(fs)
				emit("balanceTrade", {
					"symbol": fs,
					"side": "buy",
					"price": price,
					"amount": diff / price
				})

	def bestPrice(self, sym, side):
		return ask("best", sym, side) or round(self.pricer(sym), 6)

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
		self.accountant.deduct(self.bigSym, amount)
		gemget("/v1/withdraw/%s"%(self.symbol,), self.skimmed, {
			"memo": memo,
			"amount": str(amount),
			"address": self.storehouse
		})