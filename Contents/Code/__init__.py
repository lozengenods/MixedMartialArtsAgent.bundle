# Plex MMA Metadata Agent using Tapology & Wikipedia 
#
# Github: https://github.com/lozengenods/MixedMartialArtsAgent.bundle
#

import re, datetime
from random import randint

TAPOLOGY_SEARCH_URL = "https://www.tapology.com/search?mainSearchFilter=events&term=%s"
TAPOLOGY_EVENT_URL = "https://www.tapology.com/fightcenter/events/%s"
BASESCORE = 100

rdict = {
    '&': '?',
    ' ': '+',
    'æ': '%E6',
    'ø': '%F8',
    'å': '%E5',
    '(^en |^et |^de |^den |^der |^det )': ''
}

RE_REPLACE = Regex('|'.join(rdict.keys()), Regex.IGNORECASE)

#function to take in a dictionary, randomizes fighters, and returns a string
def FormatFight(fightDict):
    if randint(0,1) == 0:
        fightStr = fightDict['fighter1'] + ' vs. ' + fightDict['fighter2'] + ' (' + fightDict['weight'] + ' lbs)' 
    else:
        fightStr = fightDict['fighter2'] + ' vs. ' + fightDict['fighter1'] + ' (' + fightDict['weight'] + ' lbs)'
    return fightStr     

#Get number of early-prelim bouts from wikipedia event page
def GetBoutCount(searchResults, eventPromotion):
    wikiDict = [0, 0, 0, 0]
    eventWikiURL = ''

    if eventPromotion == "Ultimate Fighting Championship": #only needed for UFC events
        wikiSearch1 = searchResults.xpath("//div[@class='externalIconsHolder']//a/@href")
        wikiSearch2 = searchResults.xpath("//div[@class='externalIconsHolder']//a/@onclick")
        i = 0
        for url in wikiSearch1:
            if 'Event_Wikipedia' in wikiSearch2[i]:
                eventWikiURL = url
            i += 1
        
        if eventWikiURL != '':
            eventWikiPage = HTML.ElementFromURL(eventWikiURL)
            eventWikiDetails = eventWikiPage.xpath("//table[@class='toccolours']//text()")
            currentSegment = 0    
            for item in eventWikiDetails:
                if 'main card' in item.lower() or 'preliminary' in item.lower():
                    currentSegment += 1
                else:
                    if 'weight' in item.lower() and not 'weight class' in item.lower():
                        wikiDict[currentSegment] = wikiDict[currentSegment] + 1       

    return wikiDict
    
    

def Start():
  HTTP.CacheTime             = CACHE_1DAY
  HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 6_0 like Mac OS X) AppleWebKit/536.26 (KHTML, like Gecko) Version/6.0 Mobile/10A5376e Safari/8536.25'

class MixedMartialArtsAgent(Agent.Movies):
    name = 'Mixed Martial Arts'
    primary_provider = True
    fallback_agent = False
    contributes_to = None
    languages = [Locale.Language.English]
    accepts_from = ['com.plexapp.agents.localmedia']
   
    def search(self, results, media, lang, manual=False):
        Log("".ljust(157, '-'))
        Log("search() - Title: '%s'" % (media.title))
        Log(media.name)
        
        #reformat search name, strip out prelims, postlims, etc., remove periods, and stop the search string after the first instance of an integer.
        searchNameStart = media.name.lower().replace('prelims','').replace('early','').replace('postlims','').replace('.','') #remove prelim/postlim stuff and periods
        searchName = ''
        for item in searchNameStart.split():
            searchName = (searchName + ' ' + item).strip()
            if item.isdigit():
                break;

        Log("search phrase: " + searchName)
        url = TAPOLOGY_SEARCH_URL % ('%s' % RE_REPLACE.sub(lambda m: rdict[m.group(0)], searchName)) #replace characters with html chars
        searchResults = HTML.ElementFromURL(url)
        events = searchResults.xpath("//div[@class='searchResultsEvent']//a/text()") #get list of events from search results
        eventurls = searchResults.xpath("//div[@class='searchResultsEvent']//a/@href")#get list of event urls
        eventNames = searchResults.xpath("//div[@class='searchResultsEvent']//tr/td[3]") #get event name
        eventDates = searchResults.xpath("//div[@class='searchResultsEvent']//tr/td[5]") #get event dates      
        
        #get event segment: earlyprelims, prelims, maincard, postlims
        #this is used to get the appropriate fights for the video
        if 'early' in media.name.lower() and 'prelim' in media.name.lower():
            eventSegment = 'earlyprelims'
        elif 'prelim' in media.name.lower():
            eventSegment = 'prelims'
        elif 'postlim' in media.name.lower():
            eventSegment = 'postlims'
        else:
            eventSegment = 'maincard'
            
        #build a dictionary with search results
        eventDict = {}
        i = 0
        for event in events:
            eventDict[event] = {}
            eventDict[event]['id'] = eventurls.pop(0).split('/')[-1] + ' ' + eventSegment
            eventDict[event]['score'] = BASESCORE - abs(String.LevenshteinDistance(searchName, event)) #calculate search score

            if eventSegment == 'earlyprelims':
                eventDict[event]['name'] = str(eventNames[i].text) + ' (Early Prelims)'
            if eventSegment == 'prelims':
                eventDict[event]['name'] = str(eventNames[i].text) + ' (Prelims)'
            if eventSegment == 'postlims':
                eventDict[event]['name'] = str(eventNames[i].text) + ' (Postlims)'
            if eventSegment == 'maincard':
                eventDict[event]['name'] = str(eventNames[i].text)                

            eventDict[event]['date'] = eventDates[i].text
            results.Append(MetadataSearchResult(
                id=eventDict[event]['id'],
                name=event + ': ' + eventDict[event]['name'],
                year=eventDict[event]['date'][0:4],
                lang=lang,
                score=eventDict[event]['score']
            ))     
            i += 1     
                   
        Log('Search results: %s' % eventDict)
        results.Sort('score', descending=True)
        Log("".ljust(157, '-'))

    def update(self, metadata, media, lang):
        Log("".ljust(157, '='))
        Log("update() - metadata.id: '%s', metadata.title: '%s'" % (metadata.id.split()[0], metadata.title))
        url = TAPOLOGY_EVENT_URL % ('%s' % RE_REPLACE.sub(lambda m: rdict[m.group(0)], metadata.id.split()[0])) #replace characters with html chars
        searchResults = HTML.ElementFromURL(url)

        #get event segment: earlyprelims, prelims, maincard, postlims
        #this is used to get the appropriate fights for the video
        eventSegment = metadata.id.split()[1]           
       
        #get event title       
        eventTitle = searchResults.xpath("//div[@class='eventPageHeaderTitles']/h1/text()")
        if eventSegment == 'earlyprelims':
            title = eventTitle[0] + ' (Early Prelims)'
        elif eventSegment == 'prelims':
            title = eventTitle[0] + ' (Prelims)'
        elif eventSegment == 'postlims':
            title = eventTitle[0] + ' (Postlims)'
        else:
            title = eventTitle[0] 

        #get event details from right column
        eventDetails = searchResults.xpath("//div[@class='details details_with_poster clearfix']/div[@class='right']//text()")     

        #find the promotion name
        if 'Promotion:' in eventDetails:
            eventPromotion = eventDetails[eventDetails.index('Promotion:')+3]
        
        #get bout counts from Wikipedia so we can figure out which prelims are early and which are not
        #Indexes: 0 = should always be zero but here just in case we don't see a header
        #         1 = Main card
        #         2 = Prelims
        #         3 = Early prelims
        boutCount = GetBoutCount(searchResults, eventPromotion)

        #find the date        
        eventDate = (eventDetails[2].split())[1] 
        eventDate = datetime.datetime.strptime(eventDate, "%m.%d.%Y").strftime("%Y-%m-%d") #converts the date to yyyy-mm-dd format
        
        #find the location
        eventLocation = []
        if 'Location:' in eventDetails: 
            eventLocation.append(eventDetails[eventDetails.index('Location:')+2])
        if 'Venue:' in eventDetails:
            eventLocation.append(eventDetails[eventDetails.index('Venue:')+2])
        studio = ' @ '.join(eventLocation)
        
       
        #build a dictionary with fight details
        boutNumbers = searchResults.xpath("//div[@class='fightCardBoutNumber']/text()[normalize-space()]")         #create a list of bout numbers
        boutNumbers = [int(i) for i in boutNumbers]
        fighterLeft =  searchResults.xpath("//div[@class='fightCardFighterName left']//text()[normalize-space()]")  #create a list of fighters from the left
        fighterRight = searchResults.xpath("//div[@class='fightCardFighterName right']//text()[normalize-space()]") #create a list of fighters from the right
        fighterImages =  searchResults.xpath("//div[@class='fightCardFighterImage']//img/@src")  #create a list of fighter images from the left        
        fightBilling = searchResults.xpath("//div[contains(@class,'fightCardMatchup')]//span[@class='billing']//text()[normalize-space()]")  #create a list of fight billing (main event, main card, etc.)
        fightWeight = searchResults.xpath("//div[contains(@class,'fightCardMatchup')]//span[@class='weight']//text()[normalize-space()]")  #create a list of fight billing (main event, main card, etc.)
        posterURL = searchResults.xpath("//div[@class='details details_with_poster clearfix']//img/@src")[0] #get the url for the poster
        
        fightDict = {}
        i = 0
        for bout in boutNumbers:
            fightDict[bout] = {}
            fightDict[bout]['fighter1']    = fighterLeft[i]
            fightDict[bout]['fighter2']    = fighterRight[i]
            fightDict[bout]['fighter1pic'] = fighterImages[i*2]
            fightDict[bout]['fighter2pic'] = fighterImages[i*2+1]
            fightDict[bout]['weight']      = fightWeight[i]
            if bout > boutCount[3]:
                fightDict[bout]['billing'] = fightBilling[i]            
            else:
                fightDict[bout]['billing'] = 'Early Prelim'
            i += 1   
        
        #build the summary & add fighters (actors/roles)
        metadata.roles.clear()
        summaryList = []
        i = 0
        for bout in sorted(fightDict, reverse=True):
            if eventSegment == 'maincard':
                if fightDict[bout]['billing'] in ['Main Card', 'Main Event', 'Co-Main Event']:
                    summaryList.append(FormatFight(fightDict[bout]))
                    role = metadata.roles.new()
                    role.name = fightDict[bout]['fighter1']
                    role.photo = fightDict[bout]['fighter1pic']
                    role = metadata.roles.new()
                    role.name = fightDict[bout]['fighter2']
                    role.photo = fightDict[bout]['fighter2pic']                    
            if eventSegment == 'prelims':
                if fightDict[bout]['billing'] in ['Prelim']:
                    summaryList.append(FormatFight(fightDict[bout]))
                    role = metadata.roles.new()
                    role.name = fightDict[bout]['fighter1']
                    role.photo = fightDict[bout]['fighter1pic']
                    role = metadata.roles.new()
                    role.name = fightDict[bout]['fighter2']
                    role.photo = fightDict[bout]['fighter2pic']                    
            if eventSegment == 'earlyprelims':
                if fightDict[bout]['billing'] in ['Early Prelim']:
                    summaryList.append(FormatFight(fightDict[bout]))
                    role = metadata.roles.new()
                    role.name = fightDict[bout]['fighter1']
                    role.photo = fightDict[bout]['fighter1pic']
                    role = metadata.roles.new()
                    role.name = fightDict[bout]['fighter2']
                    role.photo = fightDict[bout]['fighter2pic']                                        
            if eventSegment == 'postlims':
                if fightDict[bout]['billing'] in ['Postlim']:
                    summaryList.append(FormatFight(fightDict[bout]))
                    role = metadata.roles.new()
                    role.name = fightDict[bout]['fighter1']
                    role.photo = fightDict[bout]['fighter1pic']
                    role = metadata.roles.new()
                    role.name = fightDict[bout]['fighter2']
                    role.photo = fightDict[bout]['fighter2pic']                    
           
        summary = ', '.join(summaryList)
        
        metadata.title                   = title
        metadata.summary                 = summary
        metadata.studio                  = studio
        metadata.originally_available_at = Datetime.ParseDate(eventDate).date()
        metadata.posters[posterURL] = Proxy.Media(HTTP.Request(posterURL))
        if Prefs['collection']:
            metadata.collections.add(eventPromotion)
        Log('update() ended')
