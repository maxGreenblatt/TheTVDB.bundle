import re, time, unicodedata, hashlib, types

# Define proxy for TVDB.
TVDB_SITE  = 'thetvdb.com'
TVDB_PROXY = 'thetvdb.plexapp.com'

TVDB_API_KEY    = 'D4DDDAEFAD083E6F'
TVDB_SEARCH_URL = 'http://%s/api/GetSeries.php?seriesname=%%s&language=%%s' % TVDB_PROXY 
TVDB_ADVSEARCH_NETWORK  = 'http://%s/index.php?seriesname=%%s&fieldlocation=1&genre=&year=%%s&network=%%s&zap2it_id=&tvcom_id=&imdb_id=&order=translation&searching=Search&tab=advancedsearch&language=%%s' % TVDB_PROXY

TVDB_GUID_SEARCH  = 'http://meta.plex.tv/tv/guid/'
TVDB_QUICK_SEARCH = 'http://meta.plex.tv/tv/names/'
TVDB_TITLE_SEARCH = 'http://meta.plex.tv/tv/titles/'

TVDB_SERIES_URL = '%%s/api/%s/series/%%s' % TVDB_API_KEY
TVDB_ZIP_URL    = '%s/all/%%s.zip' % TVDB_SERIES_URL
TVDB_SERIES_URL = '%s/%%s.xml' % TVDB_SERIES_URL
TVDB_BANNER_URL = '%s/banners/'

GOOGLE_JSON_TVDB = 'http://ajax.googleapis.com/ajax/services/search/web?v=1.0&rsz=large&q=%s+"thetvdb.com"+series+%s'
GOOGLE_JSON_TVDB_TITLE = 'http://ajax.googleapis.com/ajax/services/search/web?v=1.0&rsz=large&q=%s+"thetvdb.com"+series+info+%s'
GOOGLE_JSON_BROAD = 'http://ajax.googleapis.com/ajax/services/search/web?v=1.0&rsz=large&q=%s+site:thetvdb.com+%s'
GOOGLE_JSON_IMDB = 'http://ajax.googleapis.com/ajax/services/search/web?v=1.0&rsz=large&q=%s+site:imdb.com+tv+%s'

SCRUB_FROM_TITLE_SEARCH_KEYWORDS = ['uk','us']
NETWORK_IN_TITLE = ['bbc']
EXTRACT_AS_KEYWORDS = ['uk','us','bbc']

# Extras
THETVDB_EXTRAS_URL = 'http://meta.plex.tv/tv_e/%s/%s/%s'
IVA_ASSET_URL = 'iva://api.internetvideoarchive.com/2.0/DataService/VideoAssets(%s)?lang=%s&bitrates=%s&duration=%s'
TYPE_ORDER = ['primary_trailer', 'trailer', 'behind_the_scenes', 'interview', 'scene_or_sample']
EXTRA_TYPE_MAP = {'primary_trailer' : TrailerObject,
                  'trailer' : TrailerObject,
                  'interview' : InterviewObject,
                  'behind_the_scenes' : BehindTheScenesObject,
                  'scene_or_sample' : SceneOrSampleObject}
IVA_LANGUAGES = {-1   : Locale.Language.Unknown,
                  0   : Locale.Language.English,
                  12  : Locale.Language.Swedish,
                  3   : Locale.Language.French,
                  2   : Locale.Language.Spanish,
                  32  : Locale.Language.Dutch,
                  10  : Locale.Language.German,
                  11  : Locale.Language.Italian,
                  9   : Locale.Language.Danish,
                  26  : Locale.Language.Arabic,
                  44  : Locale.Language.Catalan,
                  8   : Locale.Language.Chinese,
                  18  : Locale.Language.Czech,
                  80  : Locale.Language.Estonian,
                  33  : Locale.Language.Finnish,
                  5   : Locale.Language.Greek,
                  15  : Locale.Language.Hebrew,
                  36  : Locale.Language.Hindi,
                  29  : Locale.Language.Hungarian,
                  276 : Locale.Language.Indonesian,
                  7   : Locale.Language.Japanese,
                  13  : Locale.Language.Korean,
                  324 : Locale.Language.Latvian,
                  21  : Locale.Language.Norwegian,
                  24  : Locale.Language.Persian,
                  40  : Locale.Language.Polish,
                  17  : Locale.Language.Portuguese,
                  28  : Locale.Language.Romanian,
                  4   : Locale.Language.Russian,
                  105 : Locale.Language.Slovak,
                  25  : Locale.Language.Thai,
                  64  : Locale.Language.Turkish,
                  493 : Locale.Language.Ukrainian,
                  50  : Locale.Language.Vietnamese}

netLock = Thread.Lock()

# Language table
# NOTE: if you add something here, make sure
# to add the language to the appropriate 
# tvdb cache download script on the data
# processing servers
THETVDB_LANGUAGES_CODE = {
  'cs': '28',
  'da': '10',
  'de': '14',
  'el': '20',
  'en': '7',
  'es': '16',
  'fi': '11',
  'fr': '17',
  'he': '24',
  'hu': '19',
  'it': '15',
  'ja': '25',
  'ko': '32',
  'nl': '13',
  'no': '9',
  'pl': '18',
  'pt': '26',
  'ru': '22',
  'sv': '8',
  'tr': '21',
  'zh': '6',
  'sl': '30'
}

ROMAN_NUMERAL_MAP = {
    ' i:': ' 1:',
    ' ii:': ' 2:',
    ' iii:': ' 3:',
    ' iv:': ' 4:',
    ' v:': ' 5:',
    ' vi:': ' 6:',
    ' vii:': ' 7:',
    ' viii:': ' 8:',
    ' ix:': ' 9:',
    ' x:': ' 10:',
    ' xi:': ' 11:',
    ' xii:': ' 12:',
}

GOOD_MATCH_THRESHOLD = 98 # Short circuit once we find a match better than this.

HEADERS = {'User-agent': 'Plex/Nine'}

def GetResultFromNetwork(url, fetchContent=True):

    Log("Retrieving URL: " + url)

    try:
      result = HTTP.Request(url, headers=HEADERS, timeout=60)
    except:
      try:
        url = url.replace(TVDB_PROXY, TVDB_SITE)
        Log("Falling back to non-proxied URL: " + url)
        result = HTTP.Request(url, headers=HEADERS, timeout=60)
      except:
        return None

    if fetchContent:
      result = result.content

    return result

def Start():
  
  Dict['ZIP_MIRROR'] = 'http://' + TVDB_PROXY
  Dict['IMG_MIRROR'] = 'http://' + TVDB_PROXY
  HTTP.CacheTime = CACHE_1HOUR * 24
  
class TVDBAgent(Agent.TV_Shows):
  
  name = 'TheTVDB'
  languages = [Locale.Language.English, 'fr', 'zh', 'sv', 'no', 'da', 'fi', 'nl', 'de', 'it', 'es', 'pl', 'hu', 'el', 'tr', 'ru', 'he', 'ja', 'pt', 'cs', 'ko', 'sl']

  def getGoogleResult(self, url):
    res = JSON.ObjectFromURL(url)
    if res['responseStatus'] != 200:
      res = JSON.ObjectFromURL(url, cacheTime=0)
    time.sleep(0.5)
    return res
    
  def dedupe(self, results):

    # make sure to keep the highest score for the id
    results.Sort('score', descending=True)

    toWhack = []
    resultMap = {}
    for result in results:
      if not resultMap.has_key(result.id):
        resultMap[result.id] = True
      else:
        toWhack.append(result)
    for dupe in toWhack:
      results.Remove(dupe)
    
  def searchByGuid(self, results, lang, title, year):
    
    # Compute the GUID
    guid = self.titleyear_guid(title,year)

    penalty = 0
    maxPercentPenalty = 30
    maxLevPenalty = 10
    minPercentThreshold = 25

    try:
      res = XML.ElementFromURL(TVDB_GUID_SEARCH + guid[0:2] + '/' + guid + '.xml')
      for match in res.xpath('//match'):
        guid    = match.get('guid')
        count = int(match.get('count'))
        pct   = int(match.get('percentage'))
        penalty += int(maxPercentPenalty * ((100-pct)/100.0))

        if pct > minPercentThreshold:
          try:
            xml = XML.ElementFromString(GetResultFromNetwork(TVDB_SERIES_URL % (Dict['ZIP_MIRROR'], guid, lang)))
            name = xml.xpath('//Data/Series/SeriesName')[0].text
            penalty += int(maxLevPenalty * (1 - self.lev_ratio(name,title)))
            try: year = xml.xpath('//Data/Series/FirstAired')[0].text.split('-')[0]
            except: year = None
            Log('Adding (based on guid lookup) id: %s, name: %s, year: %s, lang: %s, score: %s' % (match.get('guid'),name,year,lang,100-penalty))
            results.Append(MetadataSearchResult(id=match.get('guid'), name=name, year=year, lang=lang, score=100-penalty))
          except:
            continue

    except Exception, e:
      Log(repr(e))
      pass
    
  def searchByWords(self, results, lang, origTitle, year):
    # Process the text.
    title = origTitle.lower()
    title = re.sub(r'[\'":\-&,.!~()]', ' ', title)
    title = re.sub(r'[ ]+', ' ', title)
    
    # Search for words.
    show_map = {}
    total_words = 0
    
    for word in title.split():
      if word not in ['a', 'the', 'of', 'and']:
        total_words += 1
        wordHash = hashlib.sha1()
        wordHash.update(word.encode('utf-8'))
        wordHash = wordHash.hexdigest()
        try:
          matches = XML.ElementFromURL(TVDB_QUICK_SEARCH + lang + '/' + wordHash[0:2] + '/' + wordHash + '.xml', cacheTime=60)
          for match in matches.xpath('//match'):
            id = match.get('id')
            title = match.get('title')
            titleYear = match.get('year')
            # Make sure we use the None type (not the string 'None' which evaluates to true and sorts differently).
            if titleYear == 'None': 
              titleYear = None
            
            if not show_map.has_key(id):
              show_map[id] = [id, title, titleYear, 1]
            else:
              show_map[id] = [id, title, titleYear, show_map[id][3] + 1]
        except:
          pass
          
    resultList = show_map.values()  
    resultList.sort(lambda x, y: cmp(y[3],x[3]))
    

    for i,result in enumerate(resultList):

      if i > 10:
        break

      score = 90 # Start word matches off at a slight defecit compared to guid matches.
      theYear = result[2]
      
      # Remove year suffixes that can mess things up.
      searchTitle = origTitle
      if len(origTitle) > 8:
        searchTitle = re.sub(r'([ ]+\(?[0-9]{4}\)?)', '', searchTitle)
      
      foundTitle = result[1]
      if len(foundTitle) > 8:
        foundTitle = re.sub(r'([ ]+\(?[0-9]{4}\)?)', '', foundTitle)
        
      # Remove prefixes that can screw things up.
      searchTitle = re.sub('^[Bb][Bb][Cc] ', '', searchTitle)
      foundTitle = re.sub('^[Bb][Bb][Cc] ', '', foundTitle)
      
      # Adjust if both have 'the' prefix by adding a prefix that won't be stripped.
      distTitle = searchTitle
      distFoundTitle = foundTitle
      if searchTitle.lower()[0:4] == 'the ' and foundTitle.lower()[0:4] == 'the ':
        distTitle = 'xxx' + searchTitle
        distFoundTitle = 'xxx' + foundTitle
        
      # Score adjustment for title distance.
      score = score - int(30 * (1 - self.lev_ratio(searchTitle, foundTitle)))

      # Discount for mismatched years.
      if theYear != None and year != None and theYear != year:
        score = score - 5

      # Discout for later results.
      score = score - i * 5

      # Use a relatively high threshold here to avoid pounding TheTVDB with a bunch of bogus stuff that 404's on our proxies.
      if score > 70:

        # Make sure TheTVDB has heard of this show and we'll be able to parse the results.
        try: 
          res = XML.ElementFromString(GetResultFromNetwork(TVDB_SERIES_URL % (Dict['ZIP_MIRROR'], result[0], lang)))
          Log('Adding (based on word matches) id: %s, name: %s, year: %s, lang: %s, score: %s' % (result[0],result[1],result[2],lang,score))
          results.Append(MetadataSearchResult(id=result[0], name=result[1], year=result[2], lang=lang, score=score))
        except:
          Log('Skipping match with id %s: failed TVDB lookup.' % result[0])
    
    # Sort.
    results.Sort('score', descending=True)


  def search(self, results, media, lang, manual=False):

    if media.primary_agent == 'com.plexapp.agents.themoviedb':

      # Get the TVDB id from the Movie Database Agent
      tvdb_id = Core.messaging.call_external_function(
        'com.plexapp.agents.themoviedb',
        'MessageKit:GetTvdbId',
        kwargs = dict(
          tmdb_id = media.primary_metadata.id
        )
      )

      if tvdb_id:
        results.Append(MetadataSearchResult(
          id = tvdb_id,
          score = 100
        ))

      return


    doGoogleSearch = False
    if manual:
      doGoogleSearch = True
    
    # MAKE SURE WE USE precomposed form, since that seems to be what TVDB prefers.
    media.show = unicodedata.normalize('NFC', unicode(media.show)).strip()

    # If we got passed in something that looks like an ID, use it.
    if len(media.show) > 3 and re.match('^[0-9]+$', media.show) is not None:
      url = TVDB_PROXY + '?tab=series&id=' + media.show
      self.TVDBurlParse(media, lang, results, 100, 0, url)

    if not doGoogleSearch:
      
      # GUID-based matches.
      self.searchByGuid(results, lang, media.show, media.year)
      results.Sort('score', descending=True)

      for i,r in enumerate(results):
        if i > 2:
          break
        Log('Top GUID result: ' + str(results[i]))

      if not len(results) or results[0].score <= GOOD_MATCH_THRESHOLD:
        # No good-enough matches in GUID search, try word matches.
        self.searchByWords(results, lang, media.show, media.year)
        self.dedupe(results)
        results.Sort('score', descending=True)

        for i,r in enumerate(results):
          if i > 2:
            break
          Log('Top GUID+name result: ' + str(results[i]))


    if len(results) == 0:
      doGoogleSearch = True
     
    mediaYear = ''
    if media.year is not None:
      mediaYear = ' (' + media.year + ')'
    w = media.show.lower().split(' ')
    keywords = ''
    for k in EXTRACT_AS_KEYWORDS:
      if k.lower() in w:
        keywords = keywords + k + '+'
    cleanShow =  self.util_cleanShow(media.show, SCRUB_FROM_TITLE_SEARCH_KEYWORDS)
    cs = cleanShow.split(' ')
    cleanShow = ''
    for x in cs:
      cleanShow = cleanShow + 'intitle:' + x + ' '
      
    cleanShow = cleanShow.strip()
    origShow = media.show
    SVmediaShowYear = {'normal':String.Quote((origShow + mediaYear).encode('utf-8'), usePlus=True).replace('intitle%3A', 'intitle:'),
                       'clean': String.Quote((cleanShow + mediaYear).encode('utf-8'), usePlus=True).replace('intitle%3A','intitle:')}
    mediaShowYear = SVmediaShowYear['normal']
    
    if doGoogleSearch:
      searchVariations = [SVmediaShowYear]
      if media.year is not None:
        SVmediaShow = {'normal':String.Quote((origShow).encode('utf-8'), usePlus=True).replace('intitle%3A', 'intitle:'),
                       'clean': String.Quote((cleanShow).encode('utf-8'), usePlus=True).replace('intitle%3A', 'intitle:')}
        searchVariations.append(SVmediaShow)
  
      #option to perform searches without the year, in the event we have no results over our match threshold
      for sv in searchVariations:
        #check to make sure we want to run these searches again WITHOUT the year hint, if there was one passed in
        if len(results) > 0:
          results.Sort('score', descending=True)
          if results[0].score >= 80:
            Log('skipping search engines')
            break #don't bother trying search without year, we have a match
        Log('hitting search engines')
            
        #run through several search engines
        resultDict = {}
        @parallelize
        def hitSearchEngines():
          for s in [GOOGLE_JSON_TVDB, GOOGLE_JSON_TVDB_TITLE, GOOGLE_JSON_IMDB, GOOGLE_JSON_BROAD]: #
            resultDict[s] = []
            @task
            def UpdateEpisode(s=s,sv=sv):
              hasResults = False
              if s in [GOOGLE_JSON_TVDB_TITLE]:
                tmpMediaShowYear = sv['clean'] #String.Quote((cleanShow + mediaYear).encode('utf-8'), usePlus=True).replace('intitle%3A','intitle:')
              else:
                tmpMediaShowYear = sv['normal']
              #make sure we have results and normalize
              if s.count('googleapis.com') > 0:
                jsonObj = self.getGoogleResult(s % (tmpMediaShowYear, keywords))['responseData']['results']
                if len(jsonObj) > 0:
                  hasResults = True
    
              #loop through results   
              if hasResults:
                for r in jsonObj:
                  scorePenalty = 0
                  url = None
                  if s.count('googleapis.com') > 0:
                    url = r['unescapedUrl']
                  
                  if url:
                    resultDict[s].append((url, scorePenalty))
              
        @parallelize
        def loopResults():
          for s in resultDict:  
            if s in [GOOGLE_JSON_TVDB, GOOGLE_JSON_IMDB, GOOGLE_JSON_TVDB_TITLE, GOOGLE_JSON_BROAD]:
              score = 99
            else:
              break
            for url, scorePenalty in resultDict[s]:          
              @task
              def lookupResult(score=score, url=url, scorePenalty=scorePenalty):
                self.TVDBurlParse(media, lang, results, score, scorePenalty, url)
              score = score - 5
      
    #try an exact tvdb match    
    try:
      Log('Searching for exact match with: ' + mediaShowYear)
      el = XML.ElementFromString(GetResultFromNetwork(TVDB_SEARCH_URL % (mediaShowYear, lang))).xpath('.//Series')[0]
      series_name = el.xpath('SeriesName')[0].text
      if series_name.lower().strip() == media.show.lower().strip():
        id = el.xpath('id')[0].text
        self.ParseSeries(media, el, lang, results, 90)
      elif series_name[:series_name.rfind('(')].lower().strip() == media.show.lower().strip():
        id = el.xpath('id')[0].text
        self.ParseSeries(media, el, lang, results, 86)
    except Exception, e:
      Log(repr(e))
      pass
      
    self.dedupe(results)

    favorNewerShows = True
    if favorNewerShows:  
      #hunt for duplicate shows with different years
      resultMap = {}
      for result in results:
        for check in results:
          if result.name == check.name and result.id != check.id:
            resultMap[result.year] = result
          
      years = resultMap.keys()
      years.sort(reverse=True)
      
      #bump the score of newer dupes
      i=0
      for y in years[:-1]:
        if resultMap[y].score <= resultMap[years[i+1]].score:
          resultMap[y].score = resultMap[years[i+1]].score + 1

      for i,r in enumerate(results):
        if i > 10:
          break
        Log('Final result: ' + str(results[i]))
          
  def TVDBurlParse(self, media, lang, results, score, scorePenalty, url):
    if url.count('tab=series&id='):
      seriesRx = 'tab=series&id=([0-9]+)'
      m = re.search(seriesRx, url)  
    elif url.count('tab=seasonall&id='):
      seriesRx = 'tab=seasonall&id=([0-9]+)'
      m = re.search(seriesRx, url)
    else:
      seriesRx = 'seriesid=([0-9]+)'
      m = re.search(seriesRx, url)
    if m:
      id = m.groups(1)[0]
      try:
        xml = XML.ElementFromString(GetResultFromNetwork(TVDB_SERIES_URL % (Dict['ZIP_MIRROR'], id, lang)))
        if len(xml):
          self.ParseSeries(media, xml.xpath('//Series')[0], lang, results, score - scorePenalty)
      except Exception, e:
        Log('Couldn\'t find Series in TVDB XML: ' + str(e))
      
  def ParseSeries(self, media, el, lang, results, score):
    
    # Get attributes from the XML
    try:
      series_id = el.xpath('seriesid')[0].text
    except:
      series_id = el.xpath('id')[0].text
      
    series_name = el.xpath('SeriesName')[0].text
    try:
      series_year = el.xpath('FirstAired')[0].text[:4]
    except:
      series_year = None
      
    try:
      series_lang = el.xpath('language')[0].text
    except:
      series_lang = lang
      
    if not series_name:
      return

    if not media.year:
      clean_series_name = series_name.replace('(' + str(series_year) + ')','').strip().lower()
    else:
      clean_series_name = series_name.lower()

    cleanShow = self.util_cleanShow(media.show, NETWORK_IN_TITLE)
      
    #Log(media.show + ' | found: ' + series_name + ' score1: +[original] ' + str(score))
    
    substringLen = len(Util.LongestCommonSubstring(cleanShow.lower(), clean_series_name))
    cleanShowLen = len(cleanShow)
    
    maxSubstringPoints = 5.0 #use a float
    score = score + int((maxSubstringPoints * substringLen)/cleanShowLen) # max 15 for best substring match
    #Log(media.show + ' | found: ' + series_name + ' score2: +[longest substring]: ' + str(score))
    
    distanceFactor = .6
    score = score - int(distanceFactor * Util.LevenshteinDistance(cleanShow.lower(), clean_series_name))
    #Log(media.show + ' | found: ' + series_name + ' score3: +[levenshteindistance]: ' + str(score))
    
    if series_year and media.year:
      if media.year == series_year: 
        score = score + 10
      else:
        score = score - 10
    
    #sanity check to make sure we have SOME common substring
    if (float(substringLen) / cleanShowLen) < .15: #if we don't have at least 15% in common, then penalize below the 80 point threshold
      score = score - 25
      
    #Log(media.show + ' | found: ' + series_name + ' score4: +[year match]: ' + str(score))
    
    # Add a result for this show
    results.Append(
      MetadataSearchResult(
        id    = series_id,
        name  = series_name,
        year  = series_year,
        lang  = series_lang,
        score = score
      )
    )

  def readTags(self, element, list, name):
    try:
      el_text = lambda element, xp: element.xpath(xp)[0].text
      tag_text = el_text(element, name)
      if tag_text.find('|') != -1:
        tags = tag_text.split('|')
      else:
        tags = tag_text.split(',')
      
      tags = [tag.strip() for tag in tags if len(tag) > 0]
      list.clear()
      for tag in tags:
        if tag not in list:
          list.add(tag)
    except:
      pass

  def fixBrokenXml(self, xml):
    if xml.count('<?xml') > 1:
      xml = xml[xml.rfind('<?xml'):]
      if xml.count('</Data>') > 1:
        xml = xml[:-7]
        
    return xml

  def eligibleForExtras(self):
    # Extras.
    try:
      # Do a quick check to make sure we've got the types available in this framework version, and that the server
      # is new enough to support the IVA endpoints.
      t = InterviewObject()
      if Util.VersionAtLeast(Platform.ServerVersion, 0,9,9,13):
        find_extras = True
      else:
        find_extras = False
        Log('Not adding extras: Server v0.9.9.13+ required')
    except NameError, e:
      Log('Not adding extras: Framework v2.5.0+ required')
      find_extras = False
    return find_extras

  """
  Lovingly borrowed from https://stackoverflow.com/questions/794663/net-convert-number-to-string-representation-1-to-one-2-to-two-etc
  As instructed by IVA's Normalization Rules, Step 17: http://www.internetvideoarchive.com/documentation/data-integration/iva-data-matching-guidelines/
  """
  def number_to_text(self, n):
     if n < 0:
        return "Minus " + self.number_to_text(-n)
     elif n == 0:
        return ""
     elif n <= 19:
        return ("One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen")[n-1] + " "
     elif n <= 99:
        return ("Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")[n / 10 - 2] + " " + self.number_to_text(n % 10)
     elif n <= 199:
        return "One Hundred " + self.number_to_text(n % 100)
     elif n <= 999:
        return self.number_to_text(n / 100) + "Hundreds " + self.number_to_text(n % 100)
     elif n <= 1999:
        return "One Thousand " + self.number_to_text(n % 1000);
     elif n <= 999999:
        return self.number_to_text(n / 1000) + "Thousands " + self.number_to_text(n % 1000)
     elif n <= 1999999:
        return "One Million " + self.number_to_text(n % 1000000)
     elif n <= 999999999:
        return self.number_to_text(n / 1000000) + "Millions " + self.number_to_text(n % 1000000)
     elif n <= 1999999999:
        return "One Billion " + self.number_to_text(n % 1000000000);
     else:
        return self.number_to_text(n / 1000000000) + "Billions " + self.number_to_text(n % 1000000000)

  # IVA Normalization rules found here: http://www.internetvideoarchive.com/documentation/data-integration/iva-data-matching-guidelines/
  def ivaNormalizeTitle(self, title):
      title = title.strip().upper()

      title = re.sub(r'^(AN |A |THE )|(, AN |, A |, THE)$|\([^\)]+\)$|\{[^\}]+\}$|\[[^\]]+\]$| AN IMAX 3D EXPERIENCE| AN IMAX EXPERIENCE| THE IMAX EXPERIENCE| IMAX 3D EXPERIENCE| IMAX 3D', "", title)

      title = title.lower().replace('&', 'and').strip().upper()

      title = re.sub(r'^(AN |A |THE )|(, AN |, A |, THE)$', "", title)

      title = title.lower()

      title = re.sub(r'( i:| ii:| iii:| iv:| v:| vi:| vii:| viii:| ix:| x:| xi:| xii:)', lambda m: ROMAN_NUMERAL_MAP[m.group(0)], title)

      title = re.sub(r'[!@#\$%\^\*\_\+=\{\}\[\]\|<>`\:\-\(\)\?/\\\&\~\.\,\'\"]', " ", title)

      title = re.sub(r'\b\d+\b', lambda m: self.number_to_text(int(m.group())).replace('-', ' '), title)

      title = title.lower().strip().replace(',', ' ')

      title = re.sub(r'( i$| ii$| iii$| iv$| v$| vi$| vii$| viii$| ix$| x$| xi$| xii$)', lambda m: ROMAN_NUMERAL_MAP[m.group(0)+":"][:-1], title)

      title = re.sub(r'\b\d+\b', lambda m: self.number_to_text(int(m.group())).replace('-', ' '), title)

      title = title.lower()

      return title.encode('utf-8').strip().replace("  ", " ")

  def processExtras(self, xml, metadata, lang, ivaNormTitle=""):
    extras = []
    media_title = None
    for extra in xml.xpath('//extra'):
      avail = Datetime.ParseDate(extra.get('originally_available_at'))
      lang_code = int(extra.get('lang_code')) if extra.get('lang_code') else -1
      subtitle_lang_code = int(extra.get('subtitle_lang_code')) if extra.get('subtitle_lang_code') else -1

      spoken_lang = IVA_LANGUAGES.get(lang_code) or Locale.Language.Unknown
      subtitle_lang = IVA_LANGUAGES.get(subtitle_lang_code) or Locale.Language.Unknown
      include = False

      # Include extras in section language...
      if spoken_lang == lang:

        # ...if they have section language subs AND this was explicitly requested in prefs.
        if Prefs['native_subs'] and subtitle_lang == lang:
          include = True

        # ...if there are no subs.
        if subtitle_lang_code == -1:
          include = True

      # Include foreign language extras if they have subs in the section language.
      if spoken_lang != lang and subtitle_lang == lang:
        include = True

      # Always include English language extras anyway (often section lang options are not available), but only if they have no subs.
      if spoken_lang == Locale.Language.English and subtitle_lang_code == -1:
        include = True

      # Exclude non-primary trailers and scenes.
      # TODO: For now there is no primary trailer for TV
      extra_type = 'primary_trailer' if extra.get('primary') == 'true' else extra.get('type')

      if include:

        bitrates = extra.get('bitrates') or ''
        duration = int(extra.get('duration') or 0)

        # Remember the title if this is the primary trailer.
        # TODO: For now there is no primary trailer for TV
        if extra_type == 'primary_trailer':
          media_title = extra.get('title')

        # Add the extra.
        if extra_type in EXTRA_TYPE_MAP:
          extras.append({ 'type' : extra_type,
                          'lang' : spoken_lang,
                          'extra' : EXTRA_TYPE_MAP[extra_type](url=IVA_ASSET_URL % (extra.get('iva_id'), spoken_lang, bitrates, duration),
                                                               title=extra.get('title'),
                                                               year=avail.year,
                                                               originally_available_at=avail,
                                                               thumb=extra.get('thumb') or '')})
        else:
            Log('Skipping extra %s because type %s was not recognized.' % (extra.get('iva_id'), extra_type))

    # Sort the extras, making sure the primary trailer is first.
    extras.sort(key=lambda e: TYPE_ORDER.index(e['type']))

    # If our primary trailer is in English but the library language is something else, see if we can do better.
    if lang != Locale.Language.English and extras[0]['lang'] == Locale.Language.English:
      lang_matches = [t for t in xml.xpath('//extra') if t.get('type') == 'trailer' and IVA_LANGUAGES.get(int(t.get('subtitle_lang_code') or -1)) == lang]
      lang_matches += [t for t in xml.xpath('//extra') if t.get('type') == 'trailer' and IVA_LANGUAGES.get(int(t.get('lang_code') or -1)) == lang]
      if len(lang_matches) > 0:
        extra = lang_matches[0]
        spoken_lang = IVA_LANGUAGES.get(int(extra.get('lang_code') or -1)) or Locale.Language.Unknown
        extras[0]['lang'] = spoken_lang
        extras[0]['extra'].url = IVA_ASSET_URL % (extra.get('iva_id'), spoken_lang, extra.get('bitrates') or '', int(extra.get('duration') or 0))
        extras[0]['extra'].thumb = extra.get('thumb') or ''
        Log('Adding trailer with spoken language %s and subtitled langauge %s to match library language.' % (spoken_lang, IVA_LANGUAGES.get(int(extra.get('subtitle_lang_code') or -1)) or Locale.Language.Unknown))

    # Clean up the found extras.
    extras = [scrub_extra(extra, media_title) for extra in extras]

    # Add them in the right order to the metadata.extras list.
    for extra in extras:
      # TODO: Do more than just log the extras once the objects have been
      Log(extra['extra'])
      #metadata.extras.add(extra['extra'])

    Log('%s - Added %d of %d extras.' % (ivaNormTitle, len(extras), len(xml.xpath('//extra'))))

  def update(self, metadata, media, lang):
    Log("def update()")

    zip_url = TVDB_ZIP_URL % (Dict['ZIP_MIRROR'], metadata.id, lang)
    banner_root = TVDB_BANNER_URL % Dict['IMG_MIRROR']

    # Get the show's zipped data
    zip_data = GetResultFromNetwork(zip_url)
    zip_archive = Archive.Zip(zip_data)

    # Extract the XML files from the archive. Work around corrupt XML.
    root_el = XML.ElementFromString(self.fixBrokenXml(zip_archive[lang+'.xml']))
    actors_el = XML.ElementFromString(self.fixBrokenXml(zip_archive['actors.xml']))
    banners_el = XML.ElementFromString(self.fixBrokenXml(zip_archive['banners.xml']))
    
    # Close the archive
    del zip_archive
    
    # Get the root element
    series_el = root_el.xpath('Series')[0]
    
    # Convenience functions
    el_text = lambda element, xp: element.xpath(xp)[0].text if element.xpath(xp)[0].text else '' 
    parse_date = lambda s: Datetime.ParseDate(s).date()
    
    # Copy attributes from the XML element to the metadata object
    metadata.title = el_text(series_el, 'SeriesName')
    metadata.summary = el_text(series_el, 'Overview')
    metadata.content_rating = el_text(series_el, 'ContentRating')
    metadata.studio = el_text(series_el, 'Network')
    try: 
      originally_available_at = el_text(series_el, 'FirstAired')
      if len(originally_available_at) > 0:
        metadata.originally_available_at = parse_date(originally_available_at)
      else:
        metadata.originally_available_at = None
    except: pass
    try: metadata.duration = int(el_text(series_el, 'Runtime')) * 60 * 1000
    except: pass
    try: metadata.rating = float(el_text(series_el, 'Rating'))
    except: pass
    
    self.readTags(series_el, metadata.genres, 'Genre')

    # Cast
    metadata.roles.clear()
    for actor in actors_el.xpath('//Actor'):
      try:
        role = metadata.roles.new()
        role.role = actor.xpath('./Role')[0].text
        role.actor = actor.xpath('./Name')[0].text
      except:
        pass

    if metadata.title is not None and metadata.title is not '' and self.eligibleForExtras() and Prefs['extras']:
      ivaNormTitle = self.ivaNormalizeTitle(metadata.title)

      try:
        req = THETVDB_EXTRAS_URL % (metadata.id, ivaNormTitle.replace(' ', '+'), -1 if metadata.originally_available_at is None else metadata.originally_available_at.year)
        xml = XML.ElementFromURL(req)

        self.processExtras(xml, metadata, lang, ivaNormTitle)

      except Ex.HTTPError, e:
        if e.code == 403:
          Log('Skipping online extra lookup (an active Plex Pass is required).')


    # Get episode data
    @parallelize
    def UpdateEpisodes():

      for episode_el in root_el.xpath('Episode'):
        
        # Get the season and episode numbers
        season_num = el_text(episode_el, 'SeasonNumber')
        episode_num = el_text(episode_el, 'EpisodeNumber')
        
        if media is not None:
          # Also get the air date for date-based episodes.
          try: 
            originally_available_at = parse_date(el_text(episode_el, 'FirstAired'))
            date_based_season = originally_available_at.year
          except: 
            originally_available_at = date_based_season = None
          
          if not ((season_num in media.seasons and episode_num in media.seasons[season_num].episodes) or 
                  (originally_available_at is not None and date_based_season in media.seasons and originally_available_at in media.seasons[date_based_season].episodes) or 
                  (originally_available_at is not None and season_num in media.seasons and originally_available_at in media.seasons[season_num].episodes)):
            #Log("No media for season %s episode %s - skipping population of episode data", season_num, episode_num)
            continue
          
        # Get the episode object from the model
        episode = metadata.seasons[season_num].episodes[episode_num]
        
        # Create a task for updating this episode
        @task
        def UpdateEpisode(episode=episode, episode_el=episode_el, lang=lang, series_available=metadata.originally_available_at, series_id=metadata.id):

          # Copy attributes from the XML
          episode.title = el_text(episode_el, 'EpisodeName')
          episode.summary = el_text(episode_el, 'Overview')
          
          try: episode.absolute_number = int(el_text(episode_el, 'absolute_number'))
          except: pass
      
          rating = el_text(episode_el, 'Rating')
          if rating != None and len(rating) > 0: episode.rating = float(rating)
          
          try:    
            originally_available_at = el_text(episode_el, 'FirstAired')
            if originally_available_at != None and len(originally_available_at) > 0: 
              episode.originally_available_at = parse_date(originally_available_at)
          except:
            pass  
          
          self.readTags(episode_el, episode.directors, 'Director')
          self.readTags(episode_el, episode.writers, 'Writer')
          
          # Download the episode thumbnail
          valid_names = list()
          
          if len(episode_el.xpath('filename')) > 0:
            thumb_file = el_text(episode_el, 'filename')
            if thumb_file != None and len(thumb_file) > 0:
              thumb_url = banner_root + thumb_file
              thumb_data = GetResultFromNetwork(thumb_url, False)
              
              # Check that the thumb doesn't already exist before downloading it
              valid_names.append(thumb_url)
              if thumb_url not in episode.thumbs:
                try:
                  episode.thumbs[thumb_url] = Proxy.Media(thumb_data)
                except:
                  # tvdb doesn't have a thumb for this show
                  pass
                  
          episode.thumbs.validate_keys(valid_names)

          try:
            req = THETVDB_EXTRAS_URL % (series_id, ivaNormTitle.replace(' ', '+'), -1 if series_available is None else series_available.year)
            req = req + '/' + el_text(episode_el, 'SeasonNumber') + '/' + el_text(episode_el, 'EpisodeNumber')
            xml = XML.ElementFromURL(req)

            self.processExtras(xml, episode, lang, ivaNormTitle)

          except Ex.HTTPError, e:
            if e.code == 403:
              Log('Skipping online extra lookup (an active Plex Pass is required).')
      
    # Maintain a list of valid image names
    valid_names = list()
    
    @parallelize
    def DownloadImages():

      # Add a download task for each image
      i = 0
      for banner_el in banners_el.xpath('Banner'):
        i += 1
        @task
        def DownloadImage(metadata=metadata, banner_el=banner_el, i=i, valid_names=valid_names):

          # Parse the banner.
          banner_type, banner_path, banner_lang, banner_thumb, proxy = self.parse_banner(banner_el)
          
          # Check that the language matches
          if (banner_lang != lang) and (banner_lang != 'en'):
            return
            
          # Compute the banner name and prepare the data
          banner_name = banner_root + banner_path
          banner_url = banner_root + banner_thumb
          
          valid_names.append(banner_name)
          
          def banner_data(path):
            return GetResultFromNetwork(path, False)
        
          # Find the attribute to add to based on the image type, checking that data doesn't
          # already exist before downloading
          if banner_type == 'fanart' and banner_name not in metadata.art:
            try: metadata.art[banner_name] = proxy(banner_data(banner_url), sort_order=i)
            except: pass

          elif banner_type == 'poster' and banner_name not in metadata.posters:
            try: metadata.posters[banner_name] = proxy(banner_data(banner_url), sort_order=i)
            except: pass

          elif banner_type == 'series':
            if banner_name not in metadata.banners:
              try: metadata.banners[banner_name] = proxy(banner_data(banner_url), sort_order=i)
              except: pass

          elif banner_type == 'season':
            banner_type_2 = el_text(banner_el, 'BannerType2')
            season_num = el_text(banner_el, 'Season')
            
            # Need to check for date-based season (year) as well.
            try:
              date_based_season = (int(season_num) + metadata.originally_available_at.year - 1)
            except:
              date_based_season = None
            
            if media is None or season_num in media.seasons or date_based_season in media.seasons:
              if banner_type_2 == 'season' and banner_name not in metadata.seasons[season_num].posters:
                try: metadata.seasons[season_num].posters[banner_name] = proxy(banner_data(banner_url), sort_order=i)
                except: pass

              elif banner_type_2 == 'seasonwide' and banner_name not in metadata.seasons[season_num].banners:
                try: metadata.seasons[season_num].banners[banner_name] = proxy(banner_data(banner_url), sort_order=i)
                except: pass
            
            else:
              #Log('No media for season %s - skipping download of %s', season_num, banner_name)
              pass
              
    # Fallback to foreign art if localized art doesn't exist.
    if len(metadata.art) == 0 and lang == 'en':
      i = 0
      for banner_el in banners_el.xpath('Banner'):
        banner_type, banner_path, banner_lang, banner_thumb, proxy = self.parse_banner(banner_el)
        banner_name = banner_root + banner_path
        if banner_type == 'fanart' and banner_name not in metadata.art:
          try: metadata.art[banner_name] = proxy(self.banner_data(banner_root + banner_thumb), sort_order=i)
          except: pass
          
    # Check each poster, background & banner image we currently have saved. If any of the names are no longer valid, remove the image 
    metadata.posters.validate_keys(valid_names)
    metadata.art.validate_keys(valid_names)
    metadata.banners.validate_keys(valid_names)

    # Grab season level extras
    for season_num in metadata.seasons:
      try:
        req = THETVDB_EXTRAS_URL % (metadata.id, ivaNormTitle.replace(' ', '+'), -1 if metadata.originally_available_at is None else metadata.originally_available_at.year)
        req = req + '/' + season_num
        xml = XML.ElementFromURL(req)

        self.processExtras(xml, metadata.seasons[season_num], lang, ivaNormTitle)

      except Ex.HTTPError, e:
        if e.code == 403:
          Log('Skipping online extra lookup (an active Plex Pass is required).')

  def parse_banner(self, banner_el):
    el_text = lambda element, xp: element.xpath(xp)[0].text if element.xpath(xp)[0].text else '' 

    # Get the image attributes from the XML
    banner_type = el_text(banner_el, 'BannerType')
    banner_path = el_text(banner_el, 'BannerPath')
    try:
      banner_thumb = el_text(banner_el, 'ThumbnailPath')
      proxy = Proxy.Preview
    except:
      banner_thumb = banner_path
      proxy = Proxy.Media
    banner_lang = el_text(banner_el, 'Language')

    return (banner_type, banner_path, banner_lang, banner_thumb, proxy)
  
  def banner_data(self, path):
    return GetResultFromNetwork(path, False)
  
  def util_cleanShow(self, cleanShow, scrubList):
    for word in scrubList:
      c = word.lower()
      l = cleanShow.lower().find('(' + c + ')')
      if l >= 0:
        cleanShow = cleanShow[:l] + cleanShow[l+len(c)+2:]
      l = cleanShow.lower().find(' ' + c)
      if l >= 0:
        cleanShow = cleanShow[:l] + cleanShow[l+len(c)+1:]
      l = cleanShow.lower().find(c + ' ')
      if l >= 0:
        cleanShow = cleanShow[:l] + cleanShow[l+len(c)+1:]
    return cleanShow

  def identifierize(self, string):
    string = re.sub( r"\s+", " ", string.strip())
    string = unicodedata.normalize('NFKD', self.safe_unicode(string))
    string = re.sub(r"['\"!?@#$&%^*\(\)_+\.,;:/]","", string)
    string = re.sub(r"[_ ]+","_", string)
    string = string.strip('_')
    return string.strip().lower()
  
  def safe_unicode(self, s,encoding='utf-8'):
    if s is None:
      return None
    if isinstance(s, basestring):
      if isinstance(s, types.UnicodeType):
        return s
      else:
        return s.decode(encoding)
    else:
      return str(s).decode(encoding)
  
  def guidize(self,string):
    hash = hashlib.sha1()
    hash.update(string.encode('utf-8'))
    return hash.hexdigest()
  
  def titleyear_guid(self, title, year=None):
    if title is None:
      title = ''
  
    if year == '' or year is None or not year:
      string = u"%s" % self.identifierize(title)
    else:
      string = u"%s_%s" % (self.identifierize(title), year)
    return self.guidize(string)

  def lev_ratio(self,s1,s2):
    distance = Util.LevenshteinDistance(self.safe_unicode(s1),self.safe_unicode(s2))
    #Log('s1/s2: "%s" / "%s"' % (s1,s2))
    #Log('distance: %s' % distance)
    max_len  = float(max([ len(s1), len(s2) ]))
    #Log('max_len: %s' % max_len)

    ratio = 0.0
    try:
      ratio = float(1 - (distance/max_len))
    except:
      pass

    #Log('ratio: %s' % ratio)
    return ratio

  def best_title_by_language(self, lang, localTitle, tvdbID ):
 
    ## this returns not only the best title, but the best
    ## levenshtien ratio found amongst all of the titles
    ## in the title list... the lev ratio is to give an overall
    ## confidence that the local title corresponds to the
    ## tvdb id.. even if the picked title is in a language 
    ## other than the locally named title

    titles = { 'best_lev_ratio': { 'title': None, 'lev_ratio': -1.0 } } # -1 to force > check later
    try:
      res = XML.ElementFromURL(TVDB_TITLE_SEARCH + tvdbID[0:2] + '/' + tvdbID + '.xml')
      for row in res.xpath("/records/record"):
        t = row['title']
        l = row['lang']
        lev   = self.lev_ratio(localTitle,t)
        titles[lang] = { 'title': t, 'lev_ratio': lev, 'lang': l }
        if lev > titles.get('best_lev_ratio').get('lev_ratio'):
          titles['best_lev_ratio'] = { 'title': t, 'lev_ratio': lev, 'lang': l }
    except Exception, e:
      Log(e)
      return (localTitle, lang, 0.0)

    bestLevRatio = titles.get('best_lev_ratio').get('lev_ratio')
    if bestLevRatio < 0:
      return (localTitle, lang, 0.0)

    useTitle = None
    if titles.has_key(lang):
      useTitle = titles.get(lang)
    elif titles.has_key('en'):
      useTitle = titles.get('en')
    else:
      useTitle = titles.get('best_lev_ratio')

    return (useTitle.get('title'), useTitle.get('lang'), useTitle.get('lev_ratio'))

def scrub_extra(extra, media_title):

  e = extra['extra']

  # Remove the "Movie Title: " from non-trailer extra titles.
  if media_title is not None:
    r = re.compile(media_title + ': ', re.IGNORECASE)
    e.title = r.sub('', e.title)

  # Remove the "Movie Title Scene: " from SceneOrSample extra titles.
  if media_title is not None:
    r = re.compile(media_title + ' Scene: ', re.IGNORECASE)
    e.title = r.sub('', e.title)

  # Capitalise UK correctly.
  e.title = e.title.replace('Uk', 'UK')

  return extra
