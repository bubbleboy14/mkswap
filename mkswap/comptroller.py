from .backend import listen, gemget
from .base import Feeder

orderNumber = 0

class Comptroller(Feeder):
	def __init__(self):
		self.actives = {}
		self.backlog = []
		listen("priceChange", self.curate)
		listen("enqueueOrder", self.enqueue)
		self.feed("gemorders")

	def proc(self, msg):
		coi = msg.get("client_order_id", None)
		if not coi:
			return self.log("proc(%s): NO client_order_id!!!"%(msg,))
		order = self.actives[coi]
		etype = msg["type"]
		if etype == "closed":
			self.log("proc(): trade closed", order)
			del self.actives[coi]
		else:
			self.log("proc(): %s"%(etype,))

	def on_message(self, ws, msgs):
		self.log("message:", msgs)
		for msg in msgs:
			self.proc(msg)
		self.refill()

	def curate(self):
		# TODO
		# - backlog: rate, filter, and sort
		# - actives: rate and filter
		pass

	def refill(self):
		while self.backlog and len(self.actives.keys()) < 10:
			self.submit(self.backlog.pop(0))

	def submit(self, trade):
		orderNumber += 1
		self.actives[orderNumber] = trade
		trade["client_order_id"] = orderNumber
		gemget("/v1/order/new", self.log, trade)

	def enqueue(self, trade):
		self.backlog.append(trade)
		self.refill()