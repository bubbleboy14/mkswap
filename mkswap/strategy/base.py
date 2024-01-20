from rel.util import emit
from ..backend import log

LOUD = False

def setLoud(loud):
	log("setLoud(%s)"%(loud,))
	global LOUD
	LOUD = loud

class Base(object):
	def __init__(self, symbol, recommender=None):
		self.stats = {}
		self.symbol = symbol
		self.recommender = recommender

	def log(self, *msg):
		LOUD and print("Strategist[%s:%s] %s"%(self.__class__.__name__,
			self.symbol, " ".join([str(m) for m in msg])))

	def setRecommender(self, recommender):
		self.recommender = recommender

	def process(self, symbol, event, history):
		self.compare(symbol, event["side"], float(event["price"]), event, history)

	def compare(self, symbol, side, price, eobj, history):
		emit("quote", symbol, price) # anything else?