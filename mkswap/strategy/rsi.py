from rel.util import emit
from .base import Base
from ..backend import predefs
from ..ndx import getSpan
from ..config import config

class RSI(Base):
	def weighted_average(self, _history):
		price_remaining = 0
		remaining_total = 0
		for hist in _history:
			price_remaining += hist['price'] * hist['remaining']
			remaining_total += hist['remaining']
		wa = remaining_total and price_remaining / remaining_total or 0 # TODO: actual fix
		emit("fave", "W%s"%(self.symbol,), wa)
		return wa

	def compare(self, symbol, side, price, eobj, history):
		remaining = float(eobj["amount"])
		self.log("compare", side, price, remaining)
		hs = history[side]
		hwa = history["w_average"]
		self.stats["latest"] = {
			"price": price,
			"remaining": remaining
		}
		hs.append(self.stats["latest"])
		hwa.append(self.weighted_average(hs))
		self.log(side, "weighted average (full):", hwa[-1])
		lspan = getSpan("long")
		ospan = getSpan("outer")
		if len(hs) >= lspan:
			w_far = self.weighted_average(hs[-ospan:])
			w_near = self.weighted_average(hs[-lspan:])
			self.log(side, "far average (last", ospan, "):", w_far)
			self.log(side, "near average (last", lspan, "):", w_near)
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
				self.stats["lastrec"] = {
					"side": rec,
					"price": price,
					"symbol": symbol,
					"amount": config.strategy.rsi.size * predefs["minimums"][symbol]
				}
				emit("trade", self.stats["lastrec"])
		Base.compare(self, symbol, side, price, eobj, history)

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
			period = config.strategy.rsi.period
			if lwas > (period + 1):
				for i in range(period + 1):
					start = 1 + period - i
					s = was[-(start - 1)] - was[-start]
					if s >= 0:
						changes['upward'].append(s)
					else:
						changes['downward'].append(abs(s))
				up_mean = sum(changes['upward']) / period
				down_mean = sum(changes['downward']) / period
				if down_mean:
					changes['relative_strength'].append(up_mean/down_mean)
					rsi = 100 - (100 / (1 + changes['relative_strength'][-1]))
					self.log(rsi, "\n")