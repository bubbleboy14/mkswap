from .base import Base, OUTER, LONG
from ..backend import log

TRADE_SIZE = 10
RSI_PERIOD = 14

def setSize(size):
	log("setSize(%s)"%(size,))
	global TRADE_SIZE
	TRADE_SIZE = size

def setPeriod(period):
	log("setPeriod(%s)"%(period,))
	global RSI_PERIOD
	RSI_PERIOD = period

class RSI(Base):
	def __init__(self, symbol, recommender=None):
		self.latest = None
		self.lastrec = None
		Base.__init__(self, symbol, recommender)

	def weighted_average(self, _history):
		price_remaining = 0
		remaining_total = 0
		for hist in _history:
			price_remaining += hist['price'] * hist['remaining']
			remaining_total += hist['remaining']
		return remaining_total and price_remaining / remaining_total or 0 # TODO: actual fix

	def status(self):
		return {
			"latest": self.latest,
			"lastrec": self.lastrec
		}

	def compare(self, symbol, side, price, eobj, history):
		remaining = float("remaining" in eobj and eobj["remaining"] or eobj["size"])
		self.log("compare", side, price, remaining)
		hs = history[side]
		hwa = history["w_average"]
		self.latest = {
			"price": price,
			"remaining": remaining
		}
		hs.append(self.latest)
		hwa.append(self.weighted_average(hs))
		self.log(side, "weighted average (full):", hwa[-1])
		if len(hs) >= LONG:
			w_far = self.weighted_average(hs[-LONG:])
			w_near = self.weighted_average(hs[-OUTER:])
			self.log(side, "far average (last", LONG, "):", w_far)
			self.log(side, "near average (last", OUTER, "):", w_near)
			rec = False
			if w_near > w_far:
				self.log("near average > far average -> upswing!")
				if side in ["ask", "BUY", "SELL"] and price < w_near:
					self.log("ask price < average -> BUY!!!!")
					rec = "buy"
			else:
				self.log("near average < far average -> downswing!")
				if side in ["bid", "BUY", "SELL"] and price > w_near:
					self.log("bid price > average -> SELL!!!!")
					rec = "sell"
			if rec:
				self.lastrec = {
					"side": rec,
					"price": price,
					"symbol": symbol,
					"amount": TRADE_SIZE
				}
				self.recommender(self.lastrec)

	def tick(self, history):
		_was = history['w_average']
		was = history['1_w_average']
		if len(_was):
			was.append(_was[-1])
		lwas = len(was)
		if lwas:
			changes = {
				"upward": [],
				"downward": [],
				"relative_strength": []
			}
			self.log("tick", was[-1])
			if lwas > (RSI_PERIOD + 1):
				for i in range(RSI_PERIOD + 1):
					start = 1 + RSI_PERIOD - i
					s = was[-(start - 1)] - was[-start]
					if s >= 0:
						changes['upward'].append(s)
					else:
						changes['downward'].append(abs(s))
				up_mean = sum(changes['upward']) / RSI_PERIOD
				down_mean = sum(changes['downward']) / RSI_PERIOD
				if down_mean:
					changes['relative_strength'].append(up_mean/down_mean)
					rsi = 100 - (100 / (1 + changes['relative_strength'][-1]))
					self.log(rsi, "\n")