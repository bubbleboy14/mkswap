INNER = 10
OUTER = 40
LOUD = True

class Base(object):
	def __init__(self, symbol, recommender=None):
		self.symbol = symbol
		self.recommender = recommender

	def log(self, *msg):
		LOUD and print("Strategist[%s:%s] %s"%(self.__class__.__name__,
			self.symbol, " ".join([str(m) for m in msg])))

	def setRecommender(self, recommender):
		self.recommender = recommender

	def process(self, symbol, event, history):
		self.compare(symbol, event["side"], float(event["price"]), event, history)