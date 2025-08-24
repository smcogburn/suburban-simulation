north american suburbs -> car dependant -> bad
but what is best method to fix? lets find out with a simulation

estimating the  impact of 2 policy levers that ACTUALLY could be implemented
1. cutting bus headways (out here they take forever and are useless)
(e.g., 30→10 min) 

2. adding a protected bike lane thing (nobody bikes because you have to be on the road or on the crappy sidewalk) 

analyze this in a 2x2 factorial (control, one, the other, both)
how do these impact mode share - car trips vs. everything else (bike, transit, walk)

in a fixed study area (ex. columbia–ellicott city corridor suburban MD baltimore/dc metro). 

the pipeline: 
- build a multimodal network inside the polygon (using OSM)
- integrate with GTFS for transit network
- generate synthetic potential trip list (departure time, origin - destination pairs)
- compute the trips using r5py for fast, realistic, multimodal time matricies
- test each scenario
- analyze


one OSM extract + a GTFS zip file -> pass to r5py -> it builds transport network
from there, can compute door to door travel time
tho instead of using TravelTimeMatrix, use DetailedItineraries 
this returns transport mode, wait times, path geometry, and more
use this for our data
+ can turn it into some visualization?

use OSMmx (or something else?) to pull BUILDINGS and POIs for origin/desitnation pairs and trip sampling
for scenarios - for 1 modify the GTFS file being passed in, change headways,for 2, all bikeable roads in network (or.. all roads?) add a 20% bonus in choice algorithm to using them to represent you feeling better about uisng it
