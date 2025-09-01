

one OSM extract + a GTFS zip file -> pass to r5py -> it builds transport network
from there, can compute door to door travel time
tho instead of using TravelTimeMatrix, use DetailedItineraries 
both are pandas dataframe
but this returns transport mode, wait times, path geometry, and more
use this for our data analysis
can also turn it into a visualization (all code for this is on the documentation)

use OSMmx (or something else?) to pull BUILDINGS and POIs for origin/desitnation pairs and trip sampling
for scenarios - for 1 modify the GTFS file being passed in, change headways,for 2, all bikeable roads in network (or.. all roads?) change tag to protect or higher OR change stress level to lower

---

r5py uses conveyal analysis  :

When cycling is enabled in Conveyal Analysis, varying the Max Level of Traffic Stress limit can provide insights into gaps in a region’s cycling infrastructure. Setting Max LTS to 1 in an analysis will allow cycling only on separated bicycle infrastructure or low-traffic streets; routing will revert to walking when traversing any links with LTS exceeding 1. Setting Max LTS to 3 in an analysis will allow cycling on links with LTS 1, 2, or 3. Differences in access between these two analyses may highlight places where new dedicated cycling infrastructure could improve access for cyclists with lower tolerances for stressful conditions.

If way does not allow cars, assign LTS 1
If way has highway=service tag, do not assign LTS in this round
If way has a highway=residential or highway=living_street tag, assign LTS 1
If tagged maxspeed value is less than 25 mph (40.25 kph) and the number of lanes is less than 4 or unspecified, assign LTS 2
If way has tag highway=unclassified, highway=tertiary, or highway=tertiary-link and the number of lanes is less than 4 or there is cycleway tag for the correct direction, assign LTS 2
Otherwise, if there is a cycleway tag for the correct direction, assign LTS 3
Otherwise, assign LTS 4
