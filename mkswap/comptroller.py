import json, random, rel
from rel.util import ask, emit, listen, when
from .base import Feeder
from .gem import gem
from .config import config

orderNumber = random.randint(0, 10000)
SKIP_INITIAL = False

class Comptroller(Feeder):
	def __init__(self, pricer):
		self.actives = {}
		self.backlog = []
		self.cancels = []
		self.fills = []
		self.fees = None
		self.pricer = pricer
		self.platform = "gemorders"
		listen("rejected", self.rejected)
		listen("priceChange", self.prune)
		listen("enqueueOrder", self.enqueue)
		listen("estimateFee", self.estimateFee)
		listen("estimateGain", self.estimateGain)
		rel.timeout(10, self.longPrune)
		if config.comptroller.live:
			when("clientReady", gem.notional, self.setFees)
			when("balancesReady", self.start_feed)

	def setFees(self, fees):
		self.fees = {
			"maker": fees["api_maker_fee_bps"] / 10000,
			"taker": fees["api_taker_fee_bps"] / 10000
		}
		self.log("setFees(%s)"%(self.fees,))

	def proc(self, msg):
		coi = msg.get("client_order_id", None)
		etype = msg["type"]
		self.log("proc(%s, %s): %s"%(etype, coi, msg))
		if etype == "initial": # configurize...
			if SKIP_INITIAL:
				return self.log("proc() skipping initial")
			return self.reactivate(msg)
		if coi not in self.actives:
			return self.warn("unlisted %s %s"%(etype, coi), msg)
		order = self.actives[coi]
		order["status"] = etype
		if etype == "accepted":
			self.submitted(msg)
		elif etype == "rejected":
			self.rejected(coi, msg)
		elif etype == "fill":
			self.fill(order, msg)
		elif etype == "cancelled":
			reason = msg["reason"]
			self.log("proc() cancellation", reason)
			if reason != "Requested":
				self.cancels.append({ "msg": reason, "data": msg })
				if reason == "MakerOrCancelWouldTake":
					side = msg["side"]
					sym = msg["symbol"]
					price = ask("shifted", sym, side, msg["price"])
					reord = {
						"side": side,
						"symbol": sym,
						"force": True,
						"price": float(price),
						"amount": float(msg["original_amount"])
					}
					self.notice("reissuing %s %s @ %s"%(sym, side, price), reord)
					emit("trade", reord)
			self.cancelled(coi, reason)
		elif etype == "closed":
			self.log("proc(): trade closed", order)
			if "order_id" in order:
				emit("abort", "cancel %s %s"%(coi, order["order_id"]))
			else:
				self.warn("%s closed w/o order_id"%(coi,), order)
			del self.actives[coi]
		else:
			self.log("proc() unhandled event!")

	def getFills(self):
		fills = self.fills
		self.fills = []
		return fills

	def getCancels(self):
		cancs = self.cancels
		self.cancels = []
		return cancs

	def fill(self, order, msg):
		side = msg["side"]
		fdata = msg["fill"]
		fee = float(fdata["fee"])
		sym = msg["symbol"].upper()
		price = float(fdata["price"])
		feesym = fdata["fee_currency"]
		amount = float(fdata["amount"])
		remaining = float(msg["remaining_amount"])
		sig = "%s %s %s @ %s (%s %s fee)"%(side, amount, sym, price, fee, feesym)
		self.log("fill(%s)"%(sig,), order)
		if fdata["liquidity"] == "Taker":
			self.warn("Taker liquidity!", fdata)
		order["amount"] = remaining
		self.fills.append({
			"msg": sig,
			"data": msg
		})
		emit("orderFilled", {
			"feesym": feesym,
			"fee": fee,
			"side": side,
			"symbol": sym,
			"price": price,
			"amount": amount,
			"remaining": remaining,
			"order_id": order["order_id"],
			"oprice": float(order["price"]),
			"client_order_id": order["client_order_id"],
			"score": order.get("score", 0) # sensible fallback right?
		})

	def reactivate(self, msg):
		self.actives[msg["client_order_id"]] = order = {
			"status": "booked",
			"side": msg["side"],
			"price": msg["price"],
			"type": msg["order_type"],
			"order_id": msg["order_id"],
			"symbol": msg["symbol"].upper(),
			"amount": msg["remaining_amount"],
			"client_order_id": msg["client_order_id"]
		}
		self.log("reactivate()", order)
		emit("approved", order, True)
		emit("orderActive", order)

	def message(self, msgs):
		self.log("message:", msgs)
		if type(msgs) is not list:
			return config.base.unspammed or self.log("skipping non-list")
		for msg in msgs:
			self.proc(msg)
		self.refill()

	def estimateFee(self, trade, feeSide="taker"):
		if not self.fees:
			return None
		sym = trade["symbol"]
		if sym.endswith("USD"):
			price = float(trade["price"])
		else:
			price = ask("price", sym[:3], True)
		amountUSD = price * float(trade["amount"])
		return amountUSD * self.fees[feeSide]

	def estimateGain(self, trade):
		sym = trade["symbol"]
		side = trade["side"]
		price = float(trade["price"])
		curprice = self.pricer(sym)
		gain = (price - curprice) * float(trade["amount"])
		if side == "buy":
			gain *= -1
		if not sym.endswith("USD"):
			gain *= ask("price", sym[3:], True)
		return gain

	def score(self, trade, feeSide="taker"):
		trade["score"] = ask("realistic", trade, feeSide, True)
		return trade["score"]

	def pruneActives(self, limit=None, undupe=False):
		cancels = []
		skips = 0
		dupes = 0
		prices = {}
		for tnum in self.actives:
			trade = self.actives[tnum]
			if trade.get("status", None) == "booked":
				tp = trade["price"]
				if tp in prices:
					prices[tp]["orders"].append(tnum)
					dupes += 1
				else:
					prices[tp] = {
						"cancel": False,
						"orders": [tnum]
					}
					sym = trade["symbol"]
					curprice = self.pricer(sym)
					if not curprice:
						self.log("waiting for", sym, "prices")
						skips += 1
						continue
					if not sym.endswith("USD"):
						if not (ask("price", sym[:3], True) and ask("price", sym[3:], True)):
							self.log("waiting for", sym, "prices")
							skips += 1
							continue
					s = self.score(trade, "maker")
					toofar = False
					if limit:
						ratio = float(tp) / curprice
						toofar = abs(1 - ratio) > limit
					prices[tp]["cancel"] = s < -config.comptroller.leeway or toofar
			else:
				skips += 1
		for price in prices:
			pset = prices[price]
			ords = pset["orders"]
			if pset["cancel"]:
				cancels += ords
			elif undupe and len(ords) > 1:
				ords.sort(key = lambda tnum : -float(self.actives[tnum]["amount"]))
				self.log("unduping", len(ords), "at", price)
				cancels += ords[1:]
		for tnum in cancels:
			self.cancel(tnum)
		return skips, cancels, dupes

	def longPrune(self):
		lim = config.comptroller.plimit
		oa = ask("overActive", 0)
		if oa:
			lim = lim / (10 * oa)
		skips, cancels, dupes = self.pruneActives(lim, True)
		self.log("longPrune(oa=%s,lim=%s):"%(round(oa, 3), round(lim, 4)),
			len(cancels), "cancels;", dupes, "dupes;", skips, "skips")
		return True

	def prune(self):
		if not ask("accountsReady"):
			return self.log("prune() waiting - accounts not ready")
		icount = len(self.backlog)
		# backlog: rate, filter, and sort
		for trade in self.backlog:
			if self.score(trade) <= 0:
				emit("orderCancelled", trade, True)
		self.backlog = list(filter(lambda t : t["score"] > 0, self.backlog))
		blsremoved = icount - len(self.backlog)
		self.backlog.sort(key=lambda t : t["score"])
		# actives: rate and cancel (as necessary)
		skips, cancels, dupes = self.pruneActives()
		self.log("prune():", blsremoved, "backlogged - now at",
			len(self.backlog), "; and", len(cancels), "actives - now at", len(self.actives.keys()),
			"; skipped", skips, "uninitialized orders")

	def cancel(self, tnum):
		trade = self.actives[tnum]
		if trade.get("status", None) == "cancelling":
			return self.log("cancel(%s) aborted (already cancelling)"%(tnum,), trade)
		self.log("cancel(%s)"%(tnum,), trade)
		trade["status"] = "cancelling"
		config.comptroller.live and gem.cancel(trade)

	def cancelled(self, tnum, reason=None):
		trade = self.actives[tnum]
		msg = "cancelled(%s)"%(tnum,)
		if trade.get("status", None) != "cancelling":
			if reason:
				msg = "%s %s"%(msg, reason)
			else:
				msg = "%s unexpected!"%(msg,)
		self.log(msg, trade)
		emit("orderCancelled", trade)

	def rejected(self, coi, msg):
		self.warn("rejected(%s): %s"%(coi, msg["reason"]), msg)
		if coi in self.actives:
			emit("orderRejected", self.actives[coi])
			del self.actives[coi]
		else:
			self.log(coi, "already removed!")

	def cancelAll(self):
		cfg = config.comptroller
		akeys = list(self.actives.keys())
		self.log("cancelAll() cancelling", len(akeys), "active orders")
		for tnum in akeys:
			if cfg.canceleach:
				self.cancel(tnum)
			else:
				self.cancelled(tnum, "blanket cancel")
				trade = self.actives[tnum]
				if "order_id" in trade:
					emit("abort", "cancel %s %s"%(tnum, trade["order_id"]))
				else:
					emit("abort", "new %s"%(tnum,))
				del self.actives[tnum]
		if cfg.live and not cfg.canceleach:
			gem.cancelAll() # TODO: get accepted/rejected cancels from return val

	def refill(self):
		self.log("refill(%s)"%(len(self.backlog),))
		while self.backlog and (len(self.actives.keys()) < config.comptroller.actives):
			self.submit(self.backlog.pop(0))

	def submit(self, trade):
		global orderNumber
		orderNumber += 1
		self.log("submit(%s)"%(orderNumber,), trade)
		self.actives[str(orderNumber)] = trade
		trade["client_order_id"] = str(orderNumber)
		config.comptroller.live and gem.trade(trade)#, self.submitted)

	def submitted(self, resp):
		coid = resp["client_order_id"]
		oid = resp["order_id"]
		msg = "submitted(%s, %s)"%(coid, oid)
		if coid not in self.actives:
			return self.warn("%s order not found!"%(msg,), resp)
		trade = self.actives[coid]
		if "order_id" in trade:
			return self.warn("%s exists (%s)"%(msg, trade["status"]))
		emit("abort", "new %s"%(coid,))
		trade["order_id"] = oid
		self.log(msg, trade, resp)
		emit("orderActive", trade)

	def enqueue(self, trade):
		self.backlog.append(trade)
		self.log("enqueue()", len(self.backlog), trade)
		self.refill()