import json, random, rel
from .backend import log, listen, emit
from .base import Feeder
from .gem import gem

LIVE = False
PRUNE_LIMIT = 0.1
ACTIVES_ALLOWED = 10
orderNumber = random.randint(0, 500)

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
		self.pricer = pricer
		listen("priceChange", self.prune)
		listen("enqueueOrder", self.enqueue)
		self.feed("gemorders")
		rel.timeout(10, self.longPrune)

	def proc(self, msg):
		coi = msg.get("client_order_id", None)
		if not coi:
			return self.log("proc(%s): NO client_order_id!!!"%(msg,))
		if coi not in self.actives:
			return self.log("proc(%s): unlisted client_order_id!!!"%(msg,))
		order = self.actives[coi]
		etype = msg["type"]
		if msg.get("is_cancelled", None):
			reason = msg["reason"]
			self.log("proc() cancellation", reason)
			self.cancels.insert(0, reason)
			self.cancels = self.cancels[-10:]
			self.cancel(coi, False)
		elif etype == "closed":
			self.log("proc(): trade closed", order)
			emit("orderFilled", order)
			del self.actives[coi]
		else:
			self.log("proc(): %s"%(etype,))

	def on_message(self, ws, msgs):
		msgs = json.loads(msgs)
		self.log("message:", msgs)
		if type(msgs) is not list:
			return self.log("skipping non-list")
		for msg in msgs:
			self.proc(msg)
		self.refill()

	def score(self, trade):
		sym = trade["symbol"]
		curprice = self.pricer(sym)
		trade["score"] = float(trade["price"]) - curprice
		if trade["side"] == "buy":
			trade["score"] *= -1
		return trade["score"]

	def pruneActives(self, limit=None):
		cancels = []
		skips = 0
		for tnum in self.actives:
			trade = self.actives[tnum]
			if "order_id" in trade:
				s = self.score(trade)
				toofar = False
				if limit:
					ratio = float(trade["price"]) / self.pricer(trade["symbol"])
					toofar = abs(1 - ratio) > limit
				if s < 0 or toofar:
					cancels.append(tnum)
			else:
				skips += 1
		for tnum in cancels:
			self.cancel(tnum)
		return skips, cancels

	def longPrune(self):
		skips, cancels = self.pruneActives(PRUNE_LIMIT)
		self.log("longPrune():", len(cancels), "cancels;", skips, "skips")
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
		skips, cancels = self.pruneActives()
		self.log("prune():", blsremoved, "backlogged - now at",
			len(self.backlog), "; and", len(cancels), "actives - now at", len(self.actives.keys()),
			"; skipped", skips, "uninitialized orders")

	def cancel(self, tnum, tellgem=True):
		trade = self.actives[tnum]
		LIVE and tellgem and gem.cancel(trade)
		self.log("cancel()", trade)
		emit("orderCancelled", trade)
		del self.actives[tnum]

	def withdraw(self):
		akeys = list(self.actives.keys())
		self.log("withdraw() cancelling", len(akeys), "active orders")
		for tnum in akeys:
			trade = self.actives[tnum]
			if "order_id" in trade:
				self.cancel(tnum)
			else:
				self.log("trade uninitialized! (cancelling cancel)", trade)

	def refill(self):
		self.log("refill()")
		while self.backlog and (len(self.actives.keys()) < ACTIVES_ALLOWED):
			self.submit(self.backlog.pop(0))

	def submit(self, trade):
		global orderNumber
		self.log("submit()", trade)
		orderNumber += 1
		self.actives[str(orderNumber)] = trade
		trade["client_order_id"] = str(orderNumber)
		LIVE and gem.trade(trade, self.submitted)
		emit("orderActive", trade)

	def submitted(self, resp):
		coid = resp["client_order_id"]
		msg = "submitted(%s)"%(coid,)
		if coid not in self.actives:
			return self.log(msg, "order already cancelled!", resp)
		self.log(msg, resp)
		self.actives[coid]["order_id"] = resp["order_id"]

	def enqueue(self, trade):
		self.backlog.append(trade)
		self.log("enqueue()", len(self.backlog), trade)
		self.refill()