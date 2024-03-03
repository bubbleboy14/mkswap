from fyg import Config

config = Config({
	"accountant": {
		"nmult": 1.0,
		"nudge": "auto",
		"capped": "auto"
	},
	"backend": {
		"staging": True,
		"realdie": True,
		"credset": "default"
	},
	"base": {
		"unspammed": True
	},
	"comptroller": {
		"live": False,
		"actives": 20,
		"prunelimit": 0.1
	},
	"harvester": {
		"batch": 10,
		"bottom": 40,
		"skim": False,
		"balance": True,
		"network": "bitcoin"
	},
	"ndx": {
		"inner": 16,
		"short": 32,
		"long": 64,
		"outer": 128
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
		"slosh": {
			"vmult": 16,
			"vcutoff": 0.8,
			"randlim": 0.04,
			"oneswap": "auto"
		}
	}
})