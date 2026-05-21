
import csv

with open('edb.csv', 'r') as f: d=dict(csv.reader(f))

def ign(disc):
    return d[str(disc)]
