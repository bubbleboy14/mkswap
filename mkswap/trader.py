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
		listen("balanceTrade", self.recommend)

	def note(self, recommendation):
		# TODO: wrap in timestamped object...?
		self.trades.append(recommendation)

	def recommend(self, rec):
		self.log("recommend(%s)"%(rec,))
		mins = predefs["minimums"]
		size = rec["amount"]
		sym = rec["symbol"]
		if size < mins[sym]:
			rec["amount"] = mins[sym]
			self.log("order is too small! increased amount from", size, "to", rec["amount"])
		self.recommendations.append(rec)

	def shouldTrade(self, recommendation):
		self.log("assessing recommendation:", recommendation)
		force = "force" in recommendation and recommendation.pop() or config.trader.force
		return ask("affordable", recommendation, force)

	def trade(self, recommendation):
		self.log("TRADING", recommendation, "\n\n\n")
		self.note(recommendation)
		self.live and self.agent.trade(recommendation)

	def tick(self):
		# first rank in terms of payout
		for recommendation in self.recommendations:
			self.shouldTrade(recommendation) and self.trade(recommendation)
		self.recommendations = []