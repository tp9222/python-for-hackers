import pydnsbl
ip_checker = pydnsbl.DNSBLIpChecker()
RESULT=ip_checker.check('68.128.212.240')
print(RESULT.blacklisted)
