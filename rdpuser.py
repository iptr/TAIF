import binascii
import os
import threading
import socket
import time
import sys
import select
from io import IOBase
import commonlib
from multiprocessing import Process


# 스택 사이즈 결정
if sys.version_info >= (3, 5):
	threading.stack_size(1024 * 1024 * 2)

# 기본 타임아웃 시간 설정
socket.setdefaulttimeout(5)


class Packet:
	direction = True
	packet = ''

	def __init__(self, direction, packet):
		'''
		생성자

		@param
			direction - 세션 구분자
			packet - 데이터
		'''
		self.direction = direction
		self.packet = packet


class PacketReader:
	@staticmethod
	def read(data):
		'''
		패킷 데이터를 읽는 함수

		@param
			data - 패킷 데이터

		@return
			읽은 패킷 데이터 리스트
		'''

		datas = ""

		# 패킷 데이터 줄단위로 나눔
		if isinstance(data, list) or isinstance(data, str):
			data = ''.join(data)
			datas = data.split('\n')
		else:
			print("ERROR!@#!@#")
			return False

		ret = []
		packet = []

		last_direction = True
		for l in datas:
			l_strip = l.strip()
			if len(l_strip) == 0:
				if len(packet) == 0:
					continue
				ret.append(Packet(last_direction, bytes(packet)))
				packet = []
				continue
			direction = l[0] != ' '
			# Check direction.
			if last_direction != direction and len(packet) != 0:
				ret.append(Packet(last_direction, bytes(packet)))
				packet = []
			last_direction = direction

			values = ''.join(l_strip[10:59].split(' '))
			# ASCII 변환
			bytes_value = binascii.unhexlify(values)
			packet.extend(list(bytes_value))

			if (len(bytes_value) < 16 and len(packet) != 0):
				# 패킷을 바이트로 인코딩 한 결과를 추가
				ret.append(Packet(last_direction, bytes(packet)))
				packet = []

		if len(packet) != 0:
			ret.append(Packet(last_direction, bytes(packet)))

		return ret


class VirtualConnector:
	lock = threading.Lock()

	def __init__(self, userIP, userPort, wtaIp, wtaPort):
		'''

		@param
			wtaIp - wta IP
			wtaPort - wta PORT
		'''
		self.wtaIp = wtaIp
		self.wtaPort = wtaPort
		self.serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.serversocket.bind(('', 4003))
		self.serversocket.listen(100)

	def connect(self):
		self.lock.acquire()
		try:
			terminal_socket1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			wta_manager_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			wta_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			terminal_socket1.connect(("192.168.4.190",4095))
			wta_manager_socket.connect(("127.0.0.1", 4000))
			print("eee")
			wta_server_socket.connect(("127.0.0.1",4001))
			print("fff")
			(terminal_socket, address) = self.serversocket.accept()
			return (wta_manager_socket, wta_server_socket,terminal_socket,terminal_socket1)
		except Exception as e:
			print("ddddd")
			print(e)
		finally:
			self.lock.release()

	def destroy(self):
		self.serversocket.close()


class Worker(threading.Thread):
	def __init__(self, num, connector, packets,
				 timeout, repeat, sleep, verbose,
				 callback, callback_arg):
		threading.Thread.__init__(self)
		self.num = num
		self.connector = connector
		self.packets = packets
		self.timeout = timeout
		self.repeat = repeat
		self.sleep = sleep
		self.verbose = verbose
		self.callback = callback
		self.callback_arg = callback_arg
		self.cancelFlag = False
		self.progressCallback = None
		self.progressCallbackArg = None

	def setProgressCallback(self, callback, callbackarg):
		self.progressCallback = callback
		self.progressCallbackArg = callbackarg

	def run(self):
		'''
		시작 하는 함수

		'''
		print("Start thread %d." % self.num)
		if self.repeat == 0:
			while True:
				self.test()
		else:
			for i in range(self.repeat):
				self.test()
				if (self.cancelFlag):
					break
		if self.cancelFlag:
			print("Job canceled in thread %d." % self.num)
		else:
			print("End thread %d." % self.num)

	def cancel(self):
		self.cancelFlag = True

	def test(self):
		'''
		패킷 테스트 하는 함수
		'''
		if self.cancelFlag:
			self.callback(self.callback_arg)
			return

		wta_manager_socket = None
		wta_server_socket = None
		terminal_socket = None
		s1 = None
		try:
			print("Connecting %d..." % self.num)
			(wta_manager_socket, wta_server_socket,terminal_socket,s1) = self.connector.connect()
			print("Connected %d." % self.num)

			if self.timeout:
				wta_manager_socket.settimeout(self.timeout)
				wta_server_socket.settimeout(self.timeout)
				terminal_socket.settimeout(self.timeout)

			pos = 0

			while pos < len(self.packets):
				packet = self.packets[pos]
				pos_end = pos + 1
				while pos_end < len(self.packets):
					packet2 = self.packets[pos_end]
					if packet.direction != packet2.direction:
						break
					pos_end += 1
				try:
					procs = []
					for i in range(100):
						proc = Process(target=self.send_packet,args=(pos, pos_end, wta_manager_socket, wta_server_socket,terminal_socket,s1,))
						procs.append(proc)
					for proc in procs:
						proc.start()
					for proc in procs:
						proc.join()
					#self.send_packet(pos, pos_end, wta_manager_socket, wta_server_socket,terminal_socket,s1)
					print("dddzzzz123")

				except socket.timeout:
					print('T(%d/0)' % len(packet.packet), end=' ')
					sys.stdout.flush()
				if self.progressCallback:
					self.progressCallback(self.progressCallbackArg, pos_end - pos)
				pos = pos_end
				if self.cancelFlag:
					break

			if self.sleep != 0:
				time.sleep(self.sleep)
			wta_manager_socket.close()
			wta_manager_socket = None
			wta_server_socket.close()
			wta_server_socket = None
			terminal_socket.close()
			terminal_socket = None
			s1.close()
			s1 = None
			print("Disconnected %d." % self.num)
		except Exception as e:
			print("dddddd3333")
			print(e)

		if wta_manager_socket:
			wta_manager_socket.close()
		if wta_server_socket:
			wta_server_socket.close()
		if terminal_socket:
			terminal_socket.close()
		if s1:
			s1.close()

		self.callback(self.callback_arg)

	def send_packet(self, pos, pos_end, wta_manager_sock, wta_server_sock, terminal_sock,s1):
		'''
		select를 이용하여 패킷 송수신을 담당하는 함수
		'''
		sendedPacket = 0
		sended = 0
		recvedPacket = 0
		recved = 0

		direction = self.packets[pos].direction

		if direction:
			sendSocket = terminal_sock
			recvSocket = s1
		else:
			sendSocket = s1
			recvSocket = terminal_sock

		print(wta_server_sock.getpeername())
		print(wta_manager_sock.getpeername())
		print(terminal_sock.getpeername())

		packetLen = pos_end - pos

		while sendedPacket < packetLen or recvedPacket < packetLen:
			if sendedPacket < packetLen:
				outputs=[sendSocket,]
				# if direction == False:
				# 	(readable, writeable, exceptional) = select.select([ ], [c_sock,s_sock,wta_s_sock,], [ ], self.timeout)
				# else:
				# 	break
			else:
				outputs=[]
				# (readable, writeable, exceptional) = select.select([ c_sock,s_sock,wta_s_sock,], [], [ ], self.timeout)
				#(readable, writeable, exceptional) = select.select([recvSocket, ], outputs, [recvSocket, ], self.timeout)

			(readable, writeable, exceptional) = select.select([recvSocket, ], outputs, [recvSocket, ], self.timeout)

			if not (readable or writeable or exceptional):
				# timeout
				while recvedPacket < packetLen:
					sys.stdout.flush()
					recved = 0
					recvedPacket += 1
				return

			for s in readable:
				sendSize = 0
				if pos + recvedPacket < len(self.packets):
					sendSize = len(self.packets[pos].packet)
				r = s.recv(sendSize * 2 + 0x10000)

				while r:
					if recvedPacket >= packetLen:
						print('X', end=' ')
						sys.stdout.flush()
						break
					packet = self.packets[pos + recvedPacket].packet

					compareSize = len(packet) - recved
					if len(r) < compareSize:
						compareSize = len(r)
					recved += compareSize
					if recved == len(packet):
						recvedPacket += 1
						if recvedPacket == packetLen:
							if len(r) != compareSize:
								# has extra packet.
								sys.stdout.flush()
								break
						recved = 0
						sys.stdout.flush()

					r = r[compareSize:]

			for s in writeable:
				print(s)
				packet = self.packets[pos + sendedPacket].packet
				if sended == 0:
					print("Send")
					print(direction)
					print(type(packet))
					r = s.send(packet)
					# if direction:
					# 	r = terminal_sock.send(packet)
					# else:
					# 	r = terminal_sock.send(packet)
					# 	wta_server_sock.send(packet)
					# 	wta_manager_sock.send(packet)

				else:
					r = s.send(packet[sended:])
				if r > 0:
					sended += r
					if len(packet) <= sended:
						sended = 0
						sendedPacket += 1
						if self.sleep != 0:
							time.sleep(self.sleep)

			if exceptional:
				print('E', end=' ')
				sys.stdout.flush()
				return


def runTest():
	datafile = 'packet_tester.txt'
	repeat = 1
	thread_count = 1
	time_out = 5
	sleep_time = 0
	verbose = False

	if not os.path.exists(datafile):
		print('ERROR:', datafile, 'is not exist.')
		sys.exit(-1)

	hexdata = commonlib.readFileLines(datafile)
	packets = PacketReader.read(hexdata)
	print(packets)

	connector = VirtualConnector("127.0.0.1", 5000, "127.0.0.1", 4000)

	totalTest = repeat * thread_count
	curCount = 0

	def callback(arg):
		arg[0] = arg[0] + 1
		print('%d/%d' % (totalTest, arg[0]), end=' ')

	callback_arg = [curCount]

	start_time = time.time()

	threads = []
	for i in range(thread_count):
		threads.append(Worker(i + 1, connector, packets,
							  time_out, repeat, sleep_time, verbose,
							  callback, callback_arg))
		time.sleep(0)
	for i in threads:
		print('Thread starting : ', i.num)
		i.start()
	for i in threads:
		i.join()
		print('Thread joined.', i.num)

	elapsed_time = time.time() - start_time
	print('\n')
	print('Done. [%02d:%02d:%02.2d]' % (int(elapsed_time) / 60 / 60, int(elapsed_time) / 60 % 60, elapsed_time % 60))


if __name__ == '__main__':
	runTest()

