import pprint, atexit, rel
from .backend import log, start, predefs, setStaging, listen
from .comptroller import Comptroller
from .accountant import Accountant
from .strategist import strategies
from .harvester import Harvester
from .manager import Manager
from .trader import Trader
from .base import Worker
from .gem import gem
from .config import config

VERBOSE = False
STAGISH = False

def setVerbose(isverb):
	log("setVerbose(%s)"%(isverb,))
	global VERBOSE
	VERBOSE = isverb

def setStagish(stag):
	log("setStagish(%s)"%(stag,))
	global STAGISH
	STAGISH = stag

class Office(Worker):
	def __init__(self, platform=predefs["platform"], symbols=[], strategy=predefs["strategy"], globalStrategy=False, globalTrade=False):
		stish = config.get("office", "stagish") # necessary w/ -m for some reason...
		self.platform = platform
		self.symbols = symbols
		self.accountant = Accountant(platform)
		self.trader = globalTrade and Trader(platform)
		trec = self.trader and self.trader.recommend
		strat = strategies[strategy]
		self.stratname = strategy
		self.strategist = globalStrategy and strat(symbols, trec)
		stish and setStaging(False)
		self.managers = {}
		self.ndx = {}
		for symbol in symbols:
			self.managers[symbol] = Manager(platform, symbol, self.review,
				self.strategist or strat(symbol, trec), self.trader)
		self.log("initialized %s managers"%(len(symbols),))
		stish and setStaging(True)
		self.comptroller = Comptroller(self.price)
		self.harvester = Harvester(self)
		rel.timeout(1, self.tick)
		self.warnings = []
		listen("warning", self.warning)
		listen("price", self.price)
		listen("quote", self.quote)

	def warning(self, msg, data=None):
		self.warnings.append({ "msg": msg, "data": data })

	def getWarnings(self):
		warns = self.warnings
		self.warnings = []
		return warns

	def cancelAll(self):
		self.log("cancelAll()")
		self.comptroller.cancelAll()

	def teardown(self):
		self.log("teardown()")
		self.cancelAll()

	def sig(self):
		return "Office[%s]"%(self.platform,)

	def hasMan(self, symbol):
		return symbol in self.managers

	def quote(self, symbol, price):
		self.ndx[symbol] = price

	def price(self, symbol):
		if symbol in self.managers:
			return self.managers[symbol].latest["price"]
		return self.ndx.get(symbol, None)

	def prices(self):
		pz = {}
		for sym in self.managers.keys():
			pz[sym] = self.managers[sym].latest["price"]
		return pz

	def stratuses(self):
		ds = {}
		if self.strategist:
			ds[self.stratname] = self.strategist.status()
		else:
			for sym in self.managers:
				ds[sym] = self.managers[sym].strategist.status()
		return ds

	def status(self):
		acc = self.accountant
		com = self.comptroller
		return {
			"ndx": self.ndx,
			"gem": gem.status(),
			"orders": acc.counts,
			"actives": com.actives,
			"backlog": com.backlog,
			"fills": com.getFills(),
			"prices": self.prices(),
			"cancels": com.getCancels(),
			"warnings": self.getWarnings(),
			"strategists": self.stratuses(),
			"harvester": self.harvester.status(),
			"balances": acc.balances(self.price, "both")
		}

	def assess(self, trade, curprice=None):
#		self.log("assess", trade)
		action = trade["side"]
		price = trade["price"]
		symbol = trade["symbol"]
		curprice = curprice or self.price(symbol)
		diff = curprice - price
		if not curprice: # can this even happen?
			return self.log("skipping assessment (waiting for %s price)"%(symbol,))
		if action == "buy":
			isgood = diff > 0
		else: # sell
			isgood = diff < 0
		VERBOSE and self.log("%s %s at %s - %s trade!"%(action,
			symbol, price, isgood and "GOOD" or "BAD"))
		direction = isgood and 1 or -1
		return direction, abs(diff) * trade["amount"] * price * direction

	def review(self, symbol=None, trader=None, curprice=None):
		mans = self.managers
		if symbol:
			man = mans[symbol]
			trader = man.trader
			curprice = man.latest["price"]
		else:
			trader = trader or self.trader
		tz = trader.trades = trader.trades[-20:] # or it keeps growing...
		if symbol:
			tz = list(filter(lambda t : t["symbol"] == symbol, tz))
		if not tz:
			return self.log("skipping review (waiting for trades)")
		lstr = ["review %s"%(len(tz),)]
		symbol and lstr.append(symbol)
		lstr.append("trades\n-")
		if curprice:
			lstr.append("price is %s"%(curprice,))
		else:
			lstr.append("prices are:")
			lstr.append("; ".join(["%s at %s"%(sym, self.price(sym)) for sym in mans.keys()]))
		score = 0
		rate = 0
		for trade in tz:
			r, s = self.assess(trade, curprice)
			rate += r
			score += s
		lstr.extend(["\n- trade score:", rate, "(", score, ")"])
		lstr.append("\n- balances are:")
		lstr.append(pprint.pformat(self.accountant.balances(self.price, nodph=not VERBOSE)))
		self.log(*lstr)

	def tick(self):
		manStrat = manTrad = True
		if self.strategist:
			self.strategist.tick()
			manStrat = False
		if self.trader:
			self.trader.tick()
			self.review()
			manTrad = False
		if manStrat or manTrad:
			for manager in self.managers:
				self.managers[manager].tick(manStrat, manTrad)
		return True

def getOffice(**kwargs):
	office = Office(**(kwargs or config.select()))
	atexit.register(office.teardown)
	return office

def load():
	config.init()
	getOffice()
	start()

if __name__ == "__main__":
	load()