import datetime
import time
import requests
import random
import base64
from lxml import etree
import os
import json
import platform

from acount import fot_user,fot_pwd
'''
更新日志：

2018.9.4
1.账号独立
2.加入OCR登录异常处理

2018.9.5
1.根据系统，选择文件生成路径

2018.9.7
1.根据本地数据的情况，判断是否需要登录，减少不必要登录
2.把之前每日单独访问的模式改成智能按时间段访问

2018.9.8
1.url分解params；
2.加入get_flight_detail(flightID)函数；
3.根据传入的 endDate ，以及当前时间生成 max_endDate，
  避免重复访问无延误原因的日期，避免不必要访问
4.加入判断更新昨日数据，时间点：当日17点

2018.9.9
1.修复Linux系统路径问题

2018.10.29
1.增加航班正常统计系统登录错误提示
  明确登录失败提示
2.登录失败一直重试改为连续等错误两次后等待200秒
3.有道OCR更换为百度OCR
'''
#根据时间段，生成时间列表
def dateRange(beginDate, endDate):
    dates = []
    dt = datetime.datetime.strptime(beginDate, "%Y-%m-%d")
    date = beginDate[:]
    while date <= endDate:
        dates.append(date)
        dt = dt + datetime.timedelta(1)
        date = dt.strftime("%Y-%m-%d")
    return dates
    
#根据 endDate ，生成 max_endDate
# 17点前获取前天数据，因网站17点后才锁定延误原因
def max_enddate(endDate):
    dt = datetime.datetime.now()
    yesterday = dt + datetime.timedelta(-1)
    bf_yesterday =  dt + datetime.timedelta(-2)
    if dt.hour>=17:
        max_endDate = yesterday.strftime("%Y-%m-%d")
    else:
        max_endDate = bf_yesterday.strftime("%Y-%m-%d")
    return max_endDate
    
def get_platform_path():
    if platform.system()=='Windows':
        path=''
    elif platform.system()=='Linux':
        path='/usr/share/nginx/html/data/'
    return path
    
def baidu_ocr(code_url,times=0):
    code_rep=s.get(code_url,headers=headers)
    # with open('verify_code.jpg','wb')as f:
        # f.write(code_rep.content)
    base64_data = base64.b64encode(code_rep.content)
    url0='https://cloud.baidu.com/product/ocr/general'
    url='https://cloud.baidu.com/aidemo'
    post_data={
    'type':'commontext',
    'image': 'data:image/jpeg;base64,'+str(base64_data,'utf-8'),
    'image_url':''
    }
    
    headers1={
    'User-Agent':'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36',
    'Referer':'https://cloud.baidu.com/product/ocr/general',
    }
    try:
        s.get(url0,headers=headers1)
        rep=s.post(url,headers=headers1,data=post_data)
        if rep.status_code==200:
            if rep.json().get('errno')==0:
                verify_code=rep.json().get('data').get('words_result')[0].get('words')
                return verify_code
    except:
        times=times+1
        if times<3:#最多重试三次
            if times>1:#第二次登录失败等待200秒
                time.sleep(200)
            return baidu_ocr(code_url,times=times)


def login(n=0):
    login_url='https://flightontime.cn/loginAction.do?method=logIn'
    code_url='https://flightontime.cn/loginAction.do?method=createValidationCode&d=' + str(random.random())
    code_rep=s.get(code_url,headers=headers)
    verify_code=baidu_ocr(code_url)
    post_data={
    'name': fot_user,
    'password': fot_pwd,
    'txtValidationCode': verify_code,
    'x':str(random.randint(20,232)),
    'y':str(random.randint(8,23))
    }
    # print(post_data)
    rep=s.post(login_url,headers=headers,data=post_data,allow_redirects=False,verify=False)
    if rep.status_code==302:
        print('正常统计系统登录成功')
    else:
        print(rep.status_code)
        print('正常统计系统登录失败，180秒后正在重试')
        time.sleep(180)
        n=+1
        while n<3:
            return login(n)
        
def get_flight_info(page,start_day,end_day):
    if page>1:
        currentpage=page-1
    else:
        currentpage=page
    url='https://flightontime.cn/flightInfoQueryAction.do'
    params={
    'method': 'list',
    'togo': page,
    'advanceddivdisplay':''
    }
    post_data={
    'ScheduledDateFrom': start_day.replace('-',''),
    'ScheduledDateTo': end_day.replace('-',''),
    'CallSign': 'UEA',
    'ThreeCode': '',
    'DepAP': '',
    'ArrAP': '',
    'RegCode': '',
    'adjudicate': '',
    'isnormalid': '2',
    'isInitNormalid': '',
    'isReleaseNormalid': '',
    'delayTimeStatisticid': '',
    'currentpage': currentpage,
    'togo': ''
    }
    # print(post_data)
    rep=s.post(url,headers=headers,params=params,data=post_data)
    return rep.text
    
def get_flight_detail(flightID):
    url='https://flightontime.cn/flightInfoQueryAction.do'
    params={
    'method': 'viewDetail',
    'id': flightID
    }
    rep=s.get(url,headers=headers,params=params)
    # print(rep.text)
    return rep.text
    
def one_page(page,start_day,end_day):
    html=get_flight_info(page,start_day,end_day)
    if "pagination" in html:
        html=etree.HTML(html)
        # print(etree.tostring(html).decode())
        pages=html.xpath('//div[@class="pagination"]/ul/li/text()')[0]
        current_page=pages.split('/')[0]
        pages=pages.split('/')[-1][1:-1]
        elements=html.xpath('//tbody[@id="query_result_body"]/tr[@class]')
        item_list=[]
        for element in elements:
            item={}
            item['fnum'] = element.xpath('./td[1]')[0].text.replace('UEA','EU')
            item['forg'] = element.xpath('./td[2]')[0].text
            item['fdst'] = element.xpath('./td[3]')[0].text
            # item['注册号']  = element.xpath('./td[4]')[0].text
            item['ScheduledDepTime'] = element.xpath('./td[5]')[0].text
            item['ScheduledDate'] = item['ScheduledDepTime'][:10]
            # item['计划到港时间'] = element.xpath('./td[6]')[0].text
            item['properties'] = element.xpath('./td[7]')[0].text
            item['UnnormalReason'] = element.xpath('./td[8]/input/@value')[0]
            # item['始发正常性'] = element.xpath('./td[9]/input/@value')[0]
            # item['放行正常性'] = element.xpath('./td[10]/input/@value')[0]
            if item['properties'] =='正班飞行 W/Z 正班':
                # print(item)
                item_list.append(item)
        # print(f'当前{current_page}，总共{pages}页\n',item_list,'\n\n')
        return item_list,pages
    else:
        return '',0
    
def multi_page(start_day,end_day):
    item_lists,pages=one_page(1,start_day,end_day)
    if int(pages)>=2:
        for page in range(2,int(pages)+1):
            item_list=one_page(page,start_day,end_day)[0]
            item_lists.extend(item_list)
    # print(item_lists)
    return item_lists
    
        
class NewData():
    def __init__(self,date_seg1,date_seg2):
        self.file=UnnormalReason_file
        self.date_seg1=date_seg1
        self.date_seg2=date_seg2
        
    def old_data(self):
        if os.path.isfile(self.file):
            with open(self.file,'r',encoding='utf-8') as fp:
                old_data=json.load(fp)
                old_dates=[x.get('ScheduledDate') for x in old_data]
                old_dates.sort()
            return old_data,old_dates
        else:
            return [],''
            
    def get_new_data(self):
        # 获取本地数据
        old_data,old_dates=self.old_data()
        dates=dateRange(self.date_seg1,self.date_seg2)
        # 获取新数据
        if not set(old_dates)>=set(dates):
            login()
            total_list=old_data
            for date in dates:
                if date not in old_dates:
                    data_list=[]
                    #本地无数据
                    if not old_dates:
                        print(f'正在下载{date}——{dates[-1]}正常性数据')
                        data_list=multi_page(date,dates[-1])
                    #获取起始日期早于本地数据最早日期
                    elif date < old_dates[0]:
                        dt2=datetime.datetime.strptime(old_dates[0],"%Y-%m-%d")+datetime.timedelta(-1)
                        date2=dt2.strftime("%Y-%m-%d")
                        print(f'正在下载{date}——{date2}正常性数据')
                        data_list=multi_page(date,date2)
                    #获取结束日期晚于本地数据最晚日期
                    elif date > old_dates[-1]:
                        print(f'正在下载{date}——{dates[-1]}正常性数据')
                        data_list=multi_page(date,dates[-1])
                    total_list.extend(data_list)
                    with open(self.file,'w',encoding='utf-8') as fp:
                        json.dump(total_list,fp,ensure_ascii=False)
                    old_dates=self.old_data()[1]
        with open(UnnormalReason_file,'r',encoding='utf-8') as fp:
            total_list=json.load(fp)
        return total_list
        
    
def reason_count(item_list):
    Reason1,Reason2,Reason3,Reason4,Reason5,Reason6,='天气','公司','流量','军事活动','空管','机场'
    Reason7,Reason8,Reason9,Reason10,Reason11='联检','油料','离港系统','旅客','公共安全'
    Reason={
    Reason1:0,
    Reason2:0,
    Reason3:0,
    Reason4:0,
    Reason5:0,
    Reason6:0,
    Reason7:0,
    Reason8:0,
    Reason9:0,
    Reason10:0,
    Reason11:0,
    }
    for item in item_list:
        if item['UnnormalReason'][:2]=='01':
            Reason[Reason1]+=1
        if item['UnnormalReason'][:2]=='02':
            Reason[Reason2]+=1
        if item['UnnormalReason'][:2]=='03':
            Reason[Reason3]+=1
        if item['UnnormalReason'][:2]=='04':
            Reason[Reason4]+=1
        if item['UnnormalReason'][:2]=='05':
            Reason[Reason5]+=1
        if item['UnnormalReason'][:2]=='06':
            Reason[Reason6]+=1
        if item['UnnormalReason'][:2]=='07':
            Reason[Reason7]+=1
        if item['UnnormalReason'][:2]=='08':
            Reason[Reason8]+=1
        if item['UnnormalReason'][:2]=='09':
            Reason[Reason9]+=1
        if item['UnnormalReason'][:2]=='10':
            Reason[Reason10]+=1
        if item['UnnormalReason'][:2]=='11':
            Reason[Reason11]+=1
            
    # print(Reason)
    return Reason
    
    '''
#根据时间段，更新延误数据
def update_unnormal_reason(beginDate,endDate):
    max_endDate=max_enddate(endDate)
    print('正常统计系统最新数据日期',max_endDate)
    NewData(beginDate,max_endDate).get_new_data()
    '''
    
    
###---对外接口---###
##查某航班的某航段的某个时间段内各个延误原因次数
def flight_reason(CallSign,DepAP,ArrAP,beginDate,endDate):
    max_endDate=max_enddate(endDate)
    total_list=NewData(beginDate,max_endDate).get_new_data()
    # print(total_list)
    new_dates=dateRange(beginDate,endDate)
    # print(new_dates)
    new_list=[]
    for item in total_list:
        if item['ScheduledDate'] in new_dates:
            if item['fnum']==CallSign and item['forg']==DepAP and item['fdst']==ArrAP:
                # print(item)
                new_list.append(item)
    if new_list:
        reason=reason_count(new_list)
        print(f'{CallSign} {DepAP}-{ArrAP} {beginDate}-{endDate}\n    {reason}')
        return reason
        
        
        
        
s=requests.Session()
headers={'User-Agent':'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'}
platform_path=get_platform_path()
UnnormalReason_file=platform_path+'UnnormalReason.json'

if __name__=="__main__":
    CallSign,DepAP,ArrAP,beginDate,endDate='EU6661','ZUUU','ZSPD','2018-09-28','2018-10-11'
    # update_unnormal_reason(beginDate,endDate)
    flight_reason(CallSign,DepAP,ArrAP,beginDate,endDate)
    
    
    
    