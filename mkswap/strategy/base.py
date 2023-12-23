from rel.util import listen
from ..backend import log

INNER = 3
OUTER = 10
LONG = 40
LOUD = False

def setInner(inner):
	log("setInner(%s)"%(inner,))
	global INNER
	INNER = inner

def setOuter(outer):
	log("setOuter(%s)"%(outer,))
	global OUTER
	OUTER = outer

def setLong(howlong):
	log("setLong(%s)"%(howlong,))
	global LONG
	LONG = howlong

def setLoud(loud):
	log("setLoud(%s)"%(loud,))
	global LOUD
	LOUD = loud

side2height = {
	"buy": "low",
	"sell": "high"
}

def getSpan(span):
	return {
		"long": LONG,
		"inner": INNER,
		"outer": OUTER
	}[span]

class Base(object):
	def __init__(self, symbol, recommender=None):
		self.histories = {}
		self.symbol = symbol
		self.recommender = recommender
		if type(symbol) is not list:
			symbol = [symbol]
		for sym in symbol:
			listen("bestPrice%s"%(sym,), self.bestPrice)
			listen("bestPrices%s"%(sym,), self.bestPrices)

	def log(self, *msg):
		LOUD and print("Strategist[%s:%s] %s"%(self.__class__.__name__,
			self.symbol, " ".join([str(m) for m in msg])))

	def ave(self, limit=None, collection=None):
		rats = collection or self.allratios
		if limit:
			rats = rats[-limit:]
		return sum(rats) / len(rats)

	def bestPrice(self, sym, side, span="inner"):
		return round(self.histories[sym][span][side2height[side]], 6)

	def bestPrices(self, sym, side):
		d = {}
		for span in ["inner", "outer", "long"]:
			d[span] = self.bestPrice(sym, side, span)
		return d

	def setRecommender(self, recommender):
		self.recommender = recommender

	def process(self, symbol, event, history):
		self.compare(symbol, event["side"], float(event["price"]), event, history)

	def compare(self, symbol, side, price, eobj, history):
		if symbol not in self.histories:
			self.histories[symbol] = {
				"all": [],
				"long": {},
				"outer": {},
				"inner": {}
			}
		symhis = self.histories[symbol]
		symhis["current"] = price
		symhis["all"].append(price)
		symhis["average"] = self.ave(collection=symhis["all"])
		for span in ["inner", "outer", "long"]:
			stretch = symhis["all"][-getSpan(span):]
			symhis[span]["high"] = max(stretch)
			symhis[span]["low"] = min(stretch)