import pprint, atexit, rel
from rel.util import ask, listen
from .backend import start, predefs, getConf, setStaging, initConfig, selectPreset, wsdebug
from .comptroller import Comptroller
from .accountant import Accountant
from .strategist import strategies
from .multifeed import MultiFeed
from .harvester import Harvester
from .actuary import Actuary
from .manager import Manager
from .trader import Trader
from .booker import Booker
from .base import Worker
from .ndx import NDX
from .gem import gem
from .config import config

class Office(Worker):
	def __init__(self, platform=predefs["platform"], symbols=[], strategy=predefs["strategy"], globalStrategy=False, globalTrade=True):
		wsdebug(config.feeder.wsdebug)
		stish = config.office.stagish
		self.platform = platform
		self.symbols = symbols
		self.warnings = []
		self.notices = []
		self.crosses = []
		listen("warning", self.warning)
		listen("notice", self.notice)
		listen("cross", self.cross)
		self.ndx = NDX()
		self.actuary = Actuary()
		self.accountant = Accountant(platform, symbols)
		self.trader = globalTrade and Trader(platform)
		strat = strategies[strategy]
		stish and setStaging(False)
		self.stratname = strategy
		self.multifeed = config.backend.mdv2 and MultiFeed()
		self.strategist = globalStrategy and strat(symbols)
		self.managers = {}
		for symbol in symbols:
			self.managers[symbol] = Manager(platform, symbol, self.review,
				self.strategist or strat(symbol), self.trader)
		self.log("initialized %s managers"%(len(symbols),))
		stish and setStaging(True)
		self.comptroller = Comptroller(self.price)
		self.harvester = Harvester(self)
		self.booker = Booker()
		rel.timeout(1, self.tick)

	def cross(self, sym, variety, reason, dimension="price"):
		self.crosses.append({
			"msg": "%s %s %s cross"%(sym, dimension, variety),
			"data": {
				"market": sym,
				"reason": reason,
				"variety": variety,
				"dimension": dimension
			}
		})

	def getCrosses(self):
		crox = self.crosses
		self.crosses = []
		return crox

	def warning(self, msg, data=None):
		self.warnings.append({ "msg": msg, "data": data })

	def getWarnings(self):
		warns = self.warnings
		self.warnings = []
		return warns

	def notice(self, msg, data=None):
		self.notices.append({ "msg": msg, "data": data })

	def getNotices(self):
		notes = self.notices
		self.notices = []
		return notes

	def cancel(self, token):
		self.log("cancel(%s)"%(token,))
		self.comptroller.cancel(token)

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

	def price(self, symbol, history="trade", fallback=None):
		return self.ndx.price(symbol, history=history, fallback=fallback) or self.ndx.faves.get(symbol, None)

	def prices(self):
		pz = {}
		syms = self.multifeed and self.multifeed.subscriptions or self.managers
		for sym in syms:
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
		act = self.actuary
		boo = self.booker
		ndx = self.ndx
		return {
			"ndx": ndx.faves,
			"gem": gem.status(),
			"bests": boo.bests,
			"totals": boo.totes,
			"orders": boo.orders,
			"scores": act.scores(),
			"actives": com.actives,
			"backlog": com.backlog,
			"fills": com.getFills(),
			"prices": self.prices(),
			"hints": act.predictions,
			"volumes": ndx.volumes(),
			"accountant": acc.counts,
			"harvester": har.status(),
			"refills": har.getRefills(),
			"weighted": ndx.weighteds(),
			"cancels": com.getCancels(),
			"candles": act.freshCandles(),
			"crosses": self.getCrosses(),
			"notices": self.getNotices(),
			"volvols": act.volatilities(),
			"warnings": self.getWarnings(),
			"strategists": self.stratuses(),
			"balances": acc.balances(self.price, "all")
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
		if not ask("accountsReady"):
			self.log("tick() waiting for accounts!")
		elif not ask("observersReady"):
			self.log("tick() waiting for observer histories!")
		else:
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
			self.actuary.hints(self.booker.totals())
		return True

def setOffice(**kwargs):
	office = Office(**(kwargs or selectPreset()))
	atexit.register(office.teardown)
	return office

def getOffice(index=None, strategy=None, symbols=["BTCUSD", "ETHUSD", "ETHBTC"]):
	strat = strategy or config.office.strategy
	prestrat = strat == "preset"
	if prestrat and index == None:
		return setOffice()
	return setOffice(**getConf(index, not prestrat and strat, symbols))

def load():
	initConfig()
	getOffice()
	start()

if __name__ == "__main__":
	load()