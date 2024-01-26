import json, random, rel
from rel.util import ask, emit, listen
from .backend import log
from .base import Feeder
from .gem import gem

LIVE = False
PRUNE_LIMIT = 0.1
ACTIVES_ALLOWED = 10
orderNumber = random.randint(0, 2000)
SKIP_INITIAL = False

def setLive(islive):
	log("setLive(%s)"%(islive,))
	global LIVE
	LIVE = islive

def setPruneLimit(pl):
	log("setPruneLimit(%s)"%(pl,))
	global PRUNE_LIMIT
	PRUNE_LIMIT = pl

def setActives(actall):
	log("setActives(%s)"%(actall,))
	global ACTIVES_ALLOWED
	ACTIVES_ALLOWED = actall

class Comptroller(Feeder):
	def __init__(self, pricer):
		self.actives = {}
		self.backlog = []
		self.cancels = []
		self.fills = []
		self.fees = None
		self.pricer = pricer
		self.cancelling = set()
		listen("rejected", self.rejected)
		listen("priceChange", self.prune)
		listen("enqueueOrder", self.enqueue)
		self.feed("gemorders")
		rel.timeout(10, self.longPrune)
		LIVE and gem.notional(self.setFees)

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
			return self.warn("unlisted %s %s"%(etype, coi))
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
			self.cancelled(coi)
		elif etype == "closed":
			self.log("proc(): trade closed", order)
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
			"oprice": float(order["price"])
		}, not remaining)

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
		emit("affordable", order)
		emit("orderActive", order)

	def on_message(self, ws, msgs):
		msgs = json.loads(msgs)
		self.log("message:", msgs)
		if type(msgs) is not list:
			return self.log("skipping non-list")
		for msg in msgs:
			self.proc(msg)
		self.refill()

	def score(self, trade, feeSide="taker"):
		sym = trade["symbol"]
		side = trade["side"]
		sig = "score(%s %s %s)"%(sym, side, feeSide)
		if not ask("realistic", trade):
			trade["score"] = -1
			self.log("%s unrealistic!"%(sig,), trade)
			return trade["score"]
		curprice = self.pricer(sym)
		if not curprice:
			return
		price = float(trade["price"])
		trade["score"] = price - curprice
		if side == "buy":
			trade["score"] *= -1
		if self.fees:
			if not sym.endswith("USD"):
				price = ask("price", sym[:3], True)
			amountUSD = price * float(trade["amount"])
			fee = amountUSD * self.fees[feeSide]
			trade["score"] *= amountUSD
			trade["score"] -= fee
			if trade["score"] < 0:
				self.log("%s bad score:"%(sig,), trade["score"], "fee:", fee, trade)
		return trade["score"]

	def pruneActives(self, limit=None, undupe=False):
		cancels = []
		skips = 0
		dupes = 0
		prices = set()
		for tnum in self.actives:
			trade = self.actives[tnum]
			if trade.get("status", None) == "booked":
				tp = trade["price"]
				if undupe and tp in prices:
					cancels.append(tnum)
					dupes += 1
				else:
					prices.add(tp)
					s = self.score(trade, "maker")
					if not s:
						skips += 1
						continue
					toofar = False
					if limit:
						ratio = float(tp) / self.pricer(trade["symbol"])
						toofar = abs(1 - ratio) > limit
					if s < 0 or toofar:
						cancels.append(tnum)
			else:
				skips += 1
		for tnum in cancels:
			self.cancel(tnum)
		return skips, cancels, dupes

	def longPrune(self):
		skips, cancels, dupes = self.pruneActives(PRUNE_LIMIT, True)
		self.log("longPrune():", len(cancels), "cancels;", dupes, "dupes;", skips, "skips")
		return True

	def prune(self):
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
		if tnum in self.cancelling:
			return# self.log("cancel(%s) aborted (already cancelling)"%(tnum,))
		self.cancelling.add(tnum)
		trade = self.actives[tnum]
		self.log("cancel(%s)"%(tnum,), trade)
		LIVE and gem.cancel(trade)

	def cancelled(self, tnum, reason=None):
		trade = self.actives[tnum]
		msg = "cancelled(%s)"%(tnum,)
		if tnum in self.cancelling:
			self.cancelling.remove(tnum)
		elif reason:
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
		akeys = list(self.actives.keys())
		self.log("cancelAll() cancelling", len(akeys), "active orders")
		for tnum in akeys:
			self.cancelled(tnum, "blanket cancel")
			trade = self.actives[tnum]
			if "order_id" in trade:
				emit("preventRetry", "cancel %s"%(tnum,))
			else:
				emit("preventRetry", "new %s"%(tnum,))
			del self.actives[tnum]
		LIVE and gem.cancelAll() # TODO: get accepted/rejected cancels from return val

	def refill(self):
		self.log("refill(%s)"%(len(self.backlog),))
		while self.backlog and (len(self.actives.keys()) < ACTIVES_ALLOWED):
			self.submit(self.backlog.pop(0))

	def submit(self, trade):
		global orderNumber
		orderNumber += 1
		self.log("submit(%s)"%(orderNumber,), trade)
		self.actives[str(orderNumber)] = trade
		trade["client_order_id"] = str(orderNumber)
		LIVE and gem.trade(trade)#, self.submitted)

	def submitted(self, resp):
		coid = resp["client_order_id"]
		oid = resp["order_id"]
		msg = "submitted(%s, %s)"%(coid, oid)
		if coid not in self.actives:
			return self.warn("%s order not found!"%(msg,), resp)
		trade = self.actives[coid]
		if "order_id" in trade:
			return self.warn("%s exists (%s)"%(msg, trade["status"]))
		emit("preventRetry", "new %s"%(coid,))
		trade["order_id"] = oid
		self.log(msg, trade, resp)
		emit("orderActive", trade)

	def enqueue(self, trade):
		self.backlog.append(trade)
		self.log("enqueue()", len(self.backlog), trade)
		self.refill()