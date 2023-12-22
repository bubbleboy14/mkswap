import rel, random
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

	def retry(self, reason, timeout=None):
		timeout = timeout or random.randint(5, 25)
		self.log("retry(%s #%s)[%s] %s seconds!"%(self.path, self.attempt, reason, timeout))
		rel.timeout(timeout, self.get)

	def receive(self, res):
		if "result" not in res or res["result"] != "error":
			return (self.cb or self.log)(res)
		reason = res["reason"]
		message = res["message"]
		self.log("receive(%s) %s error: %s"%(self.path, reason, message))
		if reason not in ["RateLimit", "RateLimited", "InvalidNonce"]:
			return die(reason, res)
		self.warn(reason)
		self.retry(reason, reason == "RateLimited" and int(message.split(" ")[-2]) / 1000)

class Gem(Worker):
	def __init__(self):
		self.pending = []
		rel.timeout(0.4, self.churn) # quarter of rate limit

	def churn(self):
		self.pending and self.pending.pop(0).get()
		return True

	def get(self, path, cb=None, params={}):
		self.pending.append(Req(path, params, cb))
		self.log("get(%s) %s pending"%(path, len(self.pending)), params)

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