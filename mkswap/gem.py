import rel
from .backend import ask, spew, die
from .base import Worker

class Gem(Worker):
	def _cb(self, path, cb, params, attempt):
		def f(res):
			if "result" not in res or res["result"] != "error":
				return (cb or self.log)(res)
			reason = res["reason"]
			message = res["message"]
			msg = "_cb(%s) %s error: %s"%(path, reason, message)
			if reason != "RateLimited":
				die(msg, res)
			timeout = int(msg.split(" ")[-2]) / 1000
			self.log(msg, "-> retrying (attempt #%s) in %s seconds!"%(attempt, timeout))
			rel.timeout(timeout, self.get, path, cb, params, attempt + 1)
		return f

	def get(self, path, cb=None, params={}, attempt=1):
		from dez.http import post
		self.log("get(%s, %s)"%(path, attempt), params)
		post(hosts["gemini"], path, port=443, secure=True, headers=ask("credHead", path, params),
			cb=self._cb(path, cb, params, attempt), timeout=10, json=True)

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