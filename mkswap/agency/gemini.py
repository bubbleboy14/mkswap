from ..base import Worker

class Gemini(Worker):
	def trade(self, trade):
		self.log("TRADE:", trade)