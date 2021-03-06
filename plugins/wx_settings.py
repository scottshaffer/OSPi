import sys
sys.path.insert(0, './plugins')
import web, json, time, io, re, urllib2, datetime
import gv # Get access to ospi's settings
from urls import urls # Get access to ospi's URLs
import auto_program 

try:
    from apscheduler.scheduler import Scheduler #This is a non-standard module. Needs to be installed in order for this feature to work.
except ImportError:
    pass

urls.extend(['/wx', 'plugins.wx_settings.wx_settings', '/uwx', 'plugins.wx_settings.update_wx_settings']) # Add a new url to open the data entry page
try:
    sched = Scheduler()
    sched.start() # Start the scheduler
except NameError:
    pass    

#if it has rained today, then set rain to true
def checkRain():
    rtoday=0
    with io.open(r'./data/wx_settings.json', 'r') as data_file: 
        data = json.load(data_file)
    data_file.close()  
    rtoday=getWUTodayRain(data['wx']['apikey'],data['wx']['pws'])
    # print "rain today=", rtoday
    if rtoday and not gv.sd['urs']:
        gv.sd['rs'] = 1
    else:
        gv.sd['rs'] = 0  

    return    
    
@sched.cron_schedule(hour=1)
def getDailyRainfall(force = False):
    #do we have yesterdays rainfall data already?
    t = datetime.date.today()
    print t, "Getting rainfall history..."
    try:
        # read data from the file, if it exists
        with io.open(r'./data/wx_settings.json', 'r') as data_file: 
            data = json.load(data_file)
        data_file.close()  
#        print data
    except IOError:
    # if the data file doesn't exist, then create it with the blank data
        data = json.loads(u'{"wx": {"apikey": "1234", "useWU": 0, "pws":"<WUID>"}, "rainfall": {"2000-01-01": 0.0}, "startTimeHour": 0, "startTimeMin": 0, "enabled": 0}')
        for i in range(1,8):
            d = datetime.date.today() - datetime.timedelta(days=i)
            if data['wx']['useWU']:
                data['rainfall'][str(d)] = getWUHistoryRain(d, data['wx']['apikey'],data['wx']['pws'])
            else: data['rainfall'][str(d)]=0.0
        with io.open('./data/wx_settings.json', 'w', encoding='utf-8') as data_file:
            data_file.write(unicode(json.dumps(data, ensure_ascii=False)))

    t = datetime.date.today()
    y = t-datetime.timedelta(days=1)

    if force or (str(y) not in data['rainfall']): 
        # if not, recreate past n days rainfall data
        for i in range(1,auto_program.daysWatched+1):
            d = datetime.date.today() - datetime.timedelta(days=i)
            dstr = d.strftime("%Y%m%d")
            if data['wx']['useWU']:
                data['rainfall'][str(d)] = getWUHistoryRain(dstr, data['wx']['apikey'],data['wx']['pws'])
            else: data['rainfall'][str(d)]=0.0
#            print "getDailyRainfall: ", str(d), "=", data['rainfall'][str(d)]
    # delete entries older than daysWatched from memory
    oldest = t-datetime.timedelta(days=auto_program.daysWatched)
    # print "getDailyRainfall: oldest=", oldest
    for k, val in data['rainfall'].items():
        if datetime.datetime.strptime(k,"%Y-%m-%d").date() < oldest:
            del data['rainfall'][k]
    with io.open('./data/wx_settings.json', 'w', encoding='utf-8') as data_file:
        data_file.write(unicode(json.dumps(data, ensure_ascii=False)))
    
    return

class wx_settings:
    """Load an html page for entering extra wx settings"""
    def __init__(self):
        self.render = web.template.render('templates/', globals={'json':json,'sorted':sorted})
    
    def GET(self):
        # start by setting up our json dictionary with blank weather data
        try:
            # read wx settings from the file, if it exists
            with io.open(r'./data/wx_settings.json', 'r') as data_file: 
                data = json.load(data_file)
            data_file.close()  
        except IOError:
        # if the file doesn't exist, then create it with the blank data - this should never happen!
            data = json.loads(u'{"wx": {"apikey": "1234", "useWU": 0, "pws":"KTXSPRIN55"}, "rainfall": {"2000-01-01": 0.0}, "startTimeHour": 0, "startTimeMin": 0, "enabled": 0}')
            with io.open('./data/wx_settings.json', 'w', encoding='utf-8') as data_file:
                    data_file.write(unicode(json.dumps(data, ensure_ascii=False)))
        m=0
        if auto_program.metrics==auto_program.englishmetrics: m="english"
        elif auto_program.metrics==auto_program.metricmetrics: m="metric"
#        print "wx_settings:", auto_program.daysWatched, m
#        print "wx_settings: auto_program.metrics=", auto_program.metrics
        return self.render.wx_settings(data, auto_program.daysWatched, m)

class update_wx_settings:
    """Save user input to wx_settings.json file """
    def GET(self):
        qdict=web.input()
        #print "update_wx_settings:", int(qdict['daysWatched']), qdict['metric']
        try:
            # read wx settings from the file, if it exists, that way we keep field settings even if WU use is disabled
            with io.open(r'./data/wx_settings.json', 'r') as data_file: 
                data = json.load(data_file)
            data_file.close()    
            if 'useWU' in qdict: 
                data['wx']['useWU'] = 1
                data['wx']['apikey']=str(qdict['apikey'])
                data['wx']['pws']=str(qdict['pws'])
            else: data['wx']['useWU'] = 0
            with io.open('./data/wx_settings.json', 'w', encoding='utf-8') as data_file:
                data_file.write(unicode(json.dumps(data, ensure_ascii=False)))
            if qdict['metric']=='english': auto_program.updateSettings(auto_program.englishmetrics, int(qdict['daysWatched']))
            elif qdict['metric']=='metric': auto_program.updateSettings(auto_program.metricmetrics, int(qdict['daysWatched']))
        except IOError:
            return
        
        getDailyRainfall(True)  # pull rainfall data again
        
        raise web.seeother('/auto')

## Version that uses try/except to print an error message if the
## urlopen() fails.
def wget(url):
    #proxy = urllib2.ProxyHandler({'http': 'proxy.houston.hp.com:8080'})
    #opener = urllib2.build_opener(proxy)
    #urllib2.install_opener(opener)
    try:
        ufile = urllib2.urlopen(url)
    except IOError:
        # print 'problem reading url:', url
        return 0
    return ufile

# ------------------------------------------------------------------
# getWUHistoryRain
#  - returns a floating point value that represents the total rainfall from specified date
#
def getWUHistoryRain(d, apikey, pws):
    # if we are using wunderground.com as a data source, then pull from their api using the configured key
    url = r'http://api.wunderground.com/api/'+str(apikey)+r'/history_'+ str(d) + r'/q/pws:' + pws + r'.json'
    # print "getWUHistoryRain url=", url
    json_data = wget(url)
    if (json_data): data = json.load(json_data)
    else: return 0.0
    # print "getWUHistoryRain precipi=", data['history']['dailysummary'][0]['precipi']
    if data['history']['dailysummary'][0]['precipi']: return float(data['history']['dailysummary'][0]['precipi'])
    else: return 0.0

# ------------------------------------------------------------------
# getYesterdayRain
#  - returns a floating point value that represents the total rainfall from yesterday
#
def getWUTodayRain(apikey, pws):

    # if we are using wunderground.com as a data source, then pull from their api using the configured key
    url = r'http://api.wunderground.com/api/' + apikey + r'/conditions/q/pws:' + pws + r'.json'
    json_data = wget(url)
    if (json_data): data = json.load(json_data)
    else: return 0.0
    print "precip_today_in", data['current_observation']['precip_today_in']
#	day = parseDay(data['history']['observations'][23]['date']['pretty'])
#	print day, ':', rainfall, 'in'
	
    return float(data['current_observation']['precip_today_in'])

# ------------------------------------------------------------------
# getYesterdayRain
#  - returns a floating point value that represents the total rainfall from yesterday
#
def getWUYesterdayRain(apikey, pws):

    # if we are using wunderground.com as a data source, then pull from their api using the configured key
    url = r'http://api.wunderground.com/api/' + apikey + r'/yesterday/q/pws:' + pws + r'.json'
    json_data = wget(url)
    if (json_data): data = json.load(json_data)
    else: return 0.0
#   print 'hour:', hr, 'date:', data['history']['observations'][hr]['date']['pretty'], 'data:', data['history']['observations'][hr]['precip_totali']
#	day = parseDay(data['history']['observations'][23]['date']['pretty'])
#	print day, ':', rainfall, 'in'
	
    return float(data['history']['observations'][23]['precip_totali'])

# call once on load
getDailyRainfall()
