from rel.util import emit
from ..base import Worker
from ..config import config

class Base(Worker):
	def __init__(self, symbol, recommender=None):
		self.stats = {}
		self.symbol = symbol
		self.recommender = recommender

	def sig(self):
		return "Strategist[%s:%s]"%(self.__class__.__name__, self.symbol)

	def log(self, *msg):
		config.strategy.base.loud and Worker.log(self, *msg)

	def setRecommender(self, recommender):
		self.recommender = recommender

	def process(self, symbol, event, history):
		self.compare(symbol, event["side"], float(event["price"]), event, history)

	def compare(self, symbol, side, price, eobj, history):
		emit("quote", symbol, price, volume=float(eobj["amount"])) # anything else?