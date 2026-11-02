import json,random
r=random.Random(3);els=[]
def way(geom,tags): els.append({'type':'way','id':len(els)+1,'tags':tags,'geometry':[{'lat':a,'lon':b} for a,b in geom]})
lat0,lon0=44.0627,12.5683
def rect(la,lo,h,w,tags):
    way([(la,lo),(la,lo+w),(la+h,lo+w),(la+h,lo),(la,lo)],tags)
# costa: da SE a NW, terra a sinistra (SW), mare a NE
way([(44.0400,12.6000),(44.0560,12.5700),(44.0700,12.5500),(44.0790,12.5350)],{'natural':'coastline'})
# fiume
way([(44.0690,12.5460),(44.0600,12.5380),(44.0500,12.5300),(44.0400,12.5250)],{'waterway':'river'})
# strade a griglia
for k in range(-6,7):
    way([(lat0+k*0.0022,12.52),(lat0+k*0.0022,12.62)],{'highway':'residential'})
    way([(44.02,lon0+k*0.0030),(44.10,lon0+k*0.0030)],{'highway':'residential'})
# ponte
way([(44.0630,12.5320),(44.0630,12.5420)],{'highway':'primary','bridge':'yes'})
# edifici
for _ in range(900):
    la=lat0+r.uniform(-.0160,.0160);lo=lon0+r.uniform(-.0220,.0220)
    rect(la,lo,r.uniform(.00006,.00018),r.uniform(.00008,.0002),{'building':r.choice(['yes','house','apartments','hotel']),'building:levels':str(r.choice([2,3,4,6]))})
# parco
way([(44.0500,12.5500),(44.0500,12.5600),(44.0560,12.5600),(44.0560,12.5500),(44.0500,12.5500)],{'leisure':'park'})
# aeroporto
way([(44.0475,12.5750),(44.0475,12.5890),(44.0545,12.5890),(44.0545,12.5750),(44.0475,12.5750)],{'aeroway':'aerodrome'})
way([(44.0510,12.5755),(44.0510,12.5885)],{'aeroway':'runway'})
json.dump({'elements':els},open('fixture.json','w'))
print(len(els))
