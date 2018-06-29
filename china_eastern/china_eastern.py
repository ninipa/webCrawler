#!/usr/bin/python3
###############################################################################
# Author    :   Qianye Wu
# Email     :   ninipa1985@outlook.com
# Last modified : 2018-04-19 23:13
# Filename   : china_eastern.py
# Description    : 
###############################################################################

# -*- coding: utf-8 -*-

import sys
import time
from random import randint

import requests
import json

sys.path.append("/home/qianye/work/python")
from mytools.MydateGen import MydateGen #my own module

################## User CFG ##############
startDate = "2018-05-08"
loopNum = 350         #number of request loops, Max value is 365-roundTripGap. eg. 365-7=358
roundTripGap = 7    #gap days betwwen departure date and return date
####
# Example:
# startDate = "2018-04-19"; loopNum = 3; roundTripGap = 7
# result:
# round trip price of --- 
# departure "2018-04-19" & return "2018-04-26"
# departure "2018-04-20" & return "2018-04-27"
# departure "2018-04-21" & return "2018-04-28"
####


###################### default HTTP request ARGs ##########
#get post url by Fiddler
URL = "http://www.ceair.com/otabooking/flight-search!doFlightSearch.shtml"

#get post request header by Fiddler
headers = {
    "Accept" : "application/json, text/javascript, */*; q=0.01",
    "User-Agent" : "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36",
    "Content-Type" : "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept-Language" : "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,zh-TW;q=0.6",
}

#There is requests bug to post multi-layer dict, so transform to json first
postData = {"adtCount":1,"chdCount":0,"infCount":0,"currency":"CNY","tripType":"RT","recommend":False,"page":"0","sortType":"a","sortExec":"a","segmentList":[{"deptCd":"SHA","arrCd":"SFO","deptDt":"2018-8-1","deptAirport":"","arrAirport":"","deptCdTxt":"上海","arrCdTxt":"旧金山","deptCityCode":"SHA","arrCityCode":"SFO"},{"deptCd":"SFO","arrCd":"SHA","deptDt":"2018-8-8","deptAirport":"","arrAirport":"","deptCdTxt":"旧金山","arrCdTxt":"上海","deptCityCode":"SFO","arrCityCode":"SHA"}]}
postJSON = json.dumps(postData)
param = dict(
    _="22cafae0417f11e886776b02c323bd9a",
    searchCond=postJSON
)

def get_price(url, headers, param):
    session = requests.Session()
    #session.proxies = dict(http="192.168.0.104:8888",https="192.168.0.104:8888")   #Make traffic go through host, thus Fiddler in host can capture Python requests
    resp = session.post(URL, headers=headers, data=param)
    resp.encoding = "utf-8"
    flightsInfo = resp.json()
    #get salePrice and corresponding info from JSON;
    productUnits = flightsInfo["airResultDto"]["productUnits"]
    productNum = len(productUnits)
    dateInfo = dict(priceList=[], mileageList=[], cabinCodeList=[]) #store needed units (with info) for each date
    for i in range(0, productNum):
        if (productUnits[i]["productInfo"]["productName"]=="经济舱") and \
           (productUnits[i]["productInfo"]["purpose"] is not None) and \
           (productUnits[i]["productInfo"]["purpose"].find("国际直达") != -1): #get (economy/direct round trip) units
            units = productUnits[i]
            for fareInfoView in units["fareInfoView"]:
                if fareInfoView["paxType"] == "ADT":    #only needs ADT in {ADT, CHD, INF}
                    dateInfo["priceList"].append(fareInfoView["fare"]["salePrice"])
            dateInfo["mileageList"].append(units["productInfo"]["mileage"])
            dateInfo["cabinCodeList"].append(units["cabinInfo"]["cabinCode"])
    return dateInfo

def loop_request(startDate, loopNum, roundTripGap):
    ######################
    #   1. There is requests bug to post multi-layer dict, so transform to json first
    #   2. get postData by Fiddler
    #   3. Note about stupid issue: It's very strange that SOMETIMES if date is like "2018-<0>4-<0>9" in postData (unnecessary '0' in month/day), referenceTax will return NULL... Eg. 2018-10-01 to 2018-10-08
    #      But you can't simply remove unneccesary "0" in month/day, in such cases --- 2018-4-24 to 2018-5-1, you can't get valid JSON, maybe it's because width mismatch in two dates...Shit     
    #      update 2018/04/19 --- give up Tax capturing ...
    wholeYearDatesObj = MydateGen(startDate, 365)   #generate whole year date from startDate by default
    wholeYearDates = wholeYearDatesObj.gen_dates()
    with open("priceInfo.txt", 'w') as wf:
        for i in range(0,loopNum):
            departureDate = wholeYearDates[i]   #format --- [2018,4,19] (each unit is int)
            returnDate = wholeYearDates[i+roundTripGap]
            departureDateStr = "-".join(departureDate)
            returnDateStr = "-".join(returnDate)
            print("dpt = %s; rtt = %s"%(departureDateStr, returnDateStr))
            postData = {"adtCount":1,"chdCount":0,"infCount":0,"currency":"CNY","tripType":"RT","recommend":False,"page":"0","sortType":"a","sortExec":"a","segmentList": \
                       [{"deptCd":"SHA","arrCd":"SFO","deptDt":departureDateStr,"deptAirport":"","arrAirport":"","deptCdTxt":"上海","arrCdTxt":"旧金山","deptCityCode":"SHA","arrCityCode":"SFO"}, \
                       {"deptCd":"SFO","arrCd":"SHA","deptDt":returnDateStr,"deptAirport":"","arrAirport":"","deptCdTxt":"旧金山","arrCdTxt":"上海","deptCityCode":"SFO","arrCityCode":"SHA"}]}
            postJSON = json.dumps(postData)
            param = dict(_="22cafae0417f11e886776b02c323bd9a", searchCond=postJSON)
            try:
                priceInfo = get_price(URL, headers, param)
                print("Departure Date: %s --- %s\n"%(departureDateStr, str(priceInfo)))
                wf.write("Departure Date: %s --- %s\n"%(departureDateStr, str(priceInfo)))
            except Exception as e:
                print("Departure Date: %s RaiseException %s\nFailed to get price of date[%s]"%(departureDateStr, e, departureDateStr))
                wf.write("Departure Date: %s --- Failed to get price\n"%departureDateStr)
            #sleep to protect spider
            time.sleep(randint(10,15))

if __name__ == "__main__":
    loop_request(startDate, loopNum, roundTripGap)
