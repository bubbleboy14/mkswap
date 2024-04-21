from fyg import Config

config = Config({
	"actuary": {
		"small": 10,
		"medium": 60,
		"large": 360
	},
	"accountant": {
		"nmult": 1.0,
		"nudge": "auto",
		"capped": "auto"
	},
	"backend": {
		"mdv2": True,
		"staging": True,
		"realdie": True,
		"credset": "default"
	},
	"base": {
		"unspammed": True
	},
	"trader": {
		"force": False
	},
	"comptroller": {
		"live": False,
		"actives": 20,
		"prunelimit": 0.1,
		"canceleach": False
	},
	"harvester": {
		"batch": 10,
		"bottom": 40,
		"skim": False,
		"balance": True,
		"bookbalance": True,
		"network": "bitcoin"
	},
	"ndx": {
		"inner": 32,
		"short": 64,
		"long": 128,
		"outer": 256
	},
	"office": {
		"verbose": False,
		"stagish": False,
		"wsdebug": False
	},
	"strategy": {
		"base": {
			"loud": False
		},
		"rsi": {
			"size": 4,
			"period": 16
		},
		"slosh": {
			"vmult": 16,
			"vcutoff": 0.8,
			"randlim": 0.04,
			"oneswap": "auto"
		}
	}
})