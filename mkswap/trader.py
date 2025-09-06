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
		self.judgments = {}
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
		quotes = ask("bestPrices", sym, side)
		sym = sym.replace("/", "") # for ratio-derived prices
		if config.trader.book:
			quotes["book"] = ask("bestOrder", sym, side, average=True)
		amount = ask("fromUSD", sym, amountUSD / len(quotes.keys()))
		self.log("bestTrades(%s, %s, %s->%s)"%(sym, side, amountUSD, amount))
		prices = {}
		for span, price in quotes.items():
			if price not in prices:
				prices[price] = []
			prices[price].append(span)
		for price, spans in prices.items():
			self.order(sym, side, amount * len(spans), price, force, strict)
		return {
			"amount": amount,
			"prices": prices
		}

	def recommend(self, rec):
		self.log("recommend(%s)"%(rec,))
		self.recommendations.append(rec)

	def wise(self, rec, strict=False):
		side = rec["side"]
		sym = rec["symbol"]
		kind = strict and "strict" or "lax"
		if kind not in self.judgments:
			self.judgments[kind] = {}
		if sym not in self.judgments[kind]:
			self.judgments[kind][sym] = {}
		if side not in self.judgments[kind][sym]:
			self.judgments[kind][sym][side] = ask("wise", rec, strict)
		return self.judgments[kind][sym][side]

	def shouldTrade(self, recommendation):
		self.log("assessing recommendation:", recommendation)
		strict = "strict" in recommendation and recommendation.pop("strict")
		force = "force" in recommendation and recommendation.pop("force") or config.trader.force
		wise = self.wise(recommendation, strict)
		if force == "auto":
			force = self.wise(recommendation, True) == "very"
		return wise and ask("approved", recommendation, force)

	def trade(self, recommendation):
		self.log("TRADING", recommendation, "\n\n\n")
		self.note(recommendation)
		self.live and self.agent.trade(recommendation)

	def tick(self):
		# first rank in terms of payout
		for recommendation in self.recommendations:
			rec = ask("resize", ask("unbook", recommendation))
			self.shouldTrade(rec) and self.trade(rec)
		self.recommendations = []
		self.judgments = {}