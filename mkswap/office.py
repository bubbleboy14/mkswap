import pprint, atexit, rel
from .backend import start, predefs, setStaging, listen, initConfig, selectPreset
from .comptroller import Comptroller
from .accountant import Accountant
from .strategist import strategies
from .harvester import Harvester
from .manager import Manager
from .trader import Trader
from .base import Worker
from .ndx import NDX
from .gem import gem
from .config import config

class Office(Worker):
	def __init__(self, platform=predefs["platform"], symbols=[], strategy=predefs["strategy"], globalStrategy=False, globalTrade=False):
		stish = config.office.stagish
		self.platform = platform
		self.symbols = symbols
		self.ndx = NDX()
		self.accountant = Accountant(platform, symbols)
		self.trader = globalTrade and Trader(platform)
		trec = self.trader and self.trader.recommend
		strat = strategies[strategy]
		stish and setStaging(False)
		self.stratname = strategy
		self.strategist = globalStrategy and strat(symbols, trec)
		self.managers = {}
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

	def price(self, symbol):
		return self.ndx.price(symbol) or self.ndx.faves.get(symbol, None)

	def prices(self):
		pz = {}
		for sym in self.managers.keys():
			pz[sym] = self.price(sym)
		return pz

	def stratuses(self):
		ds = {}
		if self.strategist:
			ds[self.stratname] = self.strategist.stats
		else:
			for sym in self.managers:
				ds[sym] = self.managers[sym].strategist.stats
		return ds

	def status(self):
		com = self.comptroller
		acc = self.accountant
		har = self.harvester
		ndx = self.ndx
		return {
			"ndx": ndx.faves,
			"gem": gem.status(),
			"orders": ndx.orders,
			"actives": com.actives,
			"backlog": com.backlog,
			"fills": com.getFills(),
			"prices": self.prices(),
			"volumes": ndx.volumes(),
			"accountant": acc.counts,
			"harvester": har.status(),
			"cancels": com.getCancels(),
			"refills": har.getRefills(),
			"warnings": self.getWarnings(),
			"strategists": self.stratuses(),
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
		config.office.verbose and self.log("%s %s at %s - %s trade!"%(action,
			symbol, price, isgood and "GOOD" or "BAD"))
		direction = isgood and 1 or -1
		return direction, abs(diff) * trade["amount"] * price * direction

	def review(self, symbol=None, trader=None, curprice=None):
		if not config.office.verbose:
			return
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
		lstr.append(pprint.pformat(self.accountant.balances(self.price, nodph=config.base.unspammed)))
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
	office = Office(**(kwargs or selectPreset()))
	atexit.register(office.teardown)
	return office

def load():
	initConfig()
	getOffice()
	start()

if __name__ == "__main__":
	load()