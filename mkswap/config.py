from fyg import Config

config = Config({
	"actuary": {
		"sig": 9,
		"fast": 12,
		"slow": 26,
		"range": 14,
		"small": 10,
		"medium": 60,
		"large": 360,
		"int": "5m" # 1m/5m/15m/30m/1h/6h/1d
	},
	"accountant": {
		"split": 16,
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
	"feeder": {
		"heartbeat": 10,
		"wsdebug": "auto"
	},
	"base": {
		"unspammed": True
	},
	"trader": {
		"size": 8,
		"book": True,
		"force": False
	},
	"comptroller": {
		"live": False,
		"actives": 20,
		"plimit": 0.1,
		"leeway": 0.001,
		"canceleach": True
	},
	"harvester": {
		"batch": 10,
		"bottom": 40,
		"skim": False,
		"balance": True,
		"network": "bitcoin"
	},
	"ndx": {
		"inner": 32,
		"short": 64,
		"long": 128,
		"outer": 256,
		"hist": 1024
	},
	"office": {
		"verbose": False,
		"stagish": False,
		"strategy": "preset"
	},
	"strategy": {
		"base": {
			"loud": False
		},
		"rsi": {
			"size": 4,
			"period": 16
		},
		"hint": {
			"mult": 0.8,
			"score": 1.5
		},
		"slosh": {
			"vmult": 16,
			"vcutoff": 0.8,
			"randlim": 0.04,
			"oneswap": "auto"
		},
		"handcart": {
			"risk": 0.5,
			"profit": 0.01,
			"threshold": 0.05
		}
	}
})