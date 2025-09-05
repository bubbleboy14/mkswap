from rel.util import ask, listen
from .backend import predefs
from .agent import agencies
from .base import Worker
from .config import config

class Trader(Worker):
	def __init__(self, platform=predefs["platform"], live=True):
		self.recommendations = []
		self.live = live
		self.trades = []
		self.agent = agencies[platform]()
		listen("bestTrades", self.bestTrades)
		listen("trade", self.recommend)

	def note(self, recommendation):
		# TODO: wrap in timestamped object...?
		self.trades.append(recommendation)

	def order(self, sym, side, amount, price, force=False, strict=False):
		order = {
			"side": side,
			"symbol": sym,
			"price": price,
			"force": force,
			"strict": strict,
			"amount": amount
		}
		self.log("order(%s, %s, %s): %s"%(sym, side, amount, order))
		self.recommend(order)

	def bestTrades(self, sym, side, amountUSD=None, force=False, strict=False):
		amountUSD = amountUSD or config.trader.size
		prices = ask("bestPrices", sym, side)
		sym = sym.replace("/", "") # for ratio-derived prices
		if config.trader.book:
			prices["booksame"] = ask("bestOrder", sym, side, shift=True)
			prices["bookopp"] = ask("bestOrder", sym, side, opposite=True)
		amount = ask("fromUSD", sym, amountUSD)
		self.log("bestTrades(%s, %s, %s->%s)"%(sym, side, amountUSD, amount))
		for span in prices:
			self.order(sym, side, amount, prices[span], force, strict)
		return {
			"amount": amount,
			"prices": prices
		}

	def recommend(self, rec):
		self.log("recommend(%s)"%(rec,))
		self.recommendations.append(ask("resize", ask("unbook", rec)))

	def shouldTrade(self, recommendation):
		self.log("assessing recommendation:", recommendation)
		strict = "strict" in recommendation and recommendation.pop("strict")
		force = "force" in recommendation and recommendation.pop("force") or config.trader.force
		wise = ask("wise", recommendation, strict)
		if force == "auto":
			force = ask("wise", recommendation, True) == "very"
		return wise and ask("approved", recommendation, force)

	def trade(self, recommendation):
		self.log("TRADING", recommendation, "\n\n\n")
		self.note(recommendation)
		self.live and self.agent.trade(recommendation)

	def tick(self):
		# first rank in terms of payout
		for recommendation in self.recommendations:
			self.shouldTrade(recommendation) and self.trade(recommendation)
		self.recommendations = []