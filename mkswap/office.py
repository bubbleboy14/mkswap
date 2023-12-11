from pprint import pformat
from .backend import rel, start, getconf, predefs
from .comptroller import Comptroller
from .accountant import Accountant
from .strategist import strategies
from .manager import Manager
from .trader import Trader
from .base import Worker

VERBOSE = False

class Office(Worker):
	def __init__(self, platform=predefs["platform"], symbols=[], strategy=predefs["strategy"], globalStrategy=False, globalTrade=False):
		self.platform = platform
		self.symbols = symbols
		self.accountant = Accountant(platform)
		self.trader = globalTrade and Trader(platform)
		trec = self.trader and self.trader.recommend
		strat = strategies[strategy]
		self.stratname = strategy
		self.strategist = globalStrategy and strat(symbols, trec)
		self.managers = {}
		for symbol in symbols:
			self.managers[symbol] = Manager(platform, symbol, self.review,
				self.strategist or strat(symbol, trec), self.trader)
		self.log("initialized %s managers"%(len(symbols),))
		self.comptroller = Comptroller(self.price)
		rel.timeout(1, self.tick)

	def sig(self):
		return "Office[%s]"%(self.platform,)

	def price(self, symbol):
		return self.managers[symbol].latest["price"]

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
		return {
			"counts": acc.counts,
			"strategists": self.stratuses(),
			"balances": acc.balances(self.price)
		}

	def assess(self, trade, curprice=None):
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
		return direction, abs(diff) * trade["amount"] * direction

	def review(self, symbol=None, trader=None, curprice=None):
		mans = self.managers
		if symbol:
			man = mans[symbol]
			trader = man.trader
			curprice = man.latest["price"]
		else:
			trader = trader or self.trader
		tz = trader.trades
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
		lstr.append(pformat(self.accountant.balances(self.price)))
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

if __name__ == "__main__":
	Office(**getconf())
	start()