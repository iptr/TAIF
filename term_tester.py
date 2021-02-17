#!/usr/bin/python3
import time
import multiprocessing as mp
from ast import literal_eval
from typing import Tuple
from termctrl import *
from commonlib import *

CONF_FILE = 'conf/term_tester.conf'

class ConfSet:
    svc_type = None
    test_type = None
    server_list_csv = None
    persist_session = None
    start_after_deploy = None
    measure = None
    measure_delay = None
    proc_count = None
    session_count = None
    criteria = None
    test_time = None
    repeat_count = None
    session_delay = None
    cmd_delay = None
    connect_timeout = None
    bind_interface = None
    cmd_list_file = None
    files_list_file = None
    ssh_auth_type = None
    ssh_key_file = None
    ssh_cmd_func = None
    
    def __init__(self, configfile):
        conf = getfileconf(configfile)
        self.test_type = conf['Common']['test_type'].lower()
        if self.test_type in ['ssh','sftp']:
            self.svc_type = 'ssh'
        elif self.test_type == 'telnet':
            self.svc_type = 'telnet'
        elif self.test_type == 'ftp':
            self.svc_type = 'ftp'
        else:
            print('Config Error')
            return -1
        self.server_list_csv = conf['Common']['server_list_csv']
        self.persist_session = conf['Common']['persist_session'].lower()
        self.start_after_deploy = conf['Common']['start_after_deploy'].lower()
        self.measure = conf['Common']['measure'].lower()
        self.measure_delay = int(conf['Common']['measure_delay'])
        self.proc_count = int(conf['Common']['proc_count'])
        self.session_count = int(conf['Common']['session_count'])
        self.criteria = conf['Common']['criteria'].lower()
        self.test_time = int(conf['Common']['test_time'])
        self.repeat_count = int(conf['Common']['repeat_count'])
        self.session_delay = float(conf['Common']['session_delay'])
        self.cmd_delay = float(conf['Common']['cmd_delay'])
        self.connect_timeout = int(conf['Common']['connect_timeout'])       
        self.bind_interface = conf['Common']['bind_interface'].lower()
        self.cmd_list_file = conf['Input']['cmd_list_file']
        self.files_list_file = conf['Input']['files_list_file']
        self.ssh_auth_type = conf['SSHConfig']['ssh_auth_type'].lower()
        self.ssh_key_file = conf['SSHConfig']['ssh_key_file'].lower()
        self.ssh_cmd_func = conf['SSHConfig']['ssh_cmd_func'].lower()
        del conf

class DataSet:
    dataset = []

    def __init__(self, dataset):
        self.dataset = dataset
        del dataset

class ServerSet:
    slist = []
    sess_cnt = 0  

    def __init__(self, server_list, sess_cnt):
        self.slist = server_list
        self.sess_cnt = sess_cnt
        del server_list
        del sess_cnt

class Result:
    rdic = {
        # 프로세스 순서 번호
        'psn':None,
        # 대상 서버 개수
        'svrcnt':0,
        # 열었던 총 세션 개수
        'sescnt':0,
        # 명령어 개수
        'cmdcnt':0,
        # 실패 개수
        'failcnt':0,
        # 시작 시간
        'stime':0,
        # 종료 시간
        'ftime':0
    }
        
def chk_config(conf):
    # 설정내용이 올바른지 확인
    pass

def prepare():
    conf = ConfSet(CONF_FILE)
    server_list = getsvrlistcsv(conf.server_list_csv)
    rptcnt = repeater(range(conf.proc_count))
    svrsetlist = [ServerSet([],0) for i in range(conf.proc_count)]
    avail_svrlist = [] 

    # 파일 서버 목록에서 서비스 테스트 타입과 동일한 서비스 타입의 서비스만 추림
    for sl in server_list:
        if sl[1].lower() == conf.svc_type:
            avail_svrlist.append(sl)

    # (서버 * 프로세스 카운트)
    # ex) 서버가 1대이고 프로세스 8인데 세션수가 16이다 그러면 프로세스 8대에서 각각 2개의 세션을 열고 테스트를 수행한다.
    svrrpt = repeater(avail_svrlist)
    for _ in range(len(avail_svrlist)):
        svrsetlist[next(rptcnt)].slist.append(next(svrrpt))

    # 프로세스별 세션 개수 입력
    for i in range(conf.proc_count):
        svrsetlist[i].sess_cnt = conf.session_count
        
    # 명령어와 예상결과값 또는 파일명 및 파일 해쉬값 같은 테스트 필요 데이터세트 설정
    dataset = []
    if conf.test_type in ('ssh', 'telnet'):
        cmdlist = getlistfromcsv(conf.cmd_list_file)
    else:
        cmdlist = getlistfromcsv(conf.files_list_file)
    for row in cmdlist:
        if row[0].find('#') == -1:
            dataset.append(row)

    return conf, avail_svrlist, svrsetlist ,DataSet(dataset)

def connect(term, conf, svr):
    temp = term.connect(svr[1], svr[2], svr[3], svr[4], svr[5],
                                        ifc = conf.bind_interface)
    if conf.test_type in ['ssh','telnet']:
        ret = dist_client(temp, conf.ssh_cmd_func)
    elif conf.test_type == ['sftp', 'ftp']:
        ret = dist_ftpcli(temp, conf.test_type)
    else:
        return -1
    return ret
    
def runcmd(runner, client, cmd):
    if len(cmd) < 2:
        ret = runner.runcmd(client, cmd[0], '')
    else:
        ret = runner.runcmd(client, cmd[0], cmd[1])
    # 결과 검증
    c1 = type(ret) == int
    c2 = type(ret) == tuple
    c3 = c2 and ret[0] == True
    c4 = c2 and ret[0] == False
    if c1 or c4:
        return -1
    else:
        return 0

def runft(runner, client, row):
    row = next(filerpt)
    upload = row[1] + os.sep + row[0]
    remote = row[2] + os.sep + row[0] + '-'
    download = row[3] + os.sep + row[0] + '-'
    putret = runner.putfile(client, upload, remote)
    getret = runner.getfile(client, remote, download)
    #결과 검증1
    c1 = putret not in [0,None] or getret not in [0,None]
    if c1:
        r1 = False
    else:
        r1 = True
    #결과 검증2
    hash = None
    try:
        hash = getfilehash(download)
    except Exception as e:
        print(e)
    if hash == row[4]:
        r2 = True
    else:
        r2 = False
    if r1 == False or r2 == False:
        return -1
    else:
        return 0    
    
def measure_session(slist, dataset, sig):
    # 측정 여부 확인해서 주기적으로 성능 측정
    tq = mp.Queue()
    tconf = ConfSet(CONF_FILE)
    tconf.persist_session = 'true'
    tconf.proc_count = 1
    tconf.session_count = 1
    tconf.criteria = 'count'
    tconf.repeat_count = len(dataset.dataset)
    tconf.session_delay = 0
    tconf.cmd_delay = 0
    while True:
        if sig.value == 2:
            break
        tprocs = []
        tresult = []
        for i,sl in enumerate(slist):
            tresult.append([sl[0],sl[1],str(sl[2]+':'+sl[3]), 0])
            svrset = ServerSet([sl], 1)
            proc = mp.Process(target=tester, 
                            args=(tconf, svrset, dataset, i, sig, tq))
            proc.start()
            tprocs.append(proc)

        for proc in tprocs:
            proc.join()

        while tq.empty() == False:
            tmp = tq.get(block=False, timeout=5)
            if type(tmp) == dict:
                tresult[int(tmp['psn'])][3] = float(tmp['ftime']) - float(tmp['stime'])
        
        for tr in tresult:
            print(tr)
        print('\n')
        time.sleep(tconf.measure_delay)


def dist_ftpcli(client, test_type):
    if type(client) == int:
        return -1
    elif type(client) == tuple and test_type.lower() == 'sftp':
        return client[2]
    elif type(client) == fl.FTP and test_type.lower() == 'ftp':
        return client
    else:
        return -1

def dist_client(client, ssh_cmd_func):
    c1 = type(client) == tl.Telnet
    c2 = type(client) == tuple and len(client) == 3
    c5 = ssh_cmd_func == 'runcmdshell'
    c6 = ssh_cmd_func == 'runcmd'
    if c1:
        return client
    elif c2:
        c3 = type(client[0]) == pm.client.SSHClient
        c4 = type(client[1]) == pm.channel.Channel
        if c3 and c4 and c6:
            return client[0]
        elif c3 and c4 and c5:
            return client[1]
        else:
            print('Wrong Type of client')
            return -1
    else:
        print('Wrong type of client2', client, type(client))
        return -1

def showbasicconf(conf, svrsetlist, dataset):
    scnt = 0
    row2 = '\n'+'{0:^25}'.format('[ Test Processes ]') + '\n\n'
    header = '{0:<15}'.format('Server Name')
    header += '{0:^8}'.format('SVC')
    header += '{0:^20}'.format('IP Address:Port')
    header += '{0:^10}'.format('Session')
    for i, ss in enumerate(svrsetlist):
        row2 += 'Test Process #%s\n'%i
        row2 += header + '\n'
        for sl in ss.slist:
            scnt += 1 
            row = '{0:^15}'.format(sl[0])
            row += '{0:^8}'.format(sl[1])
            row += '{0:^20}'.format(sl[2]+':'+sl[3])
            row += '{0:^10}'.format(ss.sess_cnt)
            row2 += row + '\n'
        row2 += '\n'

    row1 = '\n' + '{0:^30}'.format('[Test Configuration]') + '\n\n'
    for mv in dir(conf):
        if mv.startswith('_') == False:
            row1 += mv.upper() + ' : ' + str(eval('conf.%s'%mv)) + '\n'
    row1 += 'Total Server Count : %s \n'%scnt
    row1 += 'Total Session Count : %s \n'%(scnt*conf.session_count)
    row1 += 'Total Process Count : %s \n'%conf.proc_count
    print(row1)
    print(row2)


def showresult(result):
    '''
    Total Sesssions:
    Total Command(Files) Count:
    Start Time :
    Finish Time :
    Test Running Time :
    '''
    totsvr = 0
    totses = 0
    totcmd = 0
    totfail = 0
    stime = result[1][0]
    ftime = result[1][1]

    print('\n\n[ Processes Result ]\n')
    header = '{0:^5}'.format('PSN')
    header += '{0:^5}'.format('SVR')
    header += '{0:^5}'.format('CMD')
    header += '{0:^6}'.format('Fail')
    header += '{0:^10}'.format('STime')
    header += '{0:^10}'.format('FTime')
    header += '{0:^10}'.format('Runtime')
    header += '{0:^10}'.format('TPS')
    print(header)

    for line in result[0]:
        totsvr += int(line['svrcnt'])
        totses += int(line['sescnt'])
        totcmd += int(line['cmdcnt'])
        totfail += int(line['failcnt'])
        tmp = '{0:^5}'.format(line['psn'])
        tmp += '{0:^5}'.format(line['svrcnt'])
        tmp += '{0:^5}'.format(line['cmdcnt'])
        tmp += '{0:^6}'.format(line['failcnt'])
        tmp += '{0:^10}'.format(time.strftime('%X',time.localtime(line['stime'])))
        tmp += '{0:^10}'.format(time.strftime('%X',time.localtime(line['ftime'])))
        tmp += '{0:^10.2f}'.format(line['ftime']-line['stime'])
        tmp += '{0:^10.2f}'.format(line['cmdcnt']/(line['ftime']-line['stime']))
        print(tmp)
            
    row = '\n[ Total Result ]\n'
    row += 'Total Servers: %s\n'%totsvr
    row += 'Total Sesssions: %s\n'%totses
    row += 'Total Command(Files) Count: %s\n'%totcmd
    row += 'Total Failure Count: %s\n'%totfail
    try:
        row += 'Total Success Rate: %.2f%%\n'%(100-((totfail/totcmd)*100))
    except Exception as e:
        row += 'Total Success Rate: 0%\n'
    row += 'Start Time : %s\n'%time.strftime('%c', time.localtime(stime))
    row += 'Finish Time : %s\n'%time.strftime('%c', time.localtime(ftime))
    row += 'Running Time : %.2fS\n'%(ftime - stime)
    print(row)


def run_test(conf, slist, svrsetlist, dataset):
    # 기본 설정 출력 부분
    showbasicconf(conf, svrsetlist, dataset)
    procs = []
    result = []

    # 부모 -> 자식 시그널용 공유메모리 
    # 0: 초기 정지 상태, 1: 시작, 2:종료
    sig = mp.Value('d',0)
    # 자식 -> 부모 결과 전달용 큐
    rq = mp.Queue()
    stime = time.time()
    for psn, sl in enumerate(svrsetlist):
        proc = mp.Process(target=tester, 
                          args=(conf, sl, dataset, psn, sig, rq,))
        procs.append(proc)
        proc.start()
    
    conndone = 0
    while conndone < conf.proc_count:
        while rq.empty() == False:
            buf = rq.get(block=False, timeout=5)
            if type(buf) == Tuple:
                if buf[1] == 'CD':
                    print('Process #%s : %s Sessions Connected'%(buf[0],buf[2]))
                    conndone +=1

    if conf.start_after_deploy == 'true':
        input('\n\n###### Press any key for starting... ######')
    sig.value = 1

    #중간에 세션 명령어 소요시간 측정
    if conf.measure == 'true':
        proc = mp.Process(target=measure_session,args=(slist, dataset, sig))
        proc.start()
        procs.append(proc)
    
    # 자식프로세스로부터 결과값 받아오기
    while len(result) < conf.proc_count:
        while rq.empty() == False:
            result.append(rq.get(block=False, timeout=5))
    
    sig.value = 2
    for proc in procs:
        proc.join()
    ftime = time.time()
    return result, (stime, ftime)


def tester(conf, svrset, dataset, psn, sig = None, rq = None):
    if len(svrset.slist) == 0:
        print('Server set not exist')
        return 0
    term = TermCtrl()
    if conf.test_type in ['telnet', 'ssh']:
        runner = CMDRunner()
    elif conf.test_type in ['ftp', 'sftp']:
        runner = FTRunner()
    else:
        print('Wrong Test Type')
        return -1

    r = Result()
    r.rdic['psn'] = psn
    r.rdic['svrcnt'] = len(svrset.slist)
    clients = []
    
    # 데이터세트 리피터
    dsrpt = repeater(dataset.dataset)

    #세션 지속하고 명령어만 반복
    r.rdic['stime'] = time.time()
    if conf.persist_session == 'true':
        # 접속
        for _ in range(svrset.sess_cnt):
            for svr in svrset.slist:
                client = connect(term, conf, svr)
                if client != -1:
                    r.rdic['sescnt'] += 1
                else:
                    r.rdic['result'] = -1
                    rq.put(r)
                    print(str(r), 'Error')
                    exit(-1)
                time.sleep(conf.session_delay)
                c1 = conf.test_type == 'telnet'
                c2 = conf.test_type == 'ssh'
                c3 = conf.ssh_cmd_func == 'runcmdshell'
                if c1 or (c2 and c3) :
                    runner.waitrecv(client)
                clients.append(client)
        rq.put((psn,'CD',len(clients)))

        # 시작시그널이 올때까지 대기
        while True:
            if sig.value == 1:
                break
            elif sig.value == 0:
                time.sleep(1)
            elif sig.value == 2:
                return 0
            else:
                return -1
        
        # 명령어 수행부
        while True:
            for client in clients:
                if conf.test_type in ['telnet', 'ssh']:
                    ret = runcmd(runner, client, next(dsrpt))
                    addvalue = 1
                elif conf.test_type in ['ftp', 'sftp']:
                    ret = runft(runner, client, next(dsrpt))
                    addvalue = 2
                else:
                    pass

                if ret != 0 :
                    r.rdic['failcnt'] += addvalue
                else:
                    r.rdic['cmdcnt'] += addvalue

            #테스트 종료 기준 (시간, 횟수)
            if conf.criteria == 'time':
                if (time.time() - r.rdic['stime']) >= conf.test_time:
                    break
            else:
                if r.rdic['cmdcnt'] >= (conf.repeat_count * len(clients) * addvalue):
                    break
            #딜레이
            time.sleep(conf.cmd_delay)

        for client in clients:
            client.close()
    else:
        svrrpt = repeater(svrset.slist)
        while True:
            # 접속
            svr = next(svrrpt)
            client = connect(term, conf, svr)
            if client != -1:
                r.rdic['sescnt'] += 1
            else:
                rq.put(result)
                print(str(result), 'error')
                exit(-1)
            runner.waitrecv(client)
            
            # 명령어/파일 전송 수행
            if runcmd(runner, next(client), next(dsrpt)) != 0:
                r.rdic['failcnt'] += 1
            
            #테스트 종료 기준 (시간, 횟수)
            if conf.criteria == 'time':
                if (time.time() - r.rdic['stime']) >= conf.test_time:
                    client.close()
                    break
            else:
                if r.rdic['cmdcnt'] >= conf.repeat_count:
                    client.close()
                    break
            time.sleep(conf.cmd_delay)
    r.rdic['ftime'] = time.time()
    rq.put(r.rdic)

 
if __name__ == '__main__':
    # 테스트 준비
    conf, slist, svrsetlist, dataset = prepare()
    
    # 테스트 실행
    result = run_test(conf, slist, svrsetlist, dataset)

    # 결과 출력
    showresult(result)