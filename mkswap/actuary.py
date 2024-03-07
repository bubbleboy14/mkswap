from rel.util import ask
from .base import Worker

class Actuary(Worker):
	def __init__(self):
		self.ratios = {}
		self.predictions = {}

	def sigma(self, symbol, cur):
		hist = self.ratios[symbol]["history"]
		sqds = []
		for rat in hist:
			d = rat - cur
			sqds.append(d * d)
		return sqrt(ask("ave", sqds))

	def volatility(self, symbol, cur):
		rdata = self.ratios[symbol]
		return (cur - ask("ave", rdata["history"])) / rdata["sigma"]

	def hints(self, vscores):
		for sym in vscores:
			if sym not in self.ratios:
				self.ratios[sym] = {
					"history": []
				}
			rat = vscores[sym]["ask"] / vscores[sym]["bid"]
			if self.ratios[sym]["history"]:
				self.ratios[sym]["sigma"] = self.sigma(sym, rat)
				vol = self.ratios[sym]["volatility"] = self.volatility(sym, rat)
				if vol > 0.5:
					self.prediction[sym] = "buy"
				elif vol < -0.5:
					self.prediction[sym] = "sell"
				else:
					self.prediction[sym] = "chill"
			self.ratios[sym]["history"].append(rat)
		return self.predictions