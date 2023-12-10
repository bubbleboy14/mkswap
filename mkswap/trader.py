from .backend import ask, predefs
from .agent import agencies
from .base import Worker

class Trader(Worker):
	def __init__(self, platform=predefs["platform"], live=True):
		self.recommendations = []
		self.live = live
		self.trades = []
		self.agent = agencies[platform]()

	def note(self, recommendation):
		# TODO: wrap in timestamped object...?
		self.trades.append(recommendation)

	def recommend(self, recommendation):
		self.log("recommended:", recommendation)
		self.recommendations.append(recommendation)

	def shouldTrade(self, recommendation): # TODO: actually evaluate
		self.log("assessing recommendation:", recommendation)
		return ask("affordable", recommendation)

	def trade(self, recommendation):
		self.log("TRADING", recommendation, "\n\n\n")
		self.note(recommendation)
		self.live and self.agent.trade(recommendation)

	def tick(self):
		# first rank in terms of payout
		for recommendation in self.recommendations:
			self.shouldTrade(recommendation) and self.trade(recommendation)
		self.recommendations = []