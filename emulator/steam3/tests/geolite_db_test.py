import geoip2.database


def get_country_code(ip_address: str) -> str:
    # Open the GeoLite2 database file
    reader = geoip2.database.Reader('F:\development\steam\emulator_git\\files\geolitedb\GeoLite2-Country.mmdb')

    try:
        # Perform the lookup
        response = reader.country(ip_address)

        # Get the country code
        country_code = response.country.iso_code
    except:
        # If IP address is not found in the database
        country_code = "US"
    finally:
        # Close the database when done
        reader.close()

    return country_code

ip_address = '192.168.0.1'
print(f"IP Address: {ip_address}, Country Code: {get_country_code(ip_address)}")