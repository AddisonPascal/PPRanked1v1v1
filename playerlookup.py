
import csv

with open('edb.csv', 'r') as f: d=dict(csv.reader(f))

def ign(disc):
    return d[str(disc)]

#import pandas as pd
#df = pd.read_excel('edb.xlsx')
#
#db = df.to_dict()
#
#byDiscordID = dict(map(reversed, db['Discord ID'].items()))
#byName = dict(map(reversed, db['IGN'].items()))
#
#def getPlayerFromID(disc):
#    ind = byDiscordID[int(disc)]
#    return {"IGN": str(db['IGN'][ind]), "Rating": str(db['Rating'][ind]), "Last Played": str(db['Last Played (UTC)'][ind]), "Rated Games": str(db['Rated Games'][ind])}
#
#def getPlayerFromName(ign):
#    ind = byName[str(ign)]
#    return {"IGN": str(db['IGN'][ind]), "Rating": str(db['Rating'][ind]), "Last Played": str(db['Last Played (UTC)'][ind]), "Rated Games": str(db['Rated Games'][ind])}
#
#def getDiscID(ign):
#    ind = byName[str(ign)]
#    return db['Discord ID'][ind]
#
#while True:
#    disc = input("Discord ID: ")
#    try:
#        ind = byDiscordID[int(disc)]
#        print("IGN: " + db['IGN'][ind])
#        print("Rating: " + str(db['Rating'][ind]))
#        print("Last Played: " + str(db['Last Played (UTC)'][ind]))
#        print("Rated Games: "  + str(db['Rated Games'][ind]))
#    except:
#        print("Error")
#    print()