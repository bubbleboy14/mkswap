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
		self.refills = 0
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
			"harvest": self.harvest,
			"refills": self.refills
		}

	def setStorehouse(self, resp):
		self.log("setStorehouse()", resp)
		self.storehouse = resp[0]["address"]

	def measure(self):
		if SKIM or BALANCE and self.office.hasMan(self.fullSym):
			bals = self.accountant.balances(self.pricer, "both", True)
			actual = bals["actual"]["diff"]
			target = BATCH + self.harvest * self.pricer(self.fullSym)
			self.log("measure():", actual, "actual;", target, "target.", bals)
			if actual > target:
				self.log("full!")
				SKIM and self.skim(bals)
			BALANCE and self.balance(bals)
		return True

	def balance(self, balances):
		abals = balances["actual"]
		sellsym = None
		ssbal = None
		for sym in abals:
			if sym == "diff" or sym == "USD": # USD handled below
				continue
			fs = self.accountant.fullSym(sym)
			bal = self.office.hasMan(fs) and self.getUSD(fs, abals[sym])
			if bal == None:
				self.log("no balance for", fs)
				continue
			self.log("balance(%s %s $%s %s) %s"%(sym,
				fs, bal, abals[sym], balances))
			if not sellsym or bal > ssbal:
				sellsym = fs
				ssbal = bal
			self.maybeBalance(fs, bal)
		self.maybeBalance(sellsym, abals["USD"], "sell")

	def maybeBalance(self, sym, bal, side="buy"):
		diff = BOTTOM - bal
		if diff > 0:
			self.log("maybeBalance(%s, %s, %s) refilling!"%(sym, bal, side))
			self.refills += 1
			self.orderBalance(sym, side, diff)

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

	def orderBalance(self, sym, side, diff):
		price = self.bestPrice(sym, side)
		order = {
			"side": side,
			"symbol": sym,
			"price": price,
			"amount": round(diff / price, 6)
		}
		self.log("orderBalance(%s, %s, %s) placing order: %s"%(sym, side, diff, order))
		emit("balanceTrade", order)

	def bestPrice(self, sym, side):
		bp = ask("best", sym, side) or round(self.pricer(sym), 6)
		self.log("bestPrice(%s, %s) -> %s"%(sym, side, bp))
		return bp

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