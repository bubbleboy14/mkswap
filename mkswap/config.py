from fyg import Config

config = Config({
	"actuary": {
		"small": 10,
		"medium": 60,
		"large": 360
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
		"force": False,
		"booktrades": True
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
		"stagish": False
	},
	"strategy": {
		"base": {
			"loud": False
		},
		"rsi": {
			"size": 4,
			"period": 16
		},
		"cross": {
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