import utilities.time
from config import get_config


def swap_blobs():
    # Get fresh config each time to pick up any changes made while running
    config = get_config()
    subtract_time = config["subtract_time"]
    
    years = subtract_time
    months = 0
    days = 0

    if "y" in subtract_time:
        year_pos = subtract_time.find("y") + 1
        if subtract_time[year_pos].isdigit(): # to ensure it's "y" and not "year" in config
            month_pos = subtract_time.find("m") + 1
            day_pos = subtract_time.find("d") + 1

            dct = {"y": year_pos, "m": month_pos, "d": day_pos}
            dct = dict(sorted(dct.items(), key=lambda item: item[1]))

            pos_list = list(dct.keys())

            if "y" in dct:
                pos = list(dct).index('y') #index
                if pos == 2:
                    years = subtract_time[year_pos:]
                else:
                    next_pos = (dct[pos_list[list(dct).index('y') + 1]] - 1) - year_pos
                    years = subtract_time[year_pos:year_pos + next_pos]

            if "m" in dct:
                pos = list(dct).index('m') #index
                if pos == 2:
                    months = subtract_time[month_pos:]
                else:
                    next_pos = (dct[pos_list[list(dct).index('m') + 1]] - 1) - month_pos
                    months = subtract_time[month_pos:month_pos + next_pos]

            if "d" in dct:
                pos = list(dct).index('d') #index
                if pos == 2:
                    days = subtract_time[day_pos:]
                else:
                    next_pos = (dct[pos_list[list(dct).index('d') + 1]] - 1) - day_pos
                    days = subtract_time[day_pos:day_pos + next_pos]

    if years == "": years = 0
    if months == "": months = 0
    if days == "": days = 0

    try:
        newdate = utilities.time.sub_yrs(utilities.time.get_current_datetime_blob(), -abs(int(years)), -abs(int(months)), -abs(int(days)))
    except:
        print("WARN: invalid format, defaulting to current date")
        newdate = utilities.time.sub_yrs()

    newtime = f"{str(newdate[11:])}"
    newdate = f"{str(newdate[0:10])}"

    # print(newdate)
    # print(newtime)

    with open("emulator.ini", 'r') as f:
        lines = f.readlines()

    with open ("emulator.ini", 'w') as g:
        for line in lines:
            if line.startswith("steam_date="):
                g.write(f"steam_date={newdate}\n")
            elif line.startswith("steam_time="):
                g.write(f"steam_time={newtime}\n")
            else:
                g.write(line)

    # Update in-memory config to match what was written to file
    # This prevents stale config issues when other code checks the values
    config["steam_date"] = newdate
    config["steam_time"] = newtime
