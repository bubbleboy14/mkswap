from dydx3 import constants
from accountant import Accountant
from agent import Agent
from backend import start, spew

def get(path, ag=None):
	from dez.http import fetch
	ag = ag or Agent()
	hz = ag.credHead(path)
	host = constants.API_HOST_GOERLI.split("//")[1]
	print("fetching:", host, path)
	fetch(host, path, port=443, secure=True, headers=hz, cb=spew, dispatch=True)

def accountant(): # doesn't work - "Invalid id"
	acc = Accountant()
	ag = Agent()
	start()

def accountById(): # works!
	ag = Agent()
	get("/v3/accounts/" + ag.id() + "?ethereumAddress=" + ag.client.default_address, ag)

def accounts(): # works!
	get("/v3/accounts")

def reg(): # works!
	get("/v3/registration")

if __name__ == "__main__":
	accountant()
	#accountById()
	#accounts()
	#reg()