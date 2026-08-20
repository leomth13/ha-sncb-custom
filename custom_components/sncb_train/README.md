# SNCB Train Tracker

Custom component Home Assistant pour suivre un train SNCB/NMBS précis via l’API iRail.

## Fonctionnalités

Pour chaque train configuré (ex. IC2108 ou IC2508) :

- **Retard** à la gare surveillée (Gembloux par défaut) en minutes
- **Statut** : Pas encore parti / En route / À quai / Déjà passé / Annulé / Non circulant aujourd’hui
- **Position actuelle** : dernière gare quittée
- **Quai** prévu/annoncé à Gembloux
- Attributs supplémentaires : occupation, heure théorique, etc.

Le component interroge l’endpoint vehicle de iRail toutes les 90 secondes.

## Installation

1. Copier le dossier `sncb_train` dans `/config/custom_components/`
2. Redémarrer Home Assistant
3. Aller dans **Paramètres → Appareils & services → Ajouter une intégration**
4. Chercher **SNCB Train Tracker**
5. Entrer le numéro du train (ex. `IC2108`)
6. Laisser `Gembloux` comme gare (ou changer si besoin)
7. Répéter pour le second train (`IC2508`)

## Exemple d’automatisation

```yaml
automation:
  - alias: "Alerte retard IC2108"
    trigger:
      - platform: numeric_state
        entity_id: sensor.ic2108_retard
        above: 5
    condition:
      - condition: state
        entity_id: sensor.ic2108_statut
        state: "En route"
    action:
      - service: notify.mobile_app_ton_telephone
        data:
          title: "Train IC2108 en retard"
          message: >
            Retard de {{ states('sensor.ic2108_retard') }} min.
            Position: {{ states('sensor.ic2108_position_actuelle') }}
            Quai prévu: {{ states('sensor.ic2108_quai') }}
```

## Notes importantes

- Le train n’existe dans l’API que le jour où il circule.
- Avant le départ théorique du train, le statut sera « Non circulant aujourd’hui » ou « Pas encore parti ».
- Les numéros de train (IC2108, IC2508…) sont généralement stables pendant toute la période horaire SNCB (changent 1 à 2 fois par an).

## Crédits

Données fournies par l’API ouverte [iRail](https://api.irail.be).
