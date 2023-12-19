import rel
from .base import Worker
from .backend import log, gemget

BATCH = 10
SKIM = False
BALANCE = False
NETWORK = "bitcoin" # ethereum available on production...

net2sym = {
	"bitcoin": "btc",
	"ethereum": "eth"
}

def setSkim(skim):
	log("setSkim(%s)"%(skim,))
	global SKIM
	SKIM = skim

def setBatch(batch):
	log("setBatch(%s)"%(batch,))
	global BATCH
	BATCH = batch

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
		bals = self.accountant.balances(self.pricer, "both", True)
		self.log("measure", bals)
		if bals["actual"]["diff"] > BATCH + self.harvest * self.pricer(self.fullSym):
			self.log("full!")
			BALANCE and self.balance(bals)
			SKIM and self.skim(bals)
		return True

	def balance(self, balances):
		self.log("balance (unimplemented)")

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