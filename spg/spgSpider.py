#!/usr/bin/python3
# -*- coding: utf-8 -*-

from queue import Queue
from time import sleep
from time import time
import re
import threading
import requests
from lxml import etree

class SpgSpider():
    #class attribute, to control threads
    CRAWLER_EXIT = False
    def __init__(self):
        # ====================== user define area --- begin ============================
        self.threadNum = 10
        self.initUrl = "https://www.starwoodhotels.com/index.html"
        self.getCitiesUrl = "http://www.starwoodhotels.com/common/ajax/ref/getCities.json"
        self.getHotelUrl = "https://www.starwoodhotels.com/preferredguest/search/results/grid.html"
        self.UA = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.79 Safari/537.36"
        self.headers = {
            "User-Agent":self.UA,
            "Connection":"keep-alive",
            "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding":"gzip, deflate",
            "Accept-Language":"en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,zh-TW;q=0.6"
        }
        self.initPayload = {
            "language":"zh_CN",
            "localeCode":"zh_CN"
        }
        self.provinceXpath = '//div[@class="searchBox"]//select[contains(@class, "CN")]/optgroup/option/'
        self.hotelXpath = [
            #hotel Chinese names
            '//div[@class="propertyOuter"]//div[@class="propertyInfo"]/a/span/text()',
            #hotel English names
            '//div[@class="propertyOuter"]//div[@class="propertyInfo"]/a/span/p/text()',
            #hotel links
            '//div[@class="propertyOuter"]//div[@class="propertyInfo"]/a/@href',
            #hotel price --- xpath matches valid price OR inactive status
            '//div[@class="propertyOuter"]//div[@class="rateOptions"]//a[1]//span[contains(@class, "currency")]/text() \
            | //div[@class="propertyOuter"]//div[@class="rateOptions"]//span[contains(@class, "inactive")]//text() \
            | //div[@class="propertyOuter"]//div[@class="rateOptions"]//span[contains(@class, notAvailable) and @data-rate-option="rateCode:DFRLME"]//span[@class="rates"]/span/text()',
            #hotel starPoints
            '//div[@class="propertyOuter"]//div[@class="rateOptions"]//a[2]//span[contains(@class, "starPoints")]/text()[1] \
            | //div[@class="propertyOuter"]//div[@class="rateOptions"]//a[2][contains(@class, "redeem")]//span[@class="rates"]/text() \
            | //div[@class="propertyOuter"]//div[@class="rateOptions"]//span[contains(@class, "inactive")]//text() \
            | //div[@class="propertyOuter"]//div[@class="rateOptions"]//span[contains(@class, notAvailable) and @data-rate-option="ratePlanId:SPG"]//span[@class="rates"]/span/text()',
        ]
        self.searchConfig = {
            "country":"CN",
            "arrivalDate":"18年07月28日",
            "departureDate":"18年07月29日",
            "numberOfRooms":"1",
            "numberOfAdults":"2",
            "numberOfChildren":"1",
            "iataNumber":""
        }
        self.hotelsFileName = "hotels_%s.txt"%self.searchConfig["arrivalDate"]
        self.priceFileName = "price_%s.txt"%self.searchConfig["arrivalDate"]
        self.pointFileName= "point_%s.txt"%self.searchConfig["arrivalDate"]
        self.profitFileName= "profit_%s.txt"%self.searchConfig["arrivalDate"]
        #calculate profit only with points >= pointThreshold
        self.pointThreshold = 5000
        # ====================== user define area --- end ============================
        #item in hotelUrlProvinceQueue is provinceCode
        self.hotelUrlProvinceQueue = Queue()
        #item in hotelResultQueue is provinceInfo including hotelNames, hotelLinks, hotelPrices, hotelPoints
        self.hotelResultQueue = Queue()
        self.totalHotelInfo = []

    def spider(self):
        self.initPageSource = self.get_page()
        self.provinceNameList, self.provinceCodeList = self.get_province(self.initPageSource)
        self.hotel_crawler()
        self.dataProcess()

    def get_page(self):
        self.session = requests.session()
        #self.session.proxies = dict(http="192.168.0.110:8888",https="192.168.0.110:8888")   #Make traffic go through host, thus Fiddler in host can capture Python requests
        response = self.session.get(self.initUrl, headers=self.headers, params=self.initPayload, verify=False)
        pageSource = response.text
        return pageSource

    def get_province(self, pageSource):
        html = etree.HTML(pageSource)
        province = html.xpath(self.provinceXpath+"text()")
        provinceCode = html.xpath(self.provinceXpath+"@value")
        print(province)
        print(provinceCode)
        for pCode in provinceCode:
            self.hotelUrlProvinceQueue.put(pCode)
        return province, provinceCode

    def hotel_crawler(self):
        ''' ------ this is a multi-thread controller ------
        '''
        #save cookies in SpgSpider.session and transfer to threads
        cookies = self.session.cookies
        #threads control
        crawlerList = []
        for i in range(0, self.threadNum):
            crawlerList.append("webCrawler_NO.%s"%i)
        print(crawlerList)
        threadPool = []
        for crawlerName in crawlerList:
            thread = ThreadGetAndParse(self.hotelUrlProvinceQueue, self.hotelResultQueue, crawlerName, self.headers, cookies, self.getHotelUrl, self.hotelXpath, self.searchConfig)
            thread.start()
            threadPool.append(thread)
        # keep threading until payloadQueue is empty
        while not self.hotelUrlProvinceQueue.empty():
            pass
        # change flag to make threads end
        SpgSpider.CRAWLER_EXIT = True
        print("payload queue is empty")
        #wait until threads ends
        for thread in threadPool:
            thread.join()
        print("------ Web Crawlers Are Finished ------")

    def dataProcess(self):
        #generate pCode <---> provinceChineseName dict
        provinceDict = {}
        #generate hotelDict, key=hotelName, value=otherAttribute
        hotelDict = {}
        for i in range(0, len(self.provinceCodeList)):
            provinceDict[self.provinceCodeList[i]] = self.provinceNameList[i]
        print(provinceDict)
        #generate new data struct based on resultQueue
        garbageWord = "\r\t\n "
        #wf2 = open('hotelDict.txt', 'w')
        with open(self.hotelsFileName, 'w') as wf:
        # ------ process resultQueue --- while loop start
            while self.hotelResultQueue.empty() is not True:
                provinceInfo = self.hotelResultQueue.get()
                pName = provinceDict[provinceInfo["provinceCode"]]
                hotelNum = len(provinceInfo["linkList"])
                if hotelNum==0:
                    print("There is no valid information in "+pName)
                else:
                    #nameLen = len(provinceInfo["nameList"])
                    #priceLen = len(provinceInfo["priceList"])
                    #pointLen = len(provinceInfo["pointList"])
                    #print("nameNum = %s, linkNum = %s, priceLen = %s, pointLen = %s"%(nameLen, hotelNum, priceLen, pointLen))
                    for i in range(0, hotelNum):
                        hotelName = provinceInfo["nameList"][i].strip(garbageWord)
                        hotelLink = "https://www.starwoodhotels.com/"+provinceInfo["linkList"][i].strip(garbageWord)
                        hotelPrice = provinceInfo["priceList"][i].strip(garbageWord)
                        hotelPoint = provinceInfo["pointList"][i].strip(garbageWord)
                        #This is 1st processing result: write whole original hotels info to file
                        wf.write(pName+"   "+hotelName+"\n")
                        wf.write(hotelLink+"\n")
                        wf.write("Price: "+hotelPrice+"\n")
                        wf.write("Point: "+hotelPoint+"\n")
                        wf.write("\n")
                        #extract int value of price and points from string; set 0 means invalid
                        hotelPriceValue = "".join(re.findall(r'\d+', hotelPrice))
                        if hotelPriceValue!="":
                            hotelPriceInt = int(hotelPriceValue)
                        else:
                            hotelPriceInt = 0
                        hotelPointValue = "".join(re.findall(r'\d+', hotelPoint))
                        if hotelPointValue!="":
                            hotelPointInt = int(hotelPointValue)
                        else:
                            hotelPointInt = 0
                        #create info dict, key=hotelName, value=otherAttribute
                        hotelKey = hotelName
                        hotelValue = [pName, hotelLink, hotelPriceInt, hotelPointInt]
                        #wf2.write(u'%s'%hotelKey+" : "+str(hotelValue)+",\n")
                        hotelDict[hotelKey] = hotelValue
                        # ------ process resultQueue --- while loop end
        hotelValidPriceDict = {}
        hotelValidPointDict = {}
        hotelBothValidDict = {}
        #get 3 dicts with valid price, points value and both
        for item in hotelDict:
            if hotelDict[item][2] != 0:
                hotelValidPriceDict[item] = hotelDict[item]
            if hotelDict[item][3] != 0:
                hotelValidPointDict[item] = hotelDict[item]
            if hotelDict[item][2] != 0 and hotelDict[item][3] >= self.pointThreshold:
                hotelBothValidDict[item] = hotelDict[item]
        #sort by price
        print("====== Sort By Price --- From High to Low =====")
        orderedPrice = sorted(hotelValidPriceDict.items(), key=lambda x:x[1][2], reverse=True)
        with open(self.priceFileName, 'w') as wfPrice:
            for i in range(0, len(orderedPrice)):
                wfPrice.write(u"%s:     %s      价格: CNY %s     链接: %s"%(orderedPrice[i][0], orderedPrice[i][1][0], orderedPrice[i][1][2], orderedPrice[i][1][1])+'\n')
                print(orderedPrice[i])
        #sort by points
        print("====== Sort By Point --- From High to Low =====")
        orderedPoint = sorted(hotelValidPointDict.items(), key=lambda x:x[1][3], reverse=True)
        with open(self.pointFileName, 'w') as wfPoint:
            for i in range(0, len(orderedPoint)):
                wfPoint.write(u"%s:     %s      积分: %s points     链接: %s"%(orderedPoint[i][0], orderedPoint[i][1][0], orderedPoint[i][1][3], orderedPoint[i][1][1])+'\n')
                print(orderedPoint[i])
        #sort by profit
        print("====== Sort By Profit --- From High to Low =====")
        for item in hotelBothValidDict:
            dictValueList = hotelBothValidDict[item]
            dictValueList.append(round(dictValueList[2]/dictValueList[3],4))
        orderedProfit = sorted(hotelBothValidDict.items(), key=lambda x: x[1][4], reverse=True)
        with open(self.profitFileName, 'w') as wfProfit:
            for i in range(0, len(orderedProfit)):
                wfProfit.write(u"%s:     %s      积分转化率: %s     价格: CNY %s     积分: %s points     链接: %s"%(orderedProfit[i][0], orderedProfit[i][1][0], orderedProfit[i][1][4], orderedProfit[i][1][2], orderedProfit[i][1][3], orderedProfit[i][1][1])+'\n')
                print(orderedProfit[i])
        #wf2.close()

class ThreadGetAndParse(threading.Thread):
    def __init__(self, payloadQueue, resultQueue, threadName, headers, cookies, getHotelUrl, hotelXpath, searchConfig):
        self.payloadQueue = payloadQueue
        self.resultQueue = resultQueue
        self.threadName = threadName
        self.headers = headers
        self.cookies = cookies
        self.getHotelUrl = getHotelUrl
        self.hotelXpath = hotelXpath
        self.searchConfig = searchConfig
        #call parent __init__() to initialize
        super(ThreadGetAndParse, self).__init__()

    def run(self):
        while not SpgSpider.CRAWLER_EXIT:
            try:
                pCode = self.payloadQueue.get(False)
                provinceHotelInfo = self.get_hotel_price(pCode)
                self.resultQueue.put(provinceHotelInfo)
            except:
                pass
        print("------ %s Ends ------"%self.threadName)

    def get_hotel_price(self, pCode):
        payload = self.searchConfig
        payload["stateProvince"] = pCode
        response = requests.get(self.getHotelUrl, headers=self.headers, params=payload, cookies=self.cookies, verify=False)
        sleep(2)
        #print(response.text)
        html = etree.HTML(response.text)
        #get hotel names
        hotelChineseNames = html.xpath(self.hotelXpath[0])
        hotelEnglishNames = html.xpath(self.hotelXpath[1])
        #combine chinese name and english name --- qianye: don't capture English names for unresolved issue
        #hotelNames = list(map(lambda x,y: x+y, hotelChineseNames, hotelEnglishNames))
        hotelNames = hotelChineseNames
        #get hotel links
        hotelLinks = html.xpath(self.hotelXpath[2])
        #get hotel prices
        hotelPrices = html.xpath(self.hotelXpath[3])
        #get hotel points
        hotelPoints = html.xpath(self.hotelXpath[4])
        print("pCode = %s"%pCode)
        print(hotelNames)
        print(hotelLinks)
        print(hotelPrices)
        print(hotelPoints)
        provinceHotelInfo = {
            "provinceCode" : pCode,
            "nameList" : hotelNames,
            "linkList" : hotelLinks,
            "priceList" : hotelPrices,
            "pointList" : hotelPoints
        }
        return provinceHotelInfo

if __name__ == '__main__':
    startTime = time()
    spg = SpgSpider()
    spg.spider()
    endTime = time()
    print("------ Time Cost = %.2f Seconds"%(endTime-startTime))