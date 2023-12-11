from .backend import listen, gemget
from .base import Feeder

class Comptroller(Feeder):
	def __init__(self):
		self.actives = []
		self.backlog = []
		listen("priceChange", self.curate)
		listen("enqueueOrder", self.enqueue)
		self.feed("gemorders")

	def on_message(self, ws, msg):
		# TODO
		# - update actives[] ; refill()
		self.log("message:")
		pprint(msg)

	def curate(self):
		# TODO
		# - backlog: rate, filter, and sort
		# - actives: rate and filter
		pass

	def refill(self):
		while self.backlog and len(self.actives) < 10:
			self.submit(self.backlog.pop(0))

	def submit(self, trade):
		self.actives.append(trade)
		gemget("/v1/order/new", self.log, trade)

	def enqueue(self, trade):
		self.backlog.append(trade)
		self.refill()