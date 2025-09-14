from rel.util import ask, emit, listen
from .base import Base
from ..config import config

scfg = config.strategy.slosh

class Slosh(Base):
	def __init__(self, symbol):
		self.top, self.bottom = symbol
		self.syms = [self.top[:3], self.bottom[:3]]
		self.onesym = "".join(self.syms)
		self.ratsym = "/".join(self.syms)
		self.shouldUpdate = False
		emit("observe", self.onesym)
		emit("tellMeWhen", self.onesym, "volatility", scfg.vcutoff, self.hardsell)
		emit("tellMeWhen", self.onesym, "volatility", -scfg.vcutoff, self.hardbuy)
		emit("overunders", [self.onesym, self.top, self.bottom], self.trades)
		listen("cross", self.cross)
		Base.__init__(self, symbol)

	def cross(self, sym, variety, reason, dimension="price"):
		self.log("cross(%s, %s, %s) %s"%(sym, dimension, variety, reason))
		isup = variety == "golden"
		traj = ask("metric", sym, "trajectory")
		if isup and traj == "undersold":
			side = "buy"
		elif not isup and traj == "overheated":
			side = "sell"
		else:
			return self.log("waiting for extremes...")
		note = "%s %s %s cross while %s (mfi=%s)"%(sym, variety,
			dimension, traj, ask("metric", sym, "mfi"))
		self.trades(side, sym, traj, note, "auto")

	def trade(self, order, reason="slosh", note=None):
		self.inc(reason)
		note = note or "volatility: %s"%(self.stats["volatility"],)
		order["rationale"] = {
			"reason": reason,
			"notes": [note]
		}
		emit("trade", order)
		self.notice("%s %s %s"%(reason, order["side"], order["symbol"]), order)

	def trades(self, side, sym=None, reason="hardslosh", note=None, force=False):
		self.inc(reason)
		sym = sym or self.onesym
		note = note or "volatility: %s"%(ask("metric", sym, "volatility"),)
		self.notice("%s %s %s"%(reason, side, sym), ask("bestTrades", sym,
			side, force=force, reason=reason, note=note))

	def hardsell(self):
		self.trades("sell", force=True)

	def hardbuy(self):
		self.trades("buy", force=True)

	def buysell(self, buysym, sellsym, size=10):
		buyprice = ask("bestPrice", buysym, "buy")
		sellprice = ask("bestPrice", sellsym, "sell")
		self.trade({
			"side": "sell",
			"force": "auto",
			"symbol": sellsym,
			"price": sellprice,
			"amount": size / sellprice
		})
		self.trade({
			"side": "buy",
			"force": "auto",
			"symbol": buysym,
			"price": buyprice,
			"amount": size / buyprice
		})

	def oneswap(self, side, size=10):
		vmult = config.strategy.slosh.vmult
		price = ask("bestPrice", self.onesym, side)
		botprice = ask("price", self.bottom)
		amount = size / (price * botprice)
		self.trade({
			"side": side,
			"price": price,
			"force": "auto",
			"amount": amount,
			"symbol": self.onesym
		})

	def shouldOneSwap(self, side):
		if scfg.oneswap != "auto":
			return scfg.oneswap
		bias = self.stats["bias"]
		isbuy = side == "buy"
		bigone = bias > 0
		top, bot = self.syms
		sellsym = isbuy and bot or top
		sellfs = ask("fullSym", sellsym)
		bals = ask("balances")
		for sec in bals:
			s = bals[sec]
			if ask("tooLow", s["USD"], half=True):
				return True
			usdval = ask("getUSD", sellfs, s[sellsym])
			if usdval and ask("tooLow", usdval):
				return False
		if abs(bias) < scfg.randlim:
			return "both"
		if isbuy:
			return not bigone
		return bigone

	def swap(self, size=10):
		side = "sell"
		if size < 0:
			size *= -1
			side = "buy"
		shouldOne = self.shouldOneSwap(side)
		shouldOne and self.oneswap(side, size)
		if not shouldOne or shouldOne == "both":
			if side == "sell":
				self.buysell(self.bottom, self.top, size)
			else:
				self.buysell(self.top, self.bottom, size)

	def upStats(self):
		mad = self.stat("mad", ask("rmad", self.top, self.bottom))
		sigma = self.stat("sigma", ask("rsigma", self.top, self.bottom))
		self.stat("turb", ask("rvolatility", self.top, self.bottom, mad))
		self.stat("volatility", ask("rvolatility", self.top, self.bottom, sigma))
		self.stat("bias", (ask("price", self.onesym) / ask("price", self.ratsym)) - 1)

	def hilo(self):
		self.upStats()
		volatility = self.stats["volatility"]
		if abs(volatility) + abs(self.stats["bias"]) > scfg.vcutoff:
			self.swap(volatility * scfg.vmult)

	def tick(self, history=None):
		if not self.shouldUpdate:
			return
		self.shouldUpdate = False
		if ask("hadEnough", self.top, self.bottom):
			self.hilo()

	def compare(self, symbol, side, price, eobj, history):
		self.shouldUpdate = True
		self.log("compare", symbol, side, price, eobj)
		Base.compare(self, symbol, side, price, eobj, history)
		rdata = ask("ratio", self.top, self.bottom, True)
		if not rdata:
			return self.log("skipping ratio (waiting for history)")
		ratcur = round(rdata["current"], 5) # occasionally rounds to 0...
		ratcur and emit("quote", self.ratsym, ratcur, fave=True)
