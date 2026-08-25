# SNCB Train Tracker

Custom component Home Assistant pour suivre un train SNCB via l'API iRail.

## Installation

Structure du dépôt Git :

```
repo/
├── custom_components/
│   └── sncb_train/
│       ├── __init__.py
│       ├── manifest.json
│       ├── const.py
│       ├── coordinator.py
│       ├── sensor.py
│       ├── config_flow.py
│       ├── strings.json
│       ├── translations/
│       └── README.md
├── hacs.json
└── README.md
```

HACS → Custom repositories → URL du repo → Integration → Download → Redémarrer HA.

## Configuration

Paramètres → Appareils & services → Ajouter → **SNCB Train Tracker**

- Numéro du train : `IC2108` ou `IC2508`
- Gare départ : `Gembloux`
- Gare arrivée : `Namur`

## Sensors

| Sensor | Description |
|--------|-------------|
| Statut | Pas encore parti / En route / … |
| Position actuelle | Dernière gare quittée |
| Retard position actuelle | Retard à cette gare (min) |
| Prochaine gare | Prochaine gare |
| Retard prochaine gare | Retard annoncé (min) |
| Retard arrivée Gembloux | arrivalDelay Gembloux |
| Retard arrivée Namur | arrivalDelay Namur |
| Quai Gembloux | Quai |

Polling toutes les 60 secondes. Données : [iRail](https://api.irail.be).
