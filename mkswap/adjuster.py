from rel.util import ask, emit, listen
from .backend import predefs
from .base import Worker
from .config import config

class Adjuster(Worker):
	def __init__(self):
		self.counts = {
			"nudges": 0,
			"nudged": 0,
			"downsized": 0
		}
		listen("shouldWork", self.shouldWork)
		listen("realistic", self.realistic)
		listen("tooBad", self.tooBad)
		listen("resize", self.resize)
		listen("round", self.round)
		listen("score", self.score)

	def shouldNudge(self, nudge):
		if nudge == "auto":
			return not ask("overActive")
		return nudge

	def nudge(self, trade):
		sym = trade["symbol"]
		oprice = trade["price"]
		cprice = ask("price", sym)
		self.counts["nudges"] += 1
		pdiff = (oprice - cprice) * config.adjuster.nmult
		trade["price"] = self.round(oprice + pdiff, sym)
		self.log("nudge(%s -> %s)"%(oprice, trade["price"]), trade)

	def round(self, amount, sym="amount"):
		if sym == "amount":
			return round(amount, 6)
		return round(amount, predefs["sigfigs"].get(sym, 2))

	def tooBig(self, trade):
		if not ask("updateBalances", trade, "available", test=True):
			self.log("trade is too big!", trade)
			return True

	def resize(self, trade):
		if self.tooBig(trade):
			self.counts["downsized"] += 1
			emit("updateBalances", trade, "available", test=True, repair=True)
		mins = predefs["minimums"]
		size = trade["amount"]
		sym = trade["symbol"]
		if size < mins[sym]:
			trade["amount"] = mins[sym]
			self.log("order is too small! increased amount from", size, "to", trade["amount"])
		trade["amount"] = self.round(trade["amount"])
		trade["price"] = self.round(trade["price"], sym)
		return trade

	def realistic(self, trade, feeSide="maker", asScore=False, nudge=False, nudged=0):
		if self.tooBig(trade):
			return asScore and -1
		score = gain = ask("estimateGain", trade)
		fee = ask("estimateFee", trade, feeSide)
		if fee:
			score -= fee
		if score <= 0 and gain > 0 and self.shouldNudge(nudge) and nudged < 10:
			self.nudge(trade)
			if not nudged:
				self.counts["nudged"] += 1
			return self.realistic(trade, feeSide, asScore, nudge, nudged + 1)
		if asScore:
			return score
		return score > -config.adjuster.leeway

	def shouldWork(self, trade, force=False):
		if force:
			return not self.tooBig(trade)
		return self.realistic(trade, nudge=config.adjuster.nudge)

	def score(self, trade, feeSide="maker"):
		trade["score"] = self.realistic(trade, feeSide, True)
		# gain + actuaryscore + bookshift + ...
		return trade["score"]

	def tooBad(self, trade, feeSide="maker"):
		return self.score(trade, feeSide) < -config.adjuster.leeway