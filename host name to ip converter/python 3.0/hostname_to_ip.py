import socket 
import sys
if sys.version_info[0] < 3:

	INPUTFILENAME = raw_input('Enter Input filename with extenstion[hostlist.txt]: ') or 'hostlist.txt'
	OUTPUTFILENAME = raw_input('Enter Output filename with extenstion[output.txt]: ') or 'output.txt'
	LISTOFFAILDHOST = raw_input('Enter Output filename with extenstion[list_of_faild_host.txt]: ') or 'list_of_faild_host.txt'

	filepointertoOUTPUTFILENAME = open(OUTPUTFILENAME, "w")
	filepointertoLISTOFFAILDHOST = open(LISTOFFAILDHOST, "w")
	try:
	
		for line in open(INPUTFILENAME): 
		
			hostname = line.strip()
			faildhost=hostname
			try:
				print("IP address for {0} is {1}.".format(hostname,socket.gethostbyname(hostname)))
				filepointertoOUTPUTFILENAME.write("\nIP address for {0} is {1}.".format(hostname,socket.gethostbyname(hostname)))
			except socket.gaierror:
				print ("failed address lookup for " + faildhost)
				filepointertoLISTOFFAILDHOST.write(faildhost)
	except IOError as e:
		print("Input file missing");
		
	filepointertoOUTPUTFILENAME.close()
	filepointertoLISTOFFAILDHOST.close()
else:


	INPUTFILENAME = input('Enter Input filename with extenstion[hostlist.txt]: ') or 'hostlist.txt'
	OUTPUTFILENAME = input('Enter Output filename with extenstion[output.txt]: ') or 'output.txt'
	LISTOFFAILDHOST = input('Enter Output filename with extenstion[list_of_faild_host.txt]: ') or 'list_of_faild_host.txt'

	filepointertoOUTPUTFILENAME = open(OUTPUTFILENAME, "w")
	filepointertoLISTOFFAILDHOST = open(LISTOFFAILDHOST, "w")
	try:
	
		for line in open(INPUTFILENAME): 
		
			hostname = line.strip()
			faildhost=hostname
			try:
				print("IP address for {0} is {1}.".format(hostname,socket.gethostbyname(hostname)))
				filepointertoOUTPUTFILENAME.write("\nIP address for {0} is {1}.".format(hostname,socket.gethostbyname(hostname)))
			except socket.gaierror:
				print ("failed address lookup for " + faildhost)
				filepointertoLISTOFFAILDHOST.write(faildhost)
	except OSError as e:
		print("Input file missing");
			
	filepointertoOUTPUTFILENAME.close()
	filepointertoLISTOFFAILDHOST.close()

#Python 2.X and 3.X version supported
#Please report bugs to tp9222@gmail.com --Tejas Pingulkar--
