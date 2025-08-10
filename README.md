# csv2librenms

CSV bulk importer for LibreNMS, importing devices as SNMP‑monitored or PING‑only.  

Each row in `data/bulkadd.csv` will create a **new** device in LibreNMS.  
Existing devices/locations are skipped — this script is **add‑only**.

You must add your LibreNMS API key in the `config.py` file.  
Generate an API key via the LibreNMS web GUI:  
**[Profile Icon] → API Settings → Generate New API Key**

**Run:**
```
python3 bulkadd.py
```
---

## CSV File Format

Save as `data/bulkadd.csv`.

| Column        | Description                                                                                                           |
|---------------|-----------------------------------------------------------------------------------------------------------------------|
| `hostname`    | IP or hostname of the device to add                                                                                   |
| `os`          | (Optional) LibreNMS OS name — see [LibreNMS OS definitions](https://github.com/librenms/librenms/tree/master/includes/definitions) |
| `sysname`     | (Optional) Device sysName                                                                                             |
| `hardware`    | (Optional) Hardware description                                                                                       |
| `syslocation` | (Optional) Location name to assign to the device                                                                      |
| `lat`         | (Optional) Latitude for the location; defaults to `-32.0000` if missing                                               |
| `lng`         | (Optional) Longitude for the location; defaults to `115.0000` if missing                                              |
| `community`   | SNMP read‑only community string. Leave blank to add as PING‑only device with SNMP disabled                            |
| `snmp_force`  | `true`/`false` — For SNMP devices: when true, *force add* even if SNMP/ping checks fail. Ping‑only devices always force‑add. |
| `snmp_version`| SNMP version (`v1`, `v2c`, `v3`). Defaults to `v2c` if blank                                                           |

---

## How It Works

- If the device exists → skipped.
- If new:
  - **SNMP device** (community set): added with given `community` and `snmp_version`.
  - **PING‑only** (community blank): SNMP disabled, added with force‑add.
- If `snmp_force` is `true` for an SNMP device: `"force_add": "true"` is sent to bypass SNMP/ping tests.
- Location:
  - If `syslocation` exists → used.
  - If missing → created with given lat/lng or defaults.
- Failing adds print the likely cause and full API response.

---

### Example CSV

```csv
hostname,os,sysname,hardware,syslocation,lat,lng,community,snmp_force,snmp_version
192.168.2.40,,Core Router,Cisco-ISR4451,Data Center,-31.9600,115.8600,network,true,v2c
192.168.2.50,,Ping Only Device,Generic,Warehouse,,,
192.168.2.60,,Edge Switch,Juniper,Main Office,-32.0200,115.8500,public,false,v3
```

