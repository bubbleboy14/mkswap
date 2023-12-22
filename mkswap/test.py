from .accountant import Accountant
from .observer import Observer
from .agent import agencies
from .comptroller import setActives
from .config import config
from .backend import start, spew, predefs, hosts, echofeed, setStaging

plat = predefs["platform"]
Agent = agencies[plat]
SILENT_REQUEST = True

#
# mkswap tests
#
def get(path, ag=None, dispatch=True):
	from dez.http import fetch, post
	getter = (plat == "dydx") and fetch or post
	host = hosts[plat]
	ag = ag or Agent()
	hz = ag.credHead(path)
	print("fetching:", host, path)
	getter(host, path, port=443, secure=True, headers=hz, cb=spew, dispatch=dispatch, silent=SILENT_REQUEST)

def accountant():
	acc = Accountant()
	ag = Agent()
	start()

#
# dydx tests
#
def daccountById(): # works!
	ag = Agent()
	get("/v3/accounts/" + ag.id() + "?ethereumAddress=" + ag.client.default_address, ag)

def daccounts(): # works!
	get("/v3/accounts")

def dreg(): # works!
	get("/v3/registration")

#
# gemini tests
#
def gemNotionalVolume():
	get("/v1/notionalvolume")

def gemAccount():
	get("/v1/account")

def gemBalances():
	get("/v1/balances")

def gemOrders():
	Agent()
	echofeed("gemorders")
	start()

def gemAddresses(network="bitcoin"):
	get("/v1/addresses/%s"%(network,))

def gemApprovedAddresses(network="bitcoin"):
	get("/v1/approvedAddresses/account/%s"%(network,))

#
# general
#
def multi():
	ag = Agent()
	get("/v1/notionalvolume", ag, False)
	get("/v1/account", ag, False)
	get("/v1/balances", ag)

def confy():
	spew(config.current())
	setStaging(False)
	setActives(100)
	spew(config.current())

def observe(sym="BTCUSD"):
	setStaging(False)
	Observer(sym)
	start()

if __name__ == "__main__":
	multi()
	#observe()
	#gemApprovedAddresses()
	#gemAddresses()
	#confy()
	#gemOrders()
	#gemBalances()
	#gemAccount()
	#gemNotionalVolume()
	#accountant()
	#daccountById()
	#daccounts()
	#dreg()