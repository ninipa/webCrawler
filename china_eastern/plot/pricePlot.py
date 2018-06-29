#!/usr/bin/python3
###############################################################################
# Author    :   Qianye Wu
# Email     :   ninipa1985@outlook.com
# Last modified : 2018-04-20 13:42
# Filename   : pricePlot.py
# Description    : 
###############################################################################

import sys
import re

import matplotlib.pyplot as plt
import numpy as np

#set auto layout of plot
from matplotlib import rcParams
rcParams.update({'figure.autolayout': True})

priceInfoFile = sys.argv[1]
defaultTax = 2500

pattern = re.compile(r"Departure Date: ([\d-]+).*?priceList.*?\[['\[]?([\d\.]*)['\]]?")
#                                                |               |          |   |
#                                       shortest match           |          |   |
#                                                    match ' or [ or none   |   |
#                                                           match "777.7" or "" |
#                                                               match ' or ] or none
#example string
#"Departure Date: 2018-04-21 {'priceList': ['6830.0', '7140.0', ..... blabla"
#"Departure Date: 2018-04-22 {'priceList': [], 'cabinCodeList': [], ..... blabla"

#for info like "Departure Date: 2019-02-18 --- Failed to get price", to get the date
pattern2 = re.compile(r"Departure Date: ([\d-]+)")

def get_average(numList, step):
    averagePriceList = []
    for i in range(0,len(numList),step):
        averagePrice = int(np.mean(numList[i:i+step]))
        averagePriceList.append(averagePrice)    
    return averagePriceList

with open(priceInfoFile, 'r') as rf:
    info = rf.readlines()
dateList = []
priceList = []
for item in info:
    capturedInfo = pattern.match(item)
    if capturedInfo is not None:
        date = capturedInfo.group(1)
        price = capturedInfo.group(2)
    else:
        date = pattern2.match(item).group(1)
        price = ""
    dateList.append(date)
    if price != "":
        priceFloat = float(price)+2500   #transform to float for plot; tax is included (usually around CNY2500)
        priceList.append(priceFloat)
    else:
        priceList.append(priceList[-1]) #sometimes, get NULL price, set default price to previous valid price

#print date and price
for i in range(0,len(dateList)):
    print("[%s]: date = %s; price = %s"%(i, dateList[i], priceList[i]))

#number of price is too large (around 300), plot will be ugly, so calculate the average price for each week
averagePriceList = get_average(priceList, 7)

#gen xticks
dateXticks = [dateList[0],]
for date in dateList[0::7]:
    if date[0:7] != dateXticks[-1][0:7]:
        dateXticks.append(date)

try:
    fig, ax = plt.subplots()
    ax.plot(dateList[0::7], averagePriceList, '--bo')
    ax.set_xticks(dateXticks)
    for xLabel in ax.get_xticklabels():
        xLabel.set_rotation("vertical")
    ax.grid(True)
    plt.show()
except Exception as e:
    print(e)
    print("plot failured")
finally:
    print("done")

