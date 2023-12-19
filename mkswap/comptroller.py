import json, random
from .backend import log, listen, emit, gemget, gemtrade
from .base import Feeder

LIVE = False
ACTIVES_ALLOWED = 10
orderNumber = random.randint(0, 500)

def setLive(islive):
	log("setLive(%s)"%(islive,))
	global LIVE
	LIVE = islive

def setActives(actall):
	log("setActives(%s)"%(actall,))
	global ACTIVES_ALLOWED
	ACTIVES_ALLOWED = actall

class Comptroller(Feeder):
	def __init__(self, pricer):
		self.actives = {}
		self.backlog = []
		self.pricer = pricer
		listen("priceChange", self.prune)
		listen("enqueueOrder", self.enqueue)
		self.feed("gemorders")

	def proc(self, msg):
		coi = msg.get("client_order_id", None)
		if not coi:
			return self.log("proc(%s): NO client_order_id!!!"%(msg,))
		if coi not in self.actives:
			return self.log("proc(%s): unlisted client_order_id!!!"%(msg,))
		order = self.actives[coi]
		etype = msg["type"]
		if msg.get("is_cancelled", None):
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
		cancels = []
		skips = 0
		for tnum in self.actives:
			trade = self.actives[tnum]
			if "order_id" in trade:
				self.score(trade)
				if trade["score"] < 0:
					cancels.append(tnum)
			else:
				skips += 1
		for tnum in cancels:
			self.cancel(tnum)
		self.log("prune():", blsremoved, "backlogged - now at",
			len(self.backlog), "; and", len(cancels), "actives - now at", len(self.actives.keys()),
			"; skipped", skips, "uninitialized orders")

	def cancel(self, tnum, tellgem=True):
		trade = self.actives[tnum]
		LIVE and tellgem and gemget("/v1/order/cancel", self.log, { "order_id": trade["order_id"] })
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
		LIVE and gemtrade(trade, self.submitted)
		emit("orderActive", trade)

	def submitted(self, resp):
		self.log("submitted()", resp)
		self.actives[resp["client_order_id"]]["order_id"] = resp["order_id"]

	def enqueue(self, trade):
		self.backlog.append(trade)
		self.log("enqueue()", len(self.backlog), trade)
		self.refill()