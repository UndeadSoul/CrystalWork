def calc_windtype_profiles(windtype, width, height):
    #conversion de cm a m
    widthm = round(int(width)/100,3)
    heightm = round(int(height)/100,3)
    profiles = []
    if windtype == "Linea20":
        #obtener medida de los perfiles
        rielSup = round(widthm-0.012,3)
        rielInf = round(widthm-0.012,3)
        zocalo = round(widthm/2,3)
        cabezal = round(widthm/2,3)
        batiente = round(heightm-0.035,3)
        traslapo = round(heightm-0.035,3)
        jamba = round(heightm,3)
        profiles = [
            {"name":"Riel superior","length": rielSup,  "cant": 1},
            {"name":"Riel Inferior","length": rielInf,  "cant": 1},
            {"name":"Zocalo",       "length": zocalo,   "cant": 2},
            {"name":"Cabezal",      "length": cabezal,  "cant": 2},
            {"name":"Batiente",     "length": batiente, "cant": 2},
            {"name":"Traslapo",     "length": traslapo, "cant": 2},
            {"name":"Jamba",        "length": jamba,    "cant": 2}]
    if windtype == "Linea25lluvia":
    #obtener medida de los perfiles
        rielSup = round(widthm-0.016,3)
        rielInf = round(widthm-0.016,3)
        zocalo = round(widthm/2,3)
        cabezal = round(widthm/2,3)
        batiente = round(heightm-0.045,3)
        traslapo = round(heightm-0.045,3)
        jamba = round(heightm,3)
        profiles = [
            {"name":"Riel superior","length": rielSup,  "cant": 1},
            {"name":"Riel Inferior","length": rielInf,  "cant": 1},
            {"name":"Zocalo",       "length": zocalo,   "cant": 2},
            {"name":"Cabezal",      "length": cabezal,  "cant": 2},
            {"name":"Batiente",     "length": batiente, "cant": 2},
            {"name":"Traslapo",     "length": traslapo, "cant": 2},
            {"name":"Jamba",        "length": jamba,    "cant": 2}]
    if windtype == "Linea25simple":
    #obtener medida de los perfiles
        rielSup = round(widthm-0.016,3)
        rielInf = round(widthm-0.016,3)
        zocalo = round(widthm/2,3)
        cabezal = round(widthm/2,3)
        batiente = round(heightm-0.035,3)
        traslapo = round(heightm-0.035,3)
        jamba = round(heightm,3)
        profiles = [
            {"name":"Riel superior","length": rielSup,  "cant": 1},
            {"name":"Riel Inferior","length": rielInf,  "cant": 1},
            {"name":"Zocalo",       "length": zocalo,   "cant": 2},
            {"name":"Cabezal",      "length": cabezal,  "cant": 2},
            {"name":"Batiente",     "length": batiente, "cant": 2},
            {"name":"Traslapo",     "length": traslapo, "cant": 2},
            {"name":"Jamba",        "length": jamba,    "cant": 2}]
        pass
    if windtype == "Linea42f":
        pass
    if windtype == "Linea42p":
        pass
    return(profiles)