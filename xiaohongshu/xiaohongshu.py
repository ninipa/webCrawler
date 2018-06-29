#!/usr/bin/python3
# -*- coding: utf-8 -*-

from time import time
from time import sleep
from queue import Queue
import threading
from random import randint

import requests
from lxml import etree

class Xiaohongshu():
    #class attribute, to control threads
    ID_CRAWLER_EXIT = False
    ITEM_CRAWLER_EXIT = False
    def __init__(self):
        # ====================== user define area --- begin ============================
        self.threadNum = 10
        self.homeUrl = "http://www.xiaohongshu.com/explore"
        self.tabUrl = "http://www.xiaohongshu.com/web_api/sns/v2/homefeed/notes"
        self.itemUrlPrefix = "http://www.xiaohongshu.com/discovery/item/"
        self.UA = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.79 Safari/537.36"
        self.X_Forwarded_For = str(randint(1,255))+"."+str(randint(1,255))+"."+str(randint(1,255))+"."+str(randint(1,255))
        self.headers = {
            "User-Agent":self.UA,
            "Connection":"keep-alive",
            "Accept":"application/json, text/plain, */*",
            "Accept-Encoding":"gzip, deflate",
            "X-Forwarded-For":self.X_Forwarded_For,
            "Accept-Language":"en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,zh-TW;q=0.6"
        }
        self.maxPageNum = 40
        self.likesThreshold = 1000 #only items whose "likes" more than threshold will be put in the itemLinkQueue
        #Query Strings
        self.pageSize = 50  #This is a value got by manual testing; make each request get as much info
        self.tab = [
            'recommend',
            #'fasion',
            #'cosmetics',
            #'food',
            #'sport',
            #'media',
            #'travel',
            #'home',
            #'babycare',
            #'books',
            #'digital',
            #'mens_fasion',
            #'medicine',
        ]
        self.pageXpath = [
            #text body [0]
            '//div[@class="card-note pc-container"]/div[@class="left-card"]/div[not(contains(@class, "all-tip"))]/div[@class="content"]/p/text()',
            #likes [1]
            '//div[@class="card-note pc-container"]/div[@class="left-card"]/div[contains(@class, "tags")]//span[@class="like"]//text()',
            #comments [2]
            '//div[@class="card-note pc-container"]/div[@class="left-card"]/div[contains(@class, "tags")]//span[@class="comment"]//text()',
            #favorite [3]
            '//div[@class="card-note pc-container"]/div[@class="left-card"]/div[contains(@class, "tags")]//span[@class="star"]//text()',
            #time(list result) [4]
            '//div[@class="card-note pc-container"]/div[@class="left-card"]/div[contains(@class, "tags")]//span[@class="title" or @class="time"]//text()',
            #author [5]
            '//div[@class="card-note pc-container"]/div[@class="right-card"]//span[@class="name-detail"]/text()',
            #card-info(list result) [6]
            '//div[@class="card-note pc-container"]/div[@class="right-card"]//div[@class="card-info"]//span/text()',
            #image link(list result) [7]
            '//div[@class="card-note pc-container"]/div[@class="left-card"]/div[@class="bottom-gap"]//i[@class="img"]/@style',
        ]
        # ====================== user define area --- end ============================
        #create pageNum queue
        self.pageNumQueue = Queue()
        for i in range(1, self.maxPageNum+1):
            self.pageNumQueue.put(i)
        #link queue which stores link(ID) of each item
        self.itemLinkQueue = Queue()
        #item queue which stores all the info/content of each item
        self.itemInfoQueue = Queue()
        #dict equivlent to itemInfoQueue
        self.infoDict = {}

    def spider(self):
        '''
        Main function
        Step 1 --- get_item_link() according to Tabs, put item ID(link) into itemLinkQueue
        Step 2 --- crawl_item(), get likes, favorite, author info - {notes, fans, total-likes}, text, image
        Step 3 --- data_process(), sorted by "likes"
        '''
        # Step 1
        for tab in self.tab:
            self.get_item_link(tab)
        # Step 2
        print("itemLinkQueue size = %s"%self.itemLinkQueue.qsize())
        self.crawl_item()
        #while not self.itemInfoQueue.empty():
        #    print(self.itemInfoQueue.get(False))
        # Step 3
        self.data_process()

    def get_item_link(self, tab):
        '''
        Get ID of each link (http address)
        Multi-Threads
        Get "self.pageSize" items per request
        '''
        print("------ Multi-Thread Item ID Crawlers Start ------")
        #Get 1st page of the tab and cookies
        queryString = {
            'tab' : tab
        }
        self.session = requests.session()
        response = self.session.get(self.homeUrl, headers=self.headers, params=queryString, verify=False)
        cookies = self.session.cookies
        # -------- Multiple Threads control begin ------------
        crawlerList = []
        for i in range(0, self.threadNum):
            crawlerList.append("webCrawler_NO.%s"%i)
        #print(crawlerList)
        threadPool = []
        for crawlerName in crawlerList:
            thread = ThreadGetItemLink(self.pageNumQueue, self.itemLinkQueue, crawlerName, self.tabUrl, tab, self.pageSize, self.headers, cookies, self.likesThreshold)
            thread.start()
            threadPool.append(thread)
        # keep threading until pageNumQueue is empty
        while not self.pageNumQueue.empty():
            pass
        # change flag to make threads end
        Xiaohongshu.ID_CRAWLER_EXIT = True
        print("pageNum queue is empty")
        #wait until threads ends
        for thread in threadPool:
            thread.join()
        print("------ Multi-Thread Item ID Crawlers Are Finished ------")
        # -------- Multiple Threads control end ------------

    def crawl_item(self):
        '''
        Get content of each link, including text body, likes/comment/favorite, publish time, author info, img link
        Put into itemInfoQueue
        '''
        print("------ Multi-Thread Item Content Crawlers Start ------")
        # -------- Multiple Threads control begin ------------
        crawlerList = []
        for i in range(0, self.threadNum):
            crawlerList.append("webCrawler_NO.%s"%i)
        #print(crawlerList)
        threadPool = []
        for crawlerName in crawlerList:
            thread = ThreadGetItemInfo(self.itemLinkQueue, self.itemInfoQueue, crawlerName, self.itemUrlPrefix, self.pageXpath, self.headers, self.session.cookies)
            thread.start()
            threadPool.append(thread)
        # keep threading until IDQueue is empty
        while not self.itemLinkQueue.empty():
            pass
        # change flag to make threads end
        Xiaohongshu.ITEM_CRAWLER_EXIT = True
        print("ID queue is empty")
        #wait until threads ends
        for thread in threadPool:
            thread.join()
        print("------ Multi-Thread Item Content Crawlers Are Finished ------")
        # -------- Multiple Threads control end ------------

    def data_process(self):
        while not self.itemInfoQueue.empty():
            item = self.itemInfoQueue.get(False)
            self.infoDict[item[0]] = item[1:]   #key=url, value=other_data
        #for ditem in self.infoDict:
        #    print([ditem,self.infoDict[ditem]])
        #sorted by "likes"
        orderedItem = sorted(self.infoDict.items(), key=lambda x:x[1][3], reverse=True)
        with open('item.txt', 'w') as wf:
            for i in orderedItem:
                print(i)
                wf.write(str(i)+'\n')


class ThreadGetItemLink(threading.Thread):
    def __init__(self, pageNumQueue, itemLinkQueue, threadName, tabUrl, tab, pageSize, headers, cookies, likesThreshold):
        self.pageNumQueue = pageNumQueue
        self.itemLinkQueue = itemLinkQueue
        self.threadName = threadName
        self.tabUrl = tabUrl
        self.tab = tab
        self.pageSize = pageSize
        self.headers = headers
        self.cookies = cookies
        self.likesThreshold = likesThreshold
        #call parent __init__() to initialize
        super(ThreadGetItemLink, self).__init__()

    def run(self):
        while not Xiaohongshu.ID_CRAWLER_EXIT:
            try:
                pageNum = self.pageNumQueue.get(False)
                print("processing pageNum=%s ThreamName=%s"%(pageNum,self.threadName))
                data = self.get_item_id(pageNum)
                if data == []:
                    #print("Invalid PageNum")
                    break
                else:
                    for item in data:
                        if item['likes'] >= self.likesThreshold:
                            #'likes' captured in tab is real number, 'likes' in each item page is probably "1.6万" and not easy for sorting; so here we also store 'likes' in linkQueue
                            self.itemLinkQueue.put([item['id'],item['likes']])
            except:
                pass
        print("------ %s Ends ------"%self.threadName)

    def get_item_id(self, pageNum):
        queryString = {
            'page_size' : self.pageSize,
            'oid' : self.tab,
            'page' : pageNum
        }
        response = requests.get(self.tabUrl, headers=self.headers, cookies=self.cookies, params=queryString, verify=False)
        sleep(randint(5,10))
        data = response.json()['data']
        return data

class ThreadGetItemInfo(threading.Thread):
    def __init__(self, itemLinkQueue, itemInfoQueue, threadName, itemUrlPrefix, pageXpath, headers, cookies):
        self.itemLinkQueue = itemLinkQueue
        self.itemInfoQueue = itemInfoQueue
        self.threadName = threadName
        self.itemUrlPrefix = itemUrlPrefix
        self.pageXpath = pageXpath
        self.headers = headers
        self.cookies = cookies
        #call parent __init__() to initialize
        super(ThreadGetItemInfo, self).__init__()

    def run(self):
        while not Xiaohongshu.ITEM_CRAWLER_EXIT:
            try:
                itemLinkAndLikes = self.itemLinkQueue.get(False)
                itemUrl = self.itemUrlPrefix+itemLinkAndLikes[0]  #gen full link
                itemlikes = int(itemLinkAndLikes[1])
                print("%s processing %s"%(self.threadName, itemUrl))
                info = self.get_item_info(itemUrl, itemlikes)
                self.itemInfoQueue.put(info)
            except:
                pass
        print("------ %s Ends ------"%self.threadName)

    def get_item_info(self, url, likes):
        response = requests.get(url, headers=self.headers, cookies=self.cookies, verify=False)
        sleep(randint(5,10))
        pageSrc = response.text
        # --------- Xpath captures info ----------
        # ---- example of raw result ----
        # ['男朋友生日不知道送什么？', '男朋友20岁生日～参考一下吧 买的东西价格价格都不贵 但是花的时间长 耗时差不多一个半月两个月左右', '礼物🎁但是没有选择什么1-20岁的礼物 我看很多女生会准备男朋友出生到现在每一年的礼物 是很浪漫拉！但是奶瓶小衣服小玩具那些真的挺不实用的 我就挑了一些男朋友比较需要的小东西 这样也不会浪费钱 他还能用 礼物清单在第八九张图 。因为躲躲藏藏的给他准备礼物他还是有些发觉 有点礼物还没包 刚买就被他自己拿去用了 太过分了 自己diy的礼物前两篇小红书都有写过啦！礼物包装纸是在淘宝的鲜花店包装买的 十块的20大张！丝带五块一大卷！包20个礼物刚刚好！但是最后包大礼物盒都的时候还是不够用 就零时又买了 大家要计算好 用纸 大礼物的包装盒是网上买的纸皮箱 看了很多礼物盒都太贵太小了 反正包了包装纸都很好看 包装盒的大小是45x45的 价格才8块左右 可以说是很实惠了 礼物2000-3000左右', '蛋糕🎂然后就是蛋糕 关键词在第八张图 好看 颜值高 适合拍照 我也有考虑过那种色彩鲜艳的ins蛋糕 但是想想男生应该比较喜欢这种汽车的吧！车钥匙送不起 模型车就可以！下来220左右', '布置🏠气球都都很便宜 我买的是一个鱼尾旗套餐还有一百个银色和黑色气球 就是氢气贵 一瓶氦气就要100块 但是注意氦气不要靠火，布置大概两个小时左右 背着男朋友提前先到了酒店叫好姐妹一起布置的 然后他到酒店还生气因为我打气球没有回到他信息？到了酒店偷偷笑 因为准备了很久 希望他能感动的掉眼泪 但是没有 想把他打到掉眼泪 价格150-200左右', '酒店🏨酒店地址是凯贝丽在盐田沙头角那边 附近有很多好吃的山水肠粉 生煎包 去一定要吃一下旁边的生煎包 真的超级好吃 但是图片放不下了酒店提前一个月定了 因为他生日又是端午节又是父亲节 平时400-500的价格到那一天只剩1000多的了！然后就是泳池山跟海！价格668', '去酒店的时候是下午天气超热然后还！拉着一个超大的行李箱 抱着45x45的纸皮箱 礼物行李箱都装不下然后还有一大罐氢气 我还穿着高跟鞋 可以说是非常拼命了！但是他开心幸苦也值得了～😗']
        # ['2428']
        # ['313']
        # ['6417']
        # ['发布于', '2018-06-18 22:09']
        # ['鸡珍亲你的小脸']
        # ['笔记', '8', '粉丝', '2208', '获赞与收藏', '1.9万']
        # ['background-image:url(//ci.xiaohongshu.com/87ef3586-9267-4987-87ac-8924dbec039a@r_750w_750h_ss1.jpg?imageView2/2/w/100/h/100/q/90);', 'background-image:url(//ci.xiaohongshu.com/911a85e4-7a0d-4896-966e-6a21c1fbf645@r_750w_750h_ss1.jpg?imageView2/2/w/100/h/100/q/90);', 'background-image:url(//ci.xiaohongshu.com/27e54170-2188-4319-a6c9-234e87237070@r_750w_750h_ss1.jpg?imageView2/2/w/100/h/100/q/90);', 'background-image:url(//ci.xiaohongshu.com/b7f2a690-1415-491d-a9e5-2078d1222686@r_750w_750h_ss1.jpg?imageView2/2/w/100/h/100/q/90);', 'background-image:url(//ci.xiaohongshu.com/b83128e7-7714-403a-9e49-5c5b5adf2877@r_750w_750h_ss1.jpg?imageView2/2/w/100/h/100/q/90);', 'background-image:url(//ci.xiaohongshu.com/700c8395-b13c-4675-8792-2bfe770bd719@r_750w_750h_ss1.jpg?imageView2/2/w/100/h/100/q/90);', 'background-image:url(//ci.xiaohongshu.com/53fd82d0-19ea-4c54-94ee-8d09cb1f465f@r_750w_750h_ss1.jpg?imageView2/2/w/100/h/100/q/90);', 'background-image:url(//ci.xiaohongshu.com/6ac22237-0955-4674-9a06-fb2c749aff5f@r_750w_750h_ss1.jpg?imageView2/2/w/100/h/100/q/90);', 'background-image:url(//ci.xiaohongshu.com/5f2dd225-d14b-4d09-8453-a3ae954b054d@r_750w_750h_ss1.jpg?imageView2/2/w/100/h/100/q/90);']
        html = etree.HTML(pageSrc)
        textBody = html.xpath(self.pageXpath[0])
        #likes = int(html.xpath(self.pageXpath[1])[0])
        comment = html.xpath(self.pageXpath[2])[0]
        favorite = html.xpath(self.pageXpath[3])[0]
        publishTime = html.xpath(self.pageXpath[4])
        author = html.xpath(self.pageXpath[5])
        cardInfo = html.xpath(self.pageXpath[6])
        imgRawLink = html.xpath(self.pageXpath[7])
        #create a list to store itemInfo
        info = [
            url,
            author,
            cardInfo,
            publishTime,
            likes,
            comment,
            favorite,
            textBody,
            imgRawLink,
        ]
        print("%s URL=%s"%(self.threadName, url))
        #print(textBody)
        #print(likes)
        #print(comment)
        #print(favorite)
        #print(publishTime)
        #print(author)
        #print(cardInfo)
        #print(imgRawLink)
        return info

if __name__ == '__main__':
    startTime = time()
    crawler = Xiaohongshu()
    crawler.spider()
    endTime = time()
    print("------ Time Cost = %.2f Seconds"%(endTime-startTime))
