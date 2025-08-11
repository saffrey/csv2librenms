\#!/usr/bin/python3
import config
import requests
import pandas as pd
import re

# --- API Headers ---
# Set HTTP headers required for LibreNMS API access, including API key from config.py
request_headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-Auth-Token": config.librenms_apikey,
    "Connection": "keep-alive"
}

# Default geographic coordinates to assign to new locations if none provided in CSV
DEFAULT_LAT = -32.0000
DEFAULT_LNG = 115.0000

# -------- Location handling ----------
def get_or_create_location_id(name, lat=None, lng=None):
    # Retrieve LibreNMS Location ID by name if exists.
    # If not found, create a new location with optional lat/lng (or defaults).
    #
    # Args:
    #     name (str): Location name.
    #     lat (float or None): Latitude coordinate.
    #     lng (float or None): Longitude coordinate.
    #
    # Returns:
    #     int or None: Location ID in LibreNMS or None if failed.

    # 1. Attempt to get existing locations from LibreNMS API
    url_get = f"http://{config.librenms_ipaddress}/api/v0/resources/locations"
    resp = requests.get(url_get, headers=request_headers)

    if resp.status_code == 200:
        try:
            # Look for a matching location name
            for loc in resp.json().get("locations", []):
                if loc.get("location") == name:
                    print(f"[INFO] Location '{name}' exists (ID {loc.get('id')})")
                    return loc.get("id")  # Return existing location ID
        except Exception as e:
            print(f"[WARN] Can't parse locations: {e}")

    # 2. Location not found—create new location with given or default coordinates
    payload = {
        "location": name,
        "lat": str(lat if lat is not None else DEFAULT_LAT),
        "lng": str(lng if lng is not None else DEFAULT_LNG),
        "fixed_coordinates": 1  # Marks coordinates as fixed in LibreNMS
    }
    url_post = f"http://{config.librenms_ipaddress}/api/v0/locations"
    resp_create = requests.post(url_post, json=payload, headers=request_headers)

    if resp_create.status_code in (200, 201):
        try:
            # Try to parse the newly created location ID from response
            new_loc = resp_create.json()
            loc_id = new_loc.get("id") or new_loc.get("location_id")
            # If ID is missing, try to extract it via regex from message text
            if not loc_id and "message" in new_loc:
                match = re.search(r"id\s+#?(\d+)", new_loc["message"])
                if match:
                    loc_id = int(match.group(1))
            print(f"[INFO] Created location '{name}' (ID {loc_id})")
            return loc_id
        except Exception as e:
            print(f"[WARN] Can't parse new location: {e}")

    print(f"[ERROR] Could not create location '{name}'")
    return None

# -------- Device handling ----------
def device_exists(hostname):
    # Check if a device with given hostname already exists in LibreNMS.
    #
    # Args:
    #     hostname (str): Device hostname or IP.
    #
    # Returns:
    #     bool: True if device exists, False otherwise.

    url = f"http://{config.librenms_ipaddress}/api/v0/devices/{hostname}"
    r = requests.get(url, headers=request_headers)
    if r.status_code == 200:
        try:
            devices = r.json().get("devices", [])
            return len(devices) > 0
        except:
            pass
    return False

def device_add(add_request):
    # Add a new device to LibreNMS using the API.
    #
    # Args:
    #     add_request (dict): JSON payload with device details.
    #
    # Returns:
    #     int or None: New device ID if success, None if failed.

    url = f"http://{config.librenms_ipaddress}/api/v0/devices"
    r = requests.post(url, json=add_request, headers=request_headers)

    try:
        data = r.json()
    except Exception as e:
        print(f"[WARN] JSON decode error: {e}")
        data = r.text

    # Check for success and extract device_id from response
    if r.status_code == 200 and isinstance(data, dict):
        if "devices" in data and len(data["devices"]) > 0:
            return data["devices"][0].get("device_id")

    # Detailed failure logs for troubleshooting SNMP issues or connectivity
    print(f"[ERROR] Failed to add {add_request.get('hostname')} "
          f"(likely SNMP check failed — wrong community, version [ensure lower case], or unreachable device)")
    print(f"         API status: {r.status_code}, Response: {r.text}")
    return None

def device_update(device_id, update_request):
    # Update device information in LibreNMS using PATCH API call.
    #
    # Args:
    #     device_id (int): LibreNMS device ID to update.
    #     update_request (dict): JSON payload specifying fields and data to update.

    url = f"http://{config.librenms_ipaddress}/api/v0/devices/{device_id}"
    r = requests.patch(url, json=update_request, headers=request_headers)
    print(f"[INFO] Updated device {device_id}: {r.status_code}")

# -------- Main execution --------
try:
    # Load device list from CSV file
    df = pd.read_csv("data/bulkadd.csv")
except Exception as e:
    print(f"[FATAL] Cannot read data/bulkadd.csv: {e}")
    quit()

# Iterate over each device from CSV to process additions
for index, row in df.iterrows():
    hostname = str(row['hostname']).strip()

    # Extract fields from CSV safely with NaN checks
    community = row['community'] if 'community' in df.columns and not pd.isna(row['community']) else None
    syslocation = row['syslocation'] if 'syslocation' in df.columns and not pd.isna(row['syslocation']) else None
    lat = row['lat'] if 'lat' in df.columns and not pd.isna(row['lat']) else None
    lng = row['lng'] if 'lng' in df.columns and not pd.isna(row['lng']) else None
    snmp_force = str(row['snmp_force']).strip().lower() == 'true' if 'snmp_force' in df.columns and not pd.isna(row['snmp_force']) else False
    snmp_version = str(row['snmp_version']).strip() if 'snmp_version' in df.columns and not pd.isna(row['snmp_version']) else 'v2c'
    sysname = row['sysname'] if 'sysname' in df.columns and not pd.isna(row['sysname']) else ""

    # Skip devices already present in LibreNMS
    if device_exists(hostname):
        print(f"[INFO] Skipping {hostname}: already exists")
        continue

    # Build device add payload depending on SNMP or ping-only mode
    if not community:  # Ping-only device: disable SNMP, force add
        add_device = {
            "hostname": hostname,
            "sysName": sysname,
            "hardware": row['hardware'] if 'hardware' in df.columns and not pd.isna(row['hardware']) else "",
            "snmp_disable": "true",
            "force_add": "true"  # Ping-only always forced add
        }
    else:  # SNMP device: add with community and version, force if requested
        add_device = {
            "hostname": hostname,
            "community": community,
            "version": snmp_version
        }
        if snmp_force:
            add_device["force_add"] = "true"

    # Add device via LibreNMS API
    device_id = device_add(add_device)
    if not device_id:
        # Failed to add device; skip further processing
        continue

    # Explicitly update the Display Name (API field "display") after add if sysname set
    if sysname:
        update_sysname = {
            "field": ["display"],  # Field 'display' controls UI display name
            "data": [sysname]
        }
        device_update(device_id, update_sysname)

    # Assign location if specified: get/create location and update device accordingly
    if syslocation:
        loc_id = get_or_create_location_id(syslocation, lat, lng)
        if loc_id:
            details = {
                "field": ["location_id", "sysLocation", "override_sysLocation"],
                "data": [loc_id, syslocation, 1]
            }
            device_update(device_id, details)
