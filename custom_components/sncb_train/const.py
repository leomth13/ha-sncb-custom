"""Constants for the SNCB Train Tracker integration."""

DOMAIN = "sncb_train"

# Polling interval (seconds) - 60s is fine for iRail
DEFAULT_SCAN_INTERVAL = 60

# API
API_BASE = "https://api.irail.be/v1"
API_VEHICLE = f"{API_BASE}/vehicle/"

# Config keys
CONF_VEHICLE_ID = "vehicle_id"
CONF_STATION_FROM = "station_from"
CONF_STATION_TO = "station_to"
CONF_NAME = "name"

# Defaults
DEFAULT_STATION_FROM = "Gembloux"
DEFAULT_STATION_TO = "Namur"
