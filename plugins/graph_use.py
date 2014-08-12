import sys
sys.path.insert(0, './plugins')
import web, json, time, io, re, urllib2, datetime
import gv # Get access to ospi's settings
from urls import urls # Get access to ospi's URLs

# Constants #
DAYS_OFWEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

englishmetrics=['in/hr', 'gal/hr', 'inches', 'gallons']
metricmetrics=['mm/hr', 'l/hr', 'mm', 'liters']

# global variables #
auto_job = 0        # cron job that executes daily
daysWatched = 7     # number of days to consider when calculating water usage and rainfall data
metrics=englishmetrics

# allows other modules to update settings
def updateSettings(m, d):
    global daysWatched
    global metrics
    # print "updateSettings:", d, m
    daysWatched = d
    metrics=m
    return

urls.extend(['/gu', 'plugins.graph_use.graph_use']) # Add a new url to open the data entry page
gv.plugin_menu.append(['Graph Water Use', '/gu']) # Add this plugin to the home page plugins menu
    

class graph_use:
    """Load an html page for entering extra wx settings"""
    def __init__(self):
        self.render = web.template.render('templates/', globals={'json':json,'sorted':sorted})
    
    def GET(self):
        zh = getZoneHistory(daysWatched)
        
        return self.render.auto_program(data)


def getZoneHistory(limit):
    zh = []
    for x in range(0, gv.sd['nbrd']*8): zh.append(0) # setup zone history list to have 0 in all locations
    try:
        logf = open('data/log.json') 
        for line in logf:
            event = json.loads(line) # parse log entry line

            #check date and break out if we're past our limit
            end_date=event["date"] # date program ended
            delta = datetime.datetime.today()-datetime.datetime.strptime(end_date, "%Y-%m-%d")
            if delta.days > limit: break
            z = int(event["station"]) # station # (zero-based)
            if z>gv.sd['nbrd']*8: continue      # skip log entry if zone # is bigger than the number of zones we have
            # otherwise, pull out the run duration and modify the zone list to include the seconds of run time
            m = re.search('(\d+):\d+', event["duration"])
            s = re.search('\d+:(\d+)', event["duration"])
            if m: zh[z]+=int(int(m.group(1))*60)
            if s: zh[z]+=int(int(s.group(1)))
        logf.close()
    except IOError:
        # return the list with all 0 - assume no usage
        pass
    return zh

