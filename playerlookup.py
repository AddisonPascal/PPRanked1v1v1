import csv

# edb.csv is a csv with discord ids and IGNs

with open('edb.csv', 'r') as f: d=dict(csv.reader(f))

def ign(disc):
    return d[str(disc)]
