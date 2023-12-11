import json
from .backend import listen, emit, gemget
from .base import Feeder

orderNumber = 0

class Comptroller(Feeder):
	def __init__(self, pricer):
		self.actives = {}
		self.backlog = []
		self.pricer = pricer
		listen("priceChange", self.curate)
		listen("enqueueOrder", self.enqueue)
		self.feed("gemorders")

	def proc(self, msg):
		coi = msg.get("client_order_id", None)
		if not coi:
			return self.log("proc(%s): NO client_order_id!!!"%(msg,))
		order = self.actives[coi]
		etype = msg["type"]
		if msg.get("is_cancelled", None):
			self.cancel(coi)
		elif etype == "closed":
			self.log("proc(): trade closed", order)
			emit("tradeComplete", order)
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
		trade["score"] = trade["price"] - curprice
		if trade["side"] == "buy":
			trade["score"] *= -1

	def curate(self):
		# backlog: rate, filter, and sort
		for trade in self.backlog:
			self.score(trade)
		self.backlog = list(filter(lambda t : t["score"] > 0, self.backlog))
		self.backlog.sort(key=lambda t : t["score"])
		# actives: rate and cancel (as necessary)
		cancels = []
		for tnum in self.actives:
			trade = self.actives[tnum]
			self.score(trade)
			if trade["score"] < 0:
				cancels.push(tnum)
		for cancels in cancel:
			self.cancel(tnum)

	def cancel(self, tnum):
		trade = self.actives[tnum]
		gemget("/v1/order/cancel", self.log, { "order_id": trade["order_id"] })
		self.log("cancel()", trade)
		emit("tradeCancelled", trade)
		del self.actives[tnum]

	def refill(self):
		while self.backlog and len(self.actives.keys()) < 10:
			self.submit(self.backlog.pop(0))

	def submit(self, trade):
		orderNumber += 1
		self.actives[orderNumber] = trade
		trade["client_order_id"] = orderNumber
		gemget("/v1/order/new", self.submitted, trade)

	def submitted(self, resp):
		self.actives[resp["client_order_id"]]["order_id"] = resp["order_id"]
		self.log("submitted()", resp)

	def enqueue(self, trade):
		self.backlog.append(trade)
		self.refill()