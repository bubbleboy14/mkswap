from ..backend import log

INNER = 10
OUTER = 40
LOUD = True

def setInner(inner):
	log("setInner(%s)"%(inner,))
	global INNER
	INNER = inner

def setOuter(outer):
	log("setOuter(%s)"%(outer,))
	global OUTER
	OUTER = outer

def setLoud(loud):
	log("setLoud(%s)"%(loud,))
	global LOUD
	LOUD = loud

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