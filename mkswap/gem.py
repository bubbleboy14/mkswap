import rel
from .backend import ask, spew, die, dpost
from .base import Worker

class Req(Worker):
	def __init__(self, path, params={}, cb=spew):
		self.path = path
		self.params = params
		self.cb = cb
		self.attempt = 0
		self.log(path, params)

	def get(self):
		self.attempt += 1
		self.log("get(%s, %s)"%(self.path, self.attempt))
		dpost(self.path, ask("credHead", self.path, self.params), self.receive, self.retry)

	def retry(self, reason, timeout=4):
		self.log("retry(#%s)[%s] %s seconds!"%(self.attempt, reason, timeout))
		rel.timeout(timeout, self.get)

	def receive(self, res):
		if "result" not in res or res["result"] != "error":
			return (self.cb or self.log)(res)
		reason = res["reason"]
		message = res["message"]
		self.log("receive(%s) %s error: %s"%(self.path, reason, message))
		if reason == "RateLimited":
			timeout = int(message.split(" ")[-2]) / 1000
		elif reason in ["RateLimit", "InvalidNonce"]:
			timeout = 5
		else:
			return die(reason, res)
		self.warn(reason)
		self.retry(reason, timeout)

class Gem(Worker):
	def __init__(self):
		self.pending = []
		rel.timeout(0.2, self.churn) # half of rate limit

	def churn(self):
		self.pending and self.pending.pop(0).get()
		return True

	def get(self, path, cb=None, params={}):
		self.log("get(%s)"%(path,), params)
		self.pending.append(Req(path, params, cb))

	def accounts(self, network, cb=None):
		self.get("/v1/addresses/%s"%(network,), cb)

	def balances(self, cb=None):
		self.get("/v1/balances", cb)

	def trade(self, trade, cb=None):
		self.get("/v1/order/new", cb, trade)

	def cancel(self, trade, cb=None):
		self.get("/v1/order/cancel", cb, { "order_id": trade["order_id"] })

	def withdraw(self, symbol, amount, address, memo, cb=None):
		self.get("/v1/withdraw/%s"%(symbol,), cb, {
			"memo": memo,
			"address": address,
			"amount": str(amount)
		})

gem = Gem()